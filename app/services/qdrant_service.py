import logging
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http.models import FieldCondition, Filter, MatchValue

from app.core.config import settings


class QdrantService:
    def __init__(self):
        self.client: Optional[QdrantClient] = None
        self.collection_name = settings.QDRANT_COLLECTION
        try:
            self.client = QdrantClient(
                url=settings.qdrant_connection_url,
                api_key=settings.QDRANT_API_KEY,
                timeout=settings.INFRA_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            logging.warning(f"Lỗi khởi tạo Qdrant Client: {exc}")

    def is_healthy(self) -> bool:
        if self.client is None:
            return False
        try:
            self.client.get_collections()
            return True
        except Exception as exc:
            logging.warning(f"Qdrant health check thất bại: {exc}")
            return False

    def search_legal_documents(
        self, query_vector: List[float], limit: int = 5, score_threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        if self.client is None:
            logging.warning("Qdrant chưa sẵn sàng. Bỏ qua vector search.")
            return []
        try:
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
                timeout=settings.INFRA_TIMEOUT_SECONDS,
            )

            output = []
            for hit in results:
                payload = hit.payload or {}
                output.append(
                    {
                        "id": hit.id,
                        "score": hit.score,
                        "doc_id": payload.get("id") or payload.get("doc_id"),
                        "title": payload.get("title")
                        or payload.get("tieu_de", "Không rõ tiêu đề"),
                        "content": payload.get("content")
                        or payload.get("content_html")
                        or payload.get("text", ""),
                        "so_ky_hieu": payload.get("so_ky_hieu"),
                        "tinh_trang_hieu_luc": payload.get(
                            "tinh_trang_hieu_luc", "Còn hiệu lực"
                        ),
                        "loai_van_ban": payload.get("loai_van_ban"),
                        "ngay_ban_hanh": payload.get("ngay_ban_hanh"),
                    }
                )
            return output
        except Exception as exc:
            logging.error(f"Lỗi khi search Qdrant: {exc}")
            return []

    def get_document_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        if self.client is None:
            return None
        try:
            try:
                search_id = int(doc_id)
            except ValueError:
                search_id = doc_id

            response, _ = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[FieldCondition(key="id", match=MatchValue(value=search_id))]
                ),
                limit=1,
                with_payload=True,
                timeout=settings.INFRA_TIMEOUT_SECONDS,
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
                    "tinh_trang_hieu_luc": payload.get("tinh_trang_hieu_luc"),
                }
            return None
        except Exception as exc:
            logging.error(f"Lỗi khi lấy doc by ID: {exc}")
            return None

    def count_documents_by_year(self, year: int) -> int:
        if self.client is None:
            return 0
        try:
            result = self.client.count(
                collection_name=self.collection_name,
                count_filter=Filter(
                    must=[
                        FieldCondition(
                            key="nam_ban_hanh",
                            match=MatchValue(value=year),
                        )
                    ]
                ),
                timeout=settings.INFRA_TIMEOUT_SECONDS,
            )
            return result.count
        except Exception as exc:
            logging.error(f"Lỗi khi đếm văn bản theo năm: {exc}")
            return 0
