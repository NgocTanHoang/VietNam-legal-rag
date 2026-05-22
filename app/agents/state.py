import operator
from typing import Annotated, List, Dict, Any, TypedDict
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    # Sử dụng Annotated[..., operator.add] giúp lưu trữ lịch sử hội thoại (messages mới tự động được append)
    messages: Annotated[List[BaseMessage], operator.add]
    
    # Câu hỏi gốc của người dùng
    raw_query: str
    
    # Câu hỏi sau khi đã được tối ưu từ khóa pháp lý thông qua LLM
    query_rewritten: str
    
    # Các đoạn văn bản luật tìm được từ Qdrant Cloud
    context_chunks: List[Dict[str, Any]]
    
    # Các mối quan hệ đồ thị pháp lý tìm được từ Neo4j (Văn bản HD chi tiết, Thay thế, Căn cứ)
    graph_context: List[Dict[str, Any]]
    
    # Câu trả lời tổng hợp cuối cùng
    answer: str
    
    # Số lần thử viết lại câu hỏi nếu kết quả vector search rỗng
    retry_count: int
