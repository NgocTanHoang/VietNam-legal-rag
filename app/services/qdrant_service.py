import logging
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
from app.core.config import settings
from app.core.exceptions import DatabaseCrashError

class QdrantService:
    def __init__(self):
        """Khởi tạo Client kết nối tới Qdrant Cloud hoặc Local"""
        try:
            self.client = QdrantClient(
                url=settings.qdrant_connection_url,
                api_key=settings.QDRANT_API_KEY
            )
            self.collection_name = settings.QDRANT_COLLECTION
        except Exception as e:
            logging.error(f"Lỗi khởi tạo Qdrant Client: {str(e)}")
            raise DatabaseCrashError("Qdrant", str(e))

    def search_legal_documents(self, query_vector: List[float], limit: int = 5, score_threshold: float = 0.3) -> List[Dict[str, Any]]:
        """
        Tìm kiếm các đoạn văn bản pháp luật tương đồng nhất dựa trên dense vector.
        """
        try:
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True
            )
            
            output = []
            for hit in results:
                # Trích xuất payload để dễ sử dụng
                payload = hit.payload or {}
                output.append({
                    "id": hit.id,
                    "score": hit.score,
                    "doc_id": payload.get("id") or payload.get("doc_id"),
                    "title": payload.get("title") or payload.get("tieu_de", "Không rõ tiêu đề"),
                    "content": payload.get("content") or payload.get("content_html") or payload.get("text", ""),
                    "so_ky_hieu": payload.get("so_ky_hieu"),
                    "tinh_trang_hieu_luc": payload.get("tinh_trang_hieu_luc", "Còn hiệu lực"),
                    "loai_van_ban": payload.get("loai_van_ban"),
                    "ngay_ban_hanh": payload.get("ngay_ban_hanh")
                })
            return output
        except Exception as e:
            logging.error(f"Lỗi khi search Qdrant: {str(e)}")
            return []

    def get_document_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin chi tiết của một văn bản dựa trên ID gốc (ở dạng metadata 'id')"""
        try:
            # Chuyển doc_id sang kiểu thích hợp (int hoặc str) tùy vào metadata lưu trữ
            # Vì trong parquet metadata ID là int64, ta thử cả hai
            try:
                search_id = int(doc_id)
            except ValueError:
                search_id = doc_id
                
            response, _ = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="id",
                            match=MatchValue(value=search_id)
                        )
                    ]
                ),
                limit=1,
                with_payload=True
            )
            
            if response:
                point = response[0]
                payload = point.payload or {}
                return {
                    "id": point.id,
                    "doc_id": payload.get("id"),
                    "title": payload.get("title") or payload.get("tieu_de"),
                    "content": payload.get("content") or payload.get("content_html"),
                    "so_ky_hieu": payload.get("so_ky_hieu"),
                    "tinh_trang_hieu_luc": payload.get("tinh_trang_hieu_luc")
                }
            return None
        except Exception as e:
            logging.error(f"Lỗi khi lấy doc by ID: {str(e)}")
            return None

    def count_documents_by_year(self, year: int) -> int:
        """Đếm số lượng văn bản ban hành trong năm cụ thể"""
        try:
            result = self.client.count(
                collection_name=self.collection_name,
                count_filter=Filter(
                    must=[
                        FieldCondition(
                            key="nam_ban_hanh",
                            match=MatchValue(value=year)
                        )
                    ]
                )
            )
            return result.count
        except Exception as e:
            logging.error(f"Lỗi khi đếm văn bản theo năm: {str(e)}")
            return 0
