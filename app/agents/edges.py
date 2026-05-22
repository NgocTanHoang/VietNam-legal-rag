import os
import logging
from typing import Dict, Any, Literal
from langchain_core.messages import HumanMessage
from app.services.llm_service import LLMService
from app.agents.state import AgentState

def query_rewriter_node(state: AgentState) -> Dict[str, Any]:
    """
    Node tối ưu từ khóa pháp lý (Query Rewrite).
    Được gọi khi truy vấn vector database không mang lại kết quả chất lượng cao.
    """
    raw_query = state.get("raw_query") or ""
    if not raw_query and state.get("messages"):
        raw_query = state["messages"][-1].content
        
    logging.info(f"--- Edges LangGraph: Đang kích hoạt viết lại câu hỏi cho '{raw_query}' ---")
    
    # Đọc Prompt tối ưu câu hỏi từ file prompts/query_rewrite.txt
    prompt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "prompts", "query_rewrite.txt")
    rewrite_prompt = "Hãy rút trích các từ khóa pháp lý chính từ câu hỏi sau: {user_query}"
    
    if os.path.exists(prompt_path):
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                rewrite_prompt = f.read()
        except Exception as e:
            logging.error(f"Lỗi khi đọc file query_rewrite.txt: {str(e)}")
            
    prompt_formatted = rewrite_prompt.format(user_query=raw_query)
    
    try:
        llm_service = LLMService()
        messages = [HumanMessage(content=prompt_formatted)]
        rewritten_text = llm_service.generate_response(messages)
        # Loại bỏ các ký tự dấu ngoặc kép dư thừa nếu LLM sinh ra
        rewritten_text = rewritten_text.strip().replace('"', '').replace("'", "")
        
        logging.info(f"Câu hỏi sau khi viết lại: '{rewritten_text}'")
        
        return {
            "query_rewritten": rewritten_text,
            "retry_count": state.get("retry_count", 0) + 1
        }
    except Exception as e:
        logging.error(f"Lỗi khi viết lại câu hỏi: {str(e)}")
        # Fallback dùng câu hỏi gốc
        return {
            "query_rewritten": raw_query,
            "retry_count": state.get("retry_count", 0) + 1
        }

def route_after_retrieval(state: AgentState) -> Literal["rewrite_query", "continue_to_graph"]:
    """
    Logic rẽ nhánh (Conditional Edge).
    Nếu tìm kiếm Vector trả về kết quả rỗng VÀ chưa từng thử viết lại câu hỏi,
    hệ thống sẽ rẽ nhánh sang bước viết lại câu hỏi (query_rewriter_node).
    Ngược lại, tiếp tục sang tra cứu Graph Neo4j.
    """
    chunks = state.get("context_chunks", [])
    retry_count = state.get("retry_count", 0)
    
    if not chunks and retry_count < 1:
        logging.info("=> Rẽ nhánh edge: Qdrant rỗng. Rẽ nhánh sang 'rewrite_query' để cải thiện từ khóa.")
        return "rewrite_query"
        
    logging.info("=> Rẽ nhánh edge: Đã có ngữ cảnh hoặc đạt giới hạn viết lại. Rẽ nhánh sang 'continue_to_graph'.")
    return "continue_to_graph"
