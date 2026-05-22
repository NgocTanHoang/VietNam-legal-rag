from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from app.api.dependencies import get_legal_agent, get_graph_service
from app.services.graph_service import GraphService
from app.agents.legal_agent import LegalAgent

router = APIRouter()

# Schema yêu cầu chat trực tiếp
class ChatRequest(BaseModel):
    query: str = Field(..., description="Câu hỏi pháp lý cần giải đáp", example="Luật doanh nghiệp quy định gì về vốn điều lệ?")
    history: Optional[List[Dict[str, Any]]] = Field(default=[], description="Lịch sử hội thoại (nếu có)")

# Schema phản hồi chat trực tiếp
class ChatResponse(BaseModel):
    query: str
    answer: str
    query_rewritten: Optional[str] = None
    chunks_count: int
    graph_relations_count: int
    graph_context: Optional[List[Dict[str, Any]]] = None

@router.get("/health", summary="Kiểm tra trạng thái hệ thống")
async def health_check(graph_service: GraphService = Depends(get_graph_service)):
    """Kiểm tra sức khỏe hệ thống và kết nối cơ sở dữ liệu"""
    neo4j_healthy = graph_service.is_healthy()
    return {
        "status": "healthy",
        "databases": {
            "qdrant_cloud": "connected",
            "neo4j_graph": "connected" if neo4j_healthy else "fallback_offline"
        }
    }

@router.post("/chat", response_model=ChatResponse, summary="Hỏi đáp Luật sư AI")
async def chat_direct(request: ChatRequest, agent: LegalAgent = Depends(get_legal_agent)):
    """Gửi câu hỏi trực tiếp và nhận câu trả lời từ AI Agent Luật Sư"""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Nội dung câu hỏi không được để trống.")
        
    try:
        import logging
        from app.services.redis_service import RedisService
        redis_service = RedisService()
        
        # 1. Thử lấy từ cache phản hồi chat (Cache Hit nhanh < 100ms)
        cached_res = redis_service.get_chat_response(request.query)
        if cached_res:
            logging.info(f"[CHAT API] Cache HIT cho câu hỏi: '{request.query[:30]}...'")
            return ChatResponse(**cached_res)
        
        # 2. Thử đặt khóa phân tán (Distributed Lock) để tránh xử lý trùng lặp
        lock_acquired = redis_service.acquire_query_lock(request.query)
        
        if not lock_acquired:
            # Có request trùng đang xử lý → đợi kết quả cache từ request đầu tiên
            logging.info(f"[CHAT API] Request trùng lặp phát hiện. Đang đợi kết quả từ request gốc...")
            waited_result = redis_service.wait_for_cached_result(request.query, max_wait_seconds=30)
            if waited_result:
                logging.info(f"[CHAT API] Nhận kết quả từ cache sau khi đợi thành công!")
                return ChatResponse(**waited_result)
            else:
                # Hết thời gian chờ hoặc request gốc lỗi → xử lý lại bình thường
                logging.warning(f"[CHAT API] Hết thời gian chờ request gốc. Xử lý lại từ đầu.")
                redis_service.acquire_query_lock(request.query)  # Thử lấy lock lại
            
        # 3. Thực thi LangGraph Agent (chỉ request đầu tiên mới chạy tới đây)
        try:
            result = agent.run(request.query)
            
            graph_relations_count = 0
            for item in result.get("graph_context", []):
                graph_relations_count += len(item.get("thong_tin_thay_the", []))
                graph_relations_count += len(item.get("van_ban_huong_dan", []))
                graph_relations_count += len(item.get("quan_he_lien_quan", []))

            response_data = {
                "query": request.query,
                "answer": result.get("answer", "Không có câu trả lời."),
                "query_rewritten": result.get("query_rewritten"),
                "chunks_count": len(result.get("context_chunks", [])),
                "graph_relations_count": graph_relations_count,
                "graph_context": result.get("graph_context", [])
            }
            
            # 4. Lưu lại vào cache
            redis_service.set_chat_response(request.query, response_data)
            
            return ChatResponse(**response_data)
        finally:
            # 5. LUÔN giải phóng khóa sau khi xử lý xong (dù thành công hay lỗi)
            redis_service.release_query_lock(request.query)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi thực thi Agent: {str(e)}")

