import logging
import threading
from typing import List, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.exceptions import LLMTimeoutError

# --- SEMAPHORE TOÀN CỤC CHO KIỂM SOÁT SONG SONG LLM ---
# Giới hạn tối đa 3 cuộc gọi LLM API đồng thời để tránh lỗi 429 Rate Limit
# Các tác vụ vượt quá ngưỡng sẽ tự động xếp hàng đợi (blocking wait) trong bộ nhớ
_LLM_SEMAPHORE = threading.Semaphore(value=3)
_llm_active_count = 0
_llm_count_lock = threading.Lock()

def is_transient_error(exception: Exception) -> bool:
    """
    Trả về False nếu lỗi là lỗi vĩnh viễn (như 401 Unauthorized, 404 Not Found, 403 Forbidden),
    ngược lại trả về True để cho phép Tenacity retry.
    """
    err_str = str(exception).lower()
    if "401" in err_str or "unauthorized" in err_str:
        return False
    if "404" in err_str or "not found" in err_str:
        return False
    if "403" in err_str or "forbidden" in err_str:
        return False
    return True

class LLMService:
    def __init__(self):
        """Khởi tạo toàn bộ các LLM Providers có cấu hình để sẵn sàng fallback tại runtime"""
        self.providers = []
        
        # 1. Thử dùng Google Gemini chính chủ
        if settings.GEMINI_API_KEY:
            try:
                logging.info("Đăng ký ChatGoogleGenerativeAI làm provider...")
                gemini_llm = ChatGoogleGenerativeAI(
                    model="gemini-1.5-flash",
                    google_api_key=settings.GEMINI_API_KEY,
                    temperature=0.2,
                    max_tokens=1500
                )
                self.providers.append(("Gemini Direct", gemini_llm))
            except Exception as e:
                logging.warning(f"Lỗi cấu hình Gemini provider: {str(e)}")

        # 2. Thử dùng OpenRouter (Rất thích hợp cho R&D, hỗ trợ nhiều model Gemini/Claude/DeepSeek)
        if settings.OPENROUTER_API_KEY:
            try:
                logging.info("Đăng ký ChatOpenAI (OpenRouter) làm provider...")
                openrouter_llm = ChatOpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=settings.OPENROUTER_API_KEY,
                    model="google/gemini-2.5-flash", # Gọi model Gemini cực tốt qua OpenRouter
                    temperature=0.2,
                    max_tokens=1500
                )
                self.providers.append(("OpenRouter", openrouter_llm))
            except Exception as e:
                logging.warning(f"Lỗi cấu hình OpenRouter provider: {str(e)}")

        # 3. Thử dùng Nvidia API (Khai thác NVIDIA_API_KEY trong .env của bạn)
        if settings.NVIDIA_API_KEY:
            try:
                logging.info("Đăng ký ChatOpenAI (NVIDIA) làm provider...")
                nvidia_llm = ChatOpenAI(
                    base_url="https://integrate.api.nvidia.com/v1",
                    api_key=settings.NVIDIA_API_KEY,
                    model="meta/llama-3.1-70b-instruct", # Dùng model Llama-3.1 của Nvidia
                    temperature=0.2,
                    max_tokens=1500
                )
                self.providers.append(("Nvidia API", nvidia_llm))
            except Exception as e:
                logging.warning(f"Lỗi cấu hình Nvidia provider: {str(e)}")

        if not self.providers:
            logging.error("Không tìm thấy bất kỳ API Key hợp lệ nào (.env thiếu GEMINI_API_KEY, OPENROUTER_API_KEY, NVIDIA_API_KEY)")
            raise ValueError("Cần cung cấp API Key hợp lệ để khởi chạy hệ thống Legal RAG.")

    # Tự động Retry nếu tất cả các providers cùng thất bại (chỉ retry đối với lỗi tạm thời)
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=3),
        retry=retry_if_exception(is_transient_error),
        reraise=True
    )
    def invoke_with_retry(self, messages: List[BaseMessage]) -> BaseMessage:
        """
        Thực thi gọi LLM kèm cơ chế:
        1. Semaphore kiểm soát song song (tối đa 3 cuộc gọi đồng thời)
        2. Tự động chuyển sang Provider dự phòng nếu lỗi xảy ra
        """
        global _llm_active_count
        
        # Ghi nhận số tác vụ đang chờ trước khi acquire
        with _llm_count_lock:
            waiting_count = max(0, _llm_active_count - 3)
        if waiting_count > 0:
            logging.info(f"⏳ [SEMAPHORE] Có {waiting_count} tác vụ LLM đang xếp hàng đợi. Đang chờ slot trống...")
        
        # Acquire semaphore - block nếu đã đạt giới hạn 3 cuộc gọi đồng thời
        _LLM_SEMAPHORE.acquire()
        with _llm_count_lock:
            _llm_active_count += 1
            current_active = _llm_active_count
        logging.info(f"🔄 [SEMAPHORE] Đã nhận slot LLM ({current_active}/3 đang hoạt động)")
        
        try:
            last_error = None
            for name, llm in self.providers:
                try:
                    logging.info(f"Đang thực thi gọi LLM qua Provider: {name}...")
                    response = llm.invoke(messages)
                    logging.info(f"Gọi LLM qua {name} thành công!")
                    return response
                except Exception as e:
                    logging.error(f"Lỗi gọi LLM qua {name}: {str(e)}. Thử chuyển sang Provider dự phòng tiếp theo...")
                    last_error = e
                    continue
                    
            if last_error:
                raise last_error
            raise ValueError("Không có LLM provider nào khả dụng.")
        finally:
            # LUÔN giải phóng semaphore slot dù thành công hay thất bại
            _LLM_SEMAPHORE.release()
            with _llm_count_lock:
                _llm_active_count -= 1
                current_active = _llm_active_count
            logging.info(f"✅ [SEMAPHORE] Đã giải phóng slot LLM ({current_active}/3 còn hoạt động)")

    def generate_response(self, messages: List[BaseMessage]) -> str:
        """Hàm bọc tiện ích, trả về chuỗi văn bản thuần túy"""
        try:
            response = self.invoke_with_retry(messages)
            return response.content
        except Exception as e:
            logging.critical(f"LLM hoàn toàn thất bại sau các lần thử: {str(e)}")
            raise LLMTimeoutError(f"Cổng kết nối AI (LLM) gặp sự cố kéo dài. Lỗi: {str(e)}")
