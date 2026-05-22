import logging
from typing import List, Dict, Any, Optional
from langchain_core.messages import HumanMessage, BaseMessage
from langgraph.graph import StateGraph, END

from app.agents.state import AgentState
from app.agents.nodes.retrieval_node import retrieval_node
from app.agents.nodes.graph_node import graph_node
from app.agents.nodes.generator_node import generator_node
from app.agents.edges import query_rewriter_node, route_after_retrieval

class LegalAgent:
    def __init__(self):
        """Khởi tạo đồ thị LangGraph điều phối AI Agent Luật Sư"""
        # 1. Định nghĩa Đồ thị trạng thái StateGraph
        workflow = StateGraph(AgentState)
        
        # 2. Khai báo các bước xử lý (Nodes)
        workflow.add_node("qdrant_retriever", retrieval_node)
        workflow.add_node("query_rewriter", query_rewriter_node)
        workflow.add_node("neo4j_analyst", graph_node)
        workflow.add_node("response_generator", generator_node)
        
        # 3. Cấu hình luồng đi (Edges)
        # Bắt đầu tại bước truy vấn Vector Qdrant
        workflow.set_entry_point("qdrant_retriever")
        
        # Rẽ nhánh điều kiện sau khi truy vấn Vector xong
        workflow.add_conditional_edges(
            "qdrant_retriever",
            route_after_retrieval,
            {
                "rewrite_query": "query_rewriter",
                "continue_to_graph": "neo4j_analyst"
            }
        )
        
        # Sau khi viết lại câu truy vấn, tự động quay lại bước truy vấn Vector lần 2
        workflow.add_edge("query_rewriter", "qdrant_retriever")
        
        # Từ phân tích đồ thị Neo4j chuyển sang bước sinh câu trả lời bằng LLM
        workflow.add_edge("neo4j_analyst", "response_generator")
        
        # Sinh câu trả lời xong là kết thúc chu trình
        workflow.add_edge("response_generator", END)
        
        # 4. Biên dịch (Compile) đồ thị thành ứng dụng hoàn chỉnh
        self.app = workflow.compile()
        logging.info("Biên dịch Đồ thị LangGraph Agent Luật Sư thành công!")

    def run(self, query: str, history: Optional[List[BaseMessage]] = None) -> Dict[str, Any]:
        """
        Thực thi đồ thị Agent đồng bộ.
        """
        history_messages = history or []
        # Tin nhắn mới của người dùng
        new_message = HumanMessage(content=query)
        
        inputs = {
            "messages": history_messages + [new_message],
            "raw_query": query,
            "query_rewritten": "",
            "context_chunks": [],
            "graph_context": [],
            "answer": "",
            "retry_count": 0
        }
        
        logging.info(f"--- Bắt đầu thực thi Agent cho câu hỏi: '{query}' ---")
        output = self.app.invoke(inputs)
        logging.info("--- Hoàn thành thực thi Agent ---")
        return output
