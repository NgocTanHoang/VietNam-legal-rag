import logging
from typing import Dict, Any
from app.core.config import settings
from app.services.qdrant_service import QdrantService
from app.agents.state import AgentState

# Khởi tạo Cache cho Embedding Model ở module-level để tránh reload nhiều lần làm chậm API
_embed_model = None

def get_embed_model():
    global _embed_model
    if _embed_model is None:
        try:
            logging.info(f"Đang tải mô hình embedding cục bộ: {settings.EMBED_MODEL}...")
            from sentence_transformers import SentenceTransformer
            _embed_model = SentenceTransformer(settings.EMBED_MODEL)
            logging.info("Tải mô hình embedding cục bộ thành công!")
        except Exception as e:
            logging.warning(
                f"Lỗi khi tải mô hình cục bộ sentence-transformers: {str(e)}. "
                f"Tự động kích hoạt chế độ Fallback sử dụng Gemini Embedding API (models/text-embedding-004)..."
            )
            _embed_model = "gemini"
    return _embed_model

def retrieval_node(state: AgentState) -> Dict[str, Any]:
    """
    Node truy vấn Vector Database Qdrant.
    Sử dụng câu hỏi đã tối ưu (query_rewritten) nếu có, nếu không sẽ dùng câu hỏi gốc (raw_query).
    """
    # Lấy query để search
    query_text = state.get("query_rewritten") or state.get("raw_query") or ""
    if not query_text:
        last_msg = state.get("messages")[-1].content if state.get("messages") else ""
        query_text = last_msg
        
    logging.info(f"--- Nodes LangGraph: Đang truy vấn Qdrant cho từ khóa: '{query_text}' ---")
    
    try:
        # 1. Tính toán vector embedding cho câu truy vấn (Thử lấy từ cache trước)
        from app.services.redis_service import RedisService
        redis_service = RedisService()
        query_vector = redis_service.get_embedding(query_text)
        
        if query_vector is None:
            model = get_embed_model()
            if model == "gemini":
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                resp = genai.embed_content(
                    model="models/text-embedding-004",
                    content=query_text,
                    task_type="retrieval_query",
                    output_dimensionality=384
                )
                query_vector = resp["embedding"]
            else:
                query_vector = model.encode(query_text).tolist()
            
            # Lưu lại vào Cache
            redis_service.set_embedding(query_text, query_vector)
        
        # 2. Tìm kiếm trong Qdrant Cloud
        qdrant_service = QdrantService()
        chunks = qdrant_service.search_legal_documents(
            query_vector=query_vector,
            limit=5,
            score_threshold=0.35
        )
        
        logging.info(f"Qdrant tìm thấy {len(chunks)} đoạn văn bản phù hợp.")
        return {"context_chunks": chunks}
    except Exception as e:
        logging.error(f"Lỗi xảy ra tại Retrieval Node: {str(e)}", exc_info=True)
        return {"context_chunks": []}
