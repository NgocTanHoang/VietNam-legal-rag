import json
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents.legal_agent import LegalAgent
from app.api.dependencies import get_graph_service, get_legal_agent
from app.services.graph_service import GraphService
from app.services.llm_service import LLMService

router = APIRouter()
DEFENSIVE_NO_EVIDENCE_MESSAGE = (
    "Hệ thống chưa tìm thấy đủ căn cứ pháp lý xác thực trong kho tri thức hiện tại để đưa ra nhận định."
)


class ChatRequest(BaseModel):
    query: str = Field(..., description="Câu hỏi pháp lý cần giải đáp")
    history: Optional[List[Dict[str, Any]]] = Field(default=[])


class ChatResponse(BaseModel):
    query: str
    answer: str
    query_rewritten: Optional[str] = None
    chunks_count: int
    graph_relations_count: int
    graph_context: Optional[List[Dict[str, Any]]] = None


class ContractReviewRequest(BaseModel):
    contract_text: str = Field(..., description="Nội dung điều khoản hợp đồng cần rà soát")


class ContractReviewResponse(BaseModel):
    score: int
    risks: List[Dict[str, Any]]
    full_analysis: str


class DraftItem(BaseModel):
    id: str
    title: str
    ministry: str
    status: str
    date: str
    deadline: str
    impact: str
    progress: int
    url: Optional[str] = None
    snippet: Optional[str] = None


class DraftAnalyzeRequest(BaseModel):
    draft_id: str
    title: Optional[str] = None


class DraftComparisonItem(BaseModel):
    clause: str
    old_content: str
    new_content: str
    reason: str


class DraftImpactedGroup(BaseModel):
    group: str
    impact: str


class DraftAnalyzeResponse(BaseModel):
    draft_id: str
    summary: str
    comparison: List[DraftComparisonItem]
    impacted_groups: List[DraftImpactedGroup]


MOCK_DRAFTS = [
    {
        "id": "draft-1",
        "title": "Dự thảo Luật Đất đai (sửa đổi) - Quy định bồi thường và tái định cư",
        "ministry": "Bộ Tài nguyên và Môi trường",
        "status": "PUBLIC_CONSULTATION",
        "date": "Tháng 09/2026",
        "deadline": "30/10/2026",
        "impact": "RẤT CAO",
        "progress": 45,
    },
    {
        "id": "draft-2",
        "title": "Dự thảo Luật Giao dịch điện tử - Chữ ký số và hợp đồng điện tử",
        "ministry": "Bộ Thông tin và Truyền thông",
        "status": "PUBLIC_CONSULTATION",
        "date": "Tháng 08/2026",
        "deadline": "15/10/2026",
        "impact": "TRUNG BÌNH",
        "progress": 75,
    },
    {
        "id": "draft-3",
        "title": "Dự thảo Nghị định hướng dẫn Luật Nhà ở - Phát triển Nhà ở xã hội",
        "ministry": "Bộ Xây dựng",
        "status": "DRAFTING",
        "date": "Tháng 11/2026",
        "deadline": "25/12/2026",
        "impact": "CAO",
        "progress": 20,
    },
    {
        "id": "draft-4",
        "title": "Dự thảo Thông tư hướng dẫn Bảo dữ liệu cá nhân trong Ngành Tài chính",
        "ministry": "Ngân hàng Nhà nước Việt Nam",
        "status": "PUBLIC_CONSULTATION",
        "date": "Tháng 10/2026",
        "deadline": "05/11/2026",
        "impact": "CAO",
        "progress": 35,
    },
]


def _defensive_contract_response() -> ContractReviewResponse:
    return ContractReviewResponse(
        score=0,
        risks=[
            {
                "issue": DEFENSIVE_NO_EVIDENCE_MESSAGE,
                "severity": "medium",
                "advice": "Hãy bổ sung kho tri thức xác thực hoặc cấu hình provider LLM trước khi dùng tính năng rà soát hợp đồng.",
            }
        ],
        full_analysis=DEFENSIVE_NO_EVIDENCE_MESSAGE,
    )


@router.get("/health", summary="Kiểm tra trạng thái hệ thống")
async def health_check(graph_service: GraphService = Depends(get_graph_service)):
    from app.services.qdrant_service import QdrantService
    from app.services.redis_service import RedisService

    redis_service = RedisService()
    qdrant_service = QdrantService()

    redis_healthy = redis_service.is_active()
    neo4j_healthy = graph_service.is_healthy()
    qdrant_healthy = qdrant_service.is_healthy()

    return {
        "status": "healthy" if all([redis_healthy, neo4j_healthy, qdrant_healthy]) else "degraded",
        "services": {
            "redis": "connected" if redis_healthy else "offline",
            "neo4j": "connected" if neo4j_healthy else "offline",
            "qdrant": "connected" if qdrant_healthy else "offline",
        },
    }


@router.post("/chat", response_model=ChatResponse, summary="Hỏi đáp Luật sư AI")
async def chat_direct(request: ChatRequest, agent: LegalAgent = Depends(get_legal_agent)):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Nội dung câu hỏi không được để trống.")

    query_lower = request.query.lower()
    attack_keywords = ["system prompt", "ignore instructions", "dan_chu_cuoi", "override"]
    if any(keyword in query_lower for keyword in attack_keywords):
        return ChatResponse(
            query=request.query,
            answer="Phát hiện yêu cầu không hợp lệ. Hệ thống từ chối xử lý câu lệnh thao túng hệ thống.",
            query_rewritten=None,
            chunks_count=0,
            graph_relations_count=0,
            graph_context=[],
        )

    try:
        from app.services.redis_service import RedisService

        redis_service = RedisService()
        cached_res = redis_service.get_chat_response(request.query)
        if cached_res:
            return ChatResponse(**cached_res)

        lock_acquired = redis_service.acquire_query_lock(request.query)
        if not lock_acquired:
            waited_result = redis_service.wait_for_cached_result(request.query, max_wait_seconds=30)
            if waited_result:
                return ChatResponse(**waited_result)
            redis_service.acquire_query_lock(request.query)

        try:
            result = agent.run(request.query)
            graph_relations_count = 0
            for item in result.get("graph_context", []):
                graph_relations_count += len(item.get("thong_tin_thay_the", []))
                graph_relations_count += len(item.get("van_ban_huong_dan", []))
                graph_relations_count += len(item.get("quan_he_lien_quan", []))

            response_data = {
                "query": request.query,
                "answer": result.get("answer", DEFENSIVE_NO_EVIDENCE_MESSAGE),
                "query_rewritten": result.get("query_rewritten"),
                "chunks_count": len(result.get("context_chunks", [])),
                "graph_relations_count": graph_relations_count,
                "graph_context": result.get("graph_context", []),
            }
            redis_service.set_chat_response(request.query, response_data)
            return ChatResponse(**response_data)
        finally:
            redis_service.release_query_lock(request.query)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi thực thi Agent: {exc}")


@router.post("/review-contract", response_model=ContractReviewResponse, summary="Rà soát Hợp đồng AI")
async def review_contract_endpoint(request: ContractReviewRequest):
    if not request.contract_text.strip():
        raise HTTPException(status_code=400, detail="Nội dung hợp đồng không được để trống.")

    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "prompts",
        "contract_reviewer.txt",
    )
    system_prompt = "Bạn là chuyên gia rà soát hợp đồng AI."
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as file:
            system_prompt = file.read()

    llm_service = LLMService()
    if not llm_service.is_available():
        return _defensive_contract_response()

    try:
        response_text = llm_service.generate_response(
            [
                SystemMessage(content=system_prompt.format(contract_text=request.contract_text)),
                HumanMessage(content="Hãy tiến hành rà soát hợp đồng này và trả về định dạng JSON duy nhất."),
            ]
        )
        clean_json_str = response_text.strip()
        if clean_json_str.startswith("```json"):
            clean_json_str = clean_json_str[7:]
        if clean_json_str.endswith("```"):
            clean_json_str = clean_json_str[:-3]
        clean_json_str = clean_json_str.strip()
        try:
            return ContractReviewResponse(**json.loads(clean_json_str))
        except Exception:
            logging.error(f"Không thể parse JSON từ phản hồi contract reviewer: {response_text}")
            return _defensive_contract_response()
    except Exception as exc:
        logging.error(f"Lỗi hệ thống rà soát hợp đồng: {exc}")
        return _defensive_contract_response()


@router.get("/drafts", response_model=List[DraftItem], summary="Lấy danh sách dự thảo")
async def get_drafts():
    return MOCK_DRAFTS


@router.get("/drafts/search", response_model=List[DraftItem], summary="Tìm kiếm các dự thảo văn bản pháp luật chính thống")
async def search_drafts_endpoint(query: str):
    from app.services.draft_scraper_service import DraftScraperService

    scraper = DraftScraperService()
    results = await scraper.search_drafts(query)
    return results if results else MOCK_DRAFTS


@router.post("/drafts/analyze", response_model=DraftAnalyzeResponse, summary="Phân tích điểm mới của dự thảo bằng AI")
async def analyze_draft(request: DraftAnalyzeRequest):
    llm_service = LLMService()
    if not llm_service.is_available():
        return DraftAnalyzeResponse(
            draft_id=request.draft_id,
            summary=DEFENSIVE_NO_EVIDENCE_MESSAGE,
            comparison=[],
            impacted_groups=[],
        )

    draft = next((item for item in MOCK_DRAFTS if item["id"] == request.draft_id), None)
    draft_title = request.title or (draft["title"] if draft else request.draft_id)

    system_prompt = (
        "Bạn là chuyên gia phân tích lập pháp Việt Nam. "
        "Chỉ trả về JSON với các trường draft_id, summary, comparison, impacted_groups."
    )
    human_prompt = (
        f"Hãy phân tích dự thảo sau:\n"
        f"ID: {request.draft_id}\n"
        f"Tiêu đề: {draft_title}\n"
    )

    try:
        response_text = llm_service.generate_response(
            [SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)]
        )
        clean_json_str = response_text.strip()
        if clean_json_str.startswith("```json"):
            clean_json_str = clean_json_str[7:]
        if clean_json_str.endswith("```"):
            clean_json_str = clean_json_str[:-3]
        clean_json_str = clean_json_str.strip()
        payload = json.loads(clean_json_str)
        payload["draft_id"] = request.draft_id
        return DraftAnalyzeResponse(**payload)
    except Exception as exc:
        logging.error(f"Lỗi phân tích dự thảo: {exc}")
        return DraftAnalyzeResponse(
            draft_id=request.draft_id,
            summary=DEFENSIVE_NO_EVIDENCE_MESSAGE,
            comparison=[],
            impacted_groups=[],
        )
