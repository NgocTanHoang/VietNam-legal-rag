from functools import lru_cache

from app.agents.legal_agent import LegalAgent
from app.services.graph_service import GraphService
from app.services.lark_service import LarkService
from app.services.llm_service import LLMService
from app.services.qdrant_service import QdrantService


def get_qdrant_service() -> QdrantService:
    return _get_qdrant_service()


def get_graph_service() -> GraphService:
    return _get_graph_service()


def get_llm_service() -> LLMService:
    return _get_llm_service()


def get_lark_service() -> LarkService:
    return _get_lark_service()


def get_legal_agent() -> LegalAgent:
    return _get_legal_agent()


@lru_cache(maxsize=1)
def _get_qdrant_service() -> QdrantService:
    return QdrantService()


@lru_cache(maxsize=1)
def _get_graph_service() -> GraphService:
    return GraphService()


@lru_cache(maxsize=1)
def _get_llm_service() -> LLMService:
    return LLMService()


@lru_cache(maxsize=1)
def _get_lark_service() -> LarkService:
    return LarkService()


@lru_cache(maxsize=1)
def _get_legal_agent() -> LegalAgent:
    return LegalAgent()
