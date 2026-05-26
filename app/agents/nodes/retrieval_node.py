import logging
from typing import Any, Dict

from app.agents.state import AgentState
from app.core.config import settings
from app.services.qdrant_service import QdrantService

_embed_model = None


def get_embed_model():
    global _embed_model
    if _embed_model is None:
        try:
            logging.info(f"Đang tải mô hình embedding cục bộ: {settings.EMBED_MODEL}...")
            from sentence_transformers import SentenceTransformer

            _embed_model = SentenceTransformer(settings.EMBED_MODEL)
        except Exception as exc:
            logging.warning(
                f"Lỗi khi tải sentence-transformers: {exc}. Chuyển sang fallback Gemini embedding."
            )
            _embed_model = "gemini"
    return _embed_model


def retrieval_node(state: AgentState) -> Dict[str, Any]:
    query_text = state.get("query_rewritten") or state.get("raw_query") or ""
    if not query_text:
        last_message = state.get("messages")[-1].content if state.get("messages") else ""
        query_text = last_message

    logging.info(f"--- Retrieval Node: truy vấn Qdrant cho '{query_text}' ---")

    try:
        qdrant_service = QdrantService()
        if not qdrant_service.is_healthy():
            logging.warning("Qdrant chưa sẵn sàng. Bỏ qua retrieval và trả về ngữ cảnh rỗng.")
            return {"context_chunks": []}

        from app.services.redis_service import RedisService

        redis_service = RedisService()
        query_vector = redis_service.get_embedding(query_text)

        if query_vector is None:
            model = get_embed_model()
            if model == "gemini":
                if not settings.GEMINI_API_KEY:
                    logging.warning("Thiếu GEMINI_API_KEY cho fallback embedding. Trả về retrieval rỗng.")
                    return {"context_chunks": []}
                import google.generativeai as genai

                genai.configure(api_key=settings.GEMINI_API_KEY)
                response = genai.embed_content(
                    model="models/text-embedding-004",
                    content=query_text,
                    task_type="retrieval_query",
                    output_dimensionality=384,
                )
                query_vector = response["embedding"]
            else:
                query_vector = model.encode(query_text).tolist()

            redis_service.set_embedding(query_text, query_vector)

        chunks = qdrant_service.search_legal_documents(
            query_vector=query_vector,
            limit=5,
            score_threshold=0.35,
        )
        logging.info(f"Qdrant tìm thấy {len(chunks)} đoạn văn bản phù hợp.")
        return {"context_chunks": chunks}
    except Exception as exc:
        logging.error(f"Lỗi tại Retrieval Node: {exc}", exc_info=True)
        return {"context_chunks": []}
