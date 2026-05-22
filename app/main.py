import sys
import types
try:
    import langchain_core.pydantic_v1
except ModuleNotFoundError:
    import pydantic.v1 as v1
    pydantic_v1 = types.ModuleType("langchain_core.pydantic_v1")
    for name in dir(v1):
        setattr(pydantic_v1, name, getattr(v1, name))
    sys.modules["langchain_core.pydantic_v1"] = pydantic_v1

import torch # Force load PyTorch DLL in clean main thread to avoid WinError 1114
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.api.v1.endpoints import router as endpoints_router
from app.api.v1.lark_webhook import router as lark_router

# 1. Cấu hình logger hệ thống chuyên nghiệp
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
)

# 2. Khởi tạo FastAPI App kèm thông tin SEO
app = FastAPI(
    title="Vietnamese Legal GraphRAG API",
    description="Hệ thống tra cứu và hỏi đáp Pháp luật Việt Nam sử dụng mô hình kết hợp Vector Database (Qdrant) và Graph Database (Neo4j) điều phối bởi LangGraph.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redocs"
)

# 3. Cấu hình CORS Middleware hỗ trợ kết nối frontend linh hoạt
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Có thể giới hạn domain cụ thể khi lên production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Đăng ký các bộ xử lý lỗi tập trung (Exceptions Handler)
register_exception_handlers(app)

# 5. Khai báo và ánh xạ các API Routers
# /api/v1/chat, /api/v1/health
app.include_router(endpoints_router, prefix="/api/v1", tags=["Direct Legal Chat"])
# /api/v1/lark/webhook
app.include_router(lark_router, prefix="/api/v1/lark", tags=["Lark Suite Webhook"])
# Fallback hỗ trợ truy cập trực tiếp qua /webhook (không cần prefix /api/v1/lark)
app.include_router(lark_router, prefix="", tags=["Lark Suite Webhook Root"])

@app.get("/", tags=["Root"])
async def root_endpoint():
    """Trang chào mừng API"""
    return {
        "message": "Chào mừng bạn đến với Hệ thống Luật sư AI Việt Nam (Legal GraphRAG)!",
        "documentation": "/docs",
        "health_check": "/api/v1/health"
    }

if __name__ == "__main__":
    # Cho phép chạy file trực tiếp bằng python app/main.py
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
