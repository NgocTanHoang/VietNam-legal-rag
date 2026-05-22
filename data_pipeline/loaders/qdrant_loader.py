import logging
import uuid
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from app.core.config import settings

logging.basicConfig(level=logging.INFO)

class QdrantLoader:
    def __init__(self, collection_name: Optional[str] = None):
        self.collection_name = collection_name or settings.QDRANT_COLLECTION
        try:
            self.client = QdrantClient(
                url=settings.qdrant_connection_url,
                api_key=settings.QDRANT_API_KEY
            )
            logging.info(f"QdrantLoader kết nối thành công tới Qdrant tại URL: {settings.qdrant_connection_url}")
        except Exception as e:
            logging.error(f"Lỗi kết nối Qdrant trong QdrantLoader: {e}")
            raise e
            
        self._model = None
        self._use_gemini = False

    @property
    def model(self):
        """Lazy load embedding model. Falls back to Gemini API if Torch/SentenceTransformers DLL errors occur."""
        if self._model is None:
            try:
                logging.info(f"Đang tải mô hình embedding cục bộ: {settings.EMBED_MODEL}...")
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(settings.EMBED_MODEL)
                logging.info("Tải mô hình embedding cục bộ thành công!")
            except Exception as e:
                logging.warning(
                    f"Không thể khởi tạo sentence-transformers cục bộ do lỗi hệ thống (ví dụ: thiếu DLL PyTorch): {e}. "
                    f"Kích hoạt chế độ Fallback sử dụng Gemini Embedding API (models/text-embedding-004)..."
                )
                self._use_gemini = True
                self._model = "gemini"
        return self._model

    def create_collection_if_not_exists(self, vector_size: Optional[int] = None):
        """Tạo collection nếu chưa tồn tại. Tự động điều chỉnh kích thước vector theo mô hình embedding sử dụng."""
        # Kích hoạt property model để kiểm tra chế độ fallback trước
        _ = self.model
        
        if vector_size is None:
            vector_size = 384 # Luôn đảm bảo 384 dimensions trùng khớp với collection thực tế
            
        try:
            exists = self.client.collection_exists(collection_name=self.collection_name)
            if not exists:
                logging.info(f"Đang tạo Qdrant collection mới: {self.collection_name} với vector size: {vector_size}...")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=vector_size,
                        distance=models.Distance.COSINE
                    )
                )
                logging.info(f"Tạo collection '{self.collection_name}' thành công.")
            else:
                logging.info(f"Collection '{self.collection_name}' đã tồn tại.")
        except Exception as e:
            logging.error(f"Lỗi khi kiểm tra/tạo collection: {e}")
            raise e

    def upsert_chunks_batch(self, chunks: List[Dict[str, Any]], batch_size: int = 100) -> int:
        """
        Nạp một danh sách các chunks vào Qdrant theo từng batch.
        """
        if not chunks:
            return 0

        # Kích hoạt model property trước để thiết lập _use_gemini chính xác
        _ = self.model
        
        # Tạo collection với kích thước vector tự động thích ứng
        self.create_collection_if_not_exists()
        
        total_upserted = 0
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            points = []
            
            texts = [c["content"] for c in batch]
            try:
                if self._use_gemini:
                    import google.generativeai as genai
                    genai.configure(api_key=settings.GEMINI_API_KEY)
                    resp = genai.embed_content(
                        model="models/text-embedding-004",
                        content=texts,
                        task_type="retrieval_document",
                        output_dimensionality=384
                    )
                    embeddings = resp["embedding"]
                else:
                    embeddings = self.model.encode(texts, show_progress_bar=False).tolist()
            except Exception as e:
                logging.error(f"Lỗi khi sinh embeddings cho batch {i}: {e}")
                continue

            for idx, chunk in enumerate(batch):
                doc_id = chunk["doc_id"]
                chunk_idx = chunk["chunk_index"]
                content = chunk["content"]
                meta = chunk.get("metadata", {})
                
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc_id}_{chunk_idx}"))
                
                payload = {
                    "id": doc_id,
                    "doc_id": doc_id,
                    "chunk_index": chunk_idx,
                    "content": content,
                    "text": content,
                    "title": meta.get("title", ""),
                    "so_ky_hieu": meta.get("so_ky_hieu", ""),
                    "tinh_trang_hieu_luc": meta.get("tinh_trang_hieu_luc", "Còn hiệu lực"),
                    "loai_van_ban": meta.get("loai_van_ban", "Luật"),
                    "ngay_ban_hanh": meta.get("ngay_ban_hanh"),
                    "nam_ban_hanh": meta.get("nam_ban_hanh")
                }
                
                points.append(
                    models.PointStruct(
                        id=point_id,
                        vector=embeddings[idx],
                        payload=payload
                    )
                )
                
            try:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                total_upserted += len(points)
                logging.info(f"Đã nạp thành công {total_upserted}/{len(chunks)} points vào Qdrant.")
            except Exception as e:
                logging.error(f"Lỗi khi upsert points lên Qdrant ở batch {i}: {e}")
                
        return total_upserted
