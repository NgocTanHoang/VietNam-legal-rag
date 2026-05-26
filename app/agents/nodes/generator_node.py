import logging
import os
from typing import Any, Dict

from langchain_core.messages import AIMessage, SystemMessage

from app.agents.state import AgentState
from app.services.llm_service import LLMService

DEFENSIVE_NO_EVIDENCE_MESSAGE = (
    "Hệ thống chưa tìm thấy đủ căn cứ pháp lý xác thực trong kho tri thức hiện tại để đưa ra nhận định."
)


def generator_node(state: AgentState) -> Dict[str, Any]:
    logging.info("--- Generator Node: tổng hợp câu trả lời ---")

    context_chunks = state.get("context_chunks", [])
    if not context_chunks:
        return {
            "answer": DEFENSIVE_NO_EVIDENCE_MESSAGE,
            "messages": [AIMessage(content=DEFENSIVE_NO_EVIDENCE_MESSAGE)],
        }

    vector_context = []
    for idx, chunk in enumerate(context_chunks, start=1):
        vector_context.append(
            "\n".join(
                [
                    f"[{idx}] Văn bản: {chunk.get('title')}",
                    f"Số hiệu: {chunk.get('so_ky_hieu') or 'Chưa cập nhật'}",
                    f"Trạng thái hiệu lực: {chunk.get('tinh_trang_hieu_luc') or 'Không rõ'}",
                    f"Nội dung điều luật: {chunk.get('content') or ''}",
                ]
            )
        )

    graph_context = state.get("graph_context", [])
    graph_context_lines = []
    if graph_context:
        for group in graph_context:
            graph_context_lines.append(
                "\n".join(
                    [
                        f"- Văn bản gốc ID {group.get('goc_doc_id')} | Số hiệu: {group.get('goc_so_hieu')}",
                        f"  Trạng thái hiệu lực: {group.get('goc_tinh_trang_hieu_luc')}",
                        f"  Số văn bản thay thế/sửa đổi: {len(group.get('thong_tin_thay_the', []))}",
                        f"  Số văn bản hướng dẫn: {len(group.get('van_ban_huong_dan', []))}",
                        f"  Số quan hệ liên quan: {len(group.get('quan_he_lien_quan', []))}",
                    ]
                )
            )
    else:
        graph_context_lines.append("Không có dữ liệu quan hệ đồ thị bổ sung.")

    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "prompts",
        "system_prompt.txt",
    )
    system_prompt = "Bạn là trợ lý luật sư AI chuyên nghiệp. Hãy trả lời câu hỏi dựa trên tài liệu pháp lý."
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as file:
            system_prompt = file.read()

    llm_service = LLMService()
    if not llm_service.is_available():
        logging.warning("LLM chưa sẵn sàng. Trả về thông điệp phòng thủ.")
        return {
            "answer": DEFENSIVE_NO_EVIDENCE_MESSAGE,
            "messages": [AIMessage(content=DEFENSIVE_NO_EVIDENCE_MESSAGE)],
        }

    try:
        formatted_prompt = system_prompt.format(
            vector_context="\n\n".join(vector_context),
            graph_context="\n".join(graph_context_lines),
        )
        response_text = llm_service.generate_response(
            [SystemMessage(content=formatted_prompt)] + state.get("messages", [])
        )
        return {
            "answer": response_text,
            "messages": [AIMessage(content=response_text)],
        }
    except Exception as exc:
        logging.error(f"Lỗi generator node: {exc}", exc_info=True)
        return {
            "answer": DEFENSIVE_NO_EVIDENCE_MESSAGE,
            "messages": [AIMessage(content=DEFENSIVE_NO_EVIDENCE_MESSAGE)],
        }
