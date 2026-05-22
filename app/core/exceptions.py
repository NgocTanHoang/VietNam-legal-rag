from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import logging

class LegalRAGException(Exception):
    """Base exception class for all Vietnamese Legal RAG errors"""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class LLMTimeoutError(LegalRAGException):
    """Raised when the LLM service fails to respond or times out"""
    def __init__(self, message: str = "Cổng kết nối AI (LLM) bị quá tải hoặc phản hồi chậm. Vui lòng thử lại sau."):
        super().__init__(message, status_code=504)

class DatabaseCrashError(LegalRAGException):
    """Raised when Qdrant Cloud or Neo4j databases fail to connect or query"""
    def __init__(self, db_name: str, details: str = ""):
        super().__init__(
            message=f"Lỗi kết nối Cơ sở dữ liệu ({db_name}). Hệ thống đang tự động khôi phục. Chi tiết: {details}",
            status_code=503
        )

class LarkSignatureVerificationError(LegalRAGException):
    """Raised when a signature from Lark Suite is invalid"""
    def __init__(self, message: str = "Xác thực chữ ký Lark Suite thất bại. Giao dịch không được phép."):
        super().__init__(message, status_code=401)

def register_exception_handlers(app: FastAPI):
    """Registers standard handlers for FastAPI to catch Legal RAG Exceptions gracefully"""
    @app.exception_handler(LegalRAGException)
    async def legal_rag_exception_handler(request: Request, exc: LegalRAGException):
        logging.error(f"Legal RAG Error on {request.url.path}: {exc.message}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "type": exc.__class__.__name__,
                    "message": exc.message
                }
            }
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logging.error(f"Unhandled Global Error on {request.url.path}: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "type": "InternalServerError",
                    "message": "Đã xảy ra lỗi hệ thống nghiêm trọng. Vui lòng liên hệ quản trị viên."
                }
            }
        )
