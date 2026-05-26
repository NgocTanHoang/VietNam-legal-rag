import logging
import sys
import types

import torch
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    import langchain_core.pydantic_v1
except ModuleNotFoundError:
    import pydantic.v1 as v1

    pydantic_v1 = types.ModuleType("langchain_core.pydantic_v1")
    for name in dir(v1):
        setattr(pydantic_v1, name, getattr(v1, name))
    sys.modules["langchain_core.pydantic_v1"] = pydantic_v1

from app.api.v1.endpoints import router as endpoints_router
from app.api.v1.lark_webhook import router as lark_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
)

app = FastAPI(
    title="Vietnamese Legal GraphRAG API",
    description="Hệ thống tra cứu và hỏi đáp pháp luật Việt Nam sử dụng Vector DB và Graph DB.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redocs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(endpoints_router, prefix="/api/v1", tags=["Direct Legal Chat"])
app.include_router(lark_router, prefix="/api/v1/lark", tags=["Lark Suite Webhook"])
app.include_router(lark_router, prefix="", tags=["Lark Suite Webhook Root"])


@app.get("/", tags=["Root"])
async def root_endpoint():
    return {
        "message": "Chào mừng bạn đến với Hệ thống Luật sư AI Việt Nam (Legal GraphRAG)!",
        "documentation": "/docs",
        "health_check": "/api/v1/health",
    }


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=True)
