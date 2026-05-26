import logging
import os
from typing import Any, Dict, Literal

from langchain_core.messages import HumanMessage

from app.agents.state import AgentState
from app.services.llm_service import LLMService


def query_rewriter_node(state: AgentState) -> Dict[str, Any]:
    raw_query = state.get("raw_query") or ""
    if not raw_query and state.get("messages"):
        raw_query = state["messages"][-1].content

    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "prompts",
        "query_rewrite.txt",
    )
    rewrite_prompt = "Hãy rút trích các từ khóa pháp lý chính từ câu hỏi sau: {user_query}"
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as file:
            rewrite_prompt = file.read()

    llm_service = LLMService()
    if not llm_service.is_available():
        logging.warning("LLM chưa sẵn sàng cho query rewrite. Giữ nguyên câu hỏi gốc.")
        return {
            "query_rewritten": raw_query,
            "retry_count": state.get("retry_count", 0) + 1,
        }

    try:
        prompt_formatted = rewrite_prompt.format(user_query=raw_query)
        rewritten_text = llm_service.generate_response([HumanMessage(content=prompt_formatted)])
        return {
            "query_rewritten": rewritten_text.strip().replace('"', "").replace("'", ""),
            "retry_count": state.get("retry_count", 0) + 1,
        }
    except Exception as exc:
        logging.error(f"Lỗi khi viết lại câu hỏi: {exc}")
        return {
            "query_rewritten": raw_query,
            "retry_count": state.get("retry_count", 0) + 1,
        }


def route_after_retrieval(state: AgentState) -> Literal["rewrite_query", "continue_to_graph"]:
    chunks = state.get("context_chunks", [])
    retry_count = state.get("retry_count", 0)

    if not chunks and retry_count < 1:
        logging.info("Retrieval rỗng. Chuyển sang query rewrite.")
        return "rewrite_query"

    return "continue_to_graph"
