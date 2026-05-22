import os
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Qdrant Config
    QDRANT_HOST: Optional[str] = None
    QDRANT_PORT: Optional[int] = 6333
    QDRANT_URL: Optional[str] = None
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION: str = "legal_documents_v2"
    
    # Neo4j Config
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    
    # Redis Config
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    
    # LLM API Keys
    GEMINI_API_KEY: Optional[str] = None
    NVIDIA_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    
    # Scraper & API Keys
    TAVILY_API_KEY: Optional[str] = None
    JINA_READER_ENDPOINT: str = "https://r.jina.ai/"
    
    # Default model parameters
    EMBED_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    
    # Lark Suite Settings
    LARK_APP_ID: str = ""
    LARK_APP_SECRET: str = ""
    LARK_ENCRYPT_KEY: str = ""
    LARK_VERIFICATION_TOKEN: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def qdrant_connection_url(self) -> str:
        """Assembles the final Qdrant URL based on host/port or direct URL"""
        if self.QDRANT_URL:
            return self.QDRANT_URL
        if self.QDRANT_HOST:
            # Check if host already includes port or scheme
            if ":" in self.QDRANT_HOST.replace("http://", "").replace("https://", ""):
                return self.QDRANT_HOST
            return f"{self.QDRANT_HOST}:{self.QDRANT_PORT}"
        return "http://localhost:6333"

settings = Settings()