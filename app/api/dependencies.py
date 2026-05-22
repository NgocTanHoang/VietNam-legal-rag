from app.services.qdrant_service import QdrantService
from app.services.graph_service import GraphService
from app.services.llm_service import LLMService
from app.services.lark_service import LarkService
from app.agents.legal_agent import LegalAgent

# Khởi tạo singletons để tái sử dụng connection pools
_qdrant_service = QdrantService()
_graph_service = GraphService()
_llm_service = LLMService()
_lark_service = LarkService()
_legal_agent = LegalAgent()

def get_qdrant_service() -> QdrantService:
    return _qdrant_service

def get_graph_service() -> GraphService:
    return _graph_service

def get_llm_service() -> LLMService:
    return _llm_service

def get_lark_service() -> LarkService:
    return _lark_service

def get_legal_agent() -> LegalAgent:
    return _legal_agent
