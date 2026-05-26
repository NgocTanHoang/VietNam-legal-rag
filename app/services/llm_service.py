import logging
import threading
from typing import List

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.exceptions import LLMTimeoutError

_LLM_SEMAPHORE = threading.Semaphore(value=3)
_llm_active_count = 0
_llm_count_lock = threading.Lock()


def is_transient_error(exception: Exception) -> bool:
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
        self.providers = []
        preferred_provider = (settings.PREFERRED_LLM_PROVIDER or "auto").strip().lower()
        secondary_enabled = settings.ENABLE_SECONDARY_LLM_PROVIDERS

        def should_load(provider_name: str) -> bool:
            if preferred_provider in {"", "auto"}:
                return True
            if provider_name == preferred_provider:
                return True
            return secondary_enabled

        if settings.GEMINI_API_KEY and should_load("gemini"):
            try:
                gemini_llm = ChatGoogleGenerativeAI(
                    model=settings.GEMINI_MODEL,
                    google_api_key=settings.GEMINI_API_KEY,
                    temperature=0.2,
                    max_tokens=1500,
                    timeout=settings.LLM_TIMEOUT_SECONDS,
                )
                self.providers.append((f"Gemini Direct {settings.GEMINI_MODEL}", gemini_llm))
            except Exception as exc:
                logging.warning(f"Lỗi cấu hình Gemini provider: {exc}")

        if settings.OPENROUTER_API_KEY and should_load("openrouter"):
            try:
                openrouter_llm = ChatOpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=settings.OPENROUTER_API_KEY,
                    model=settings.OPENROUTER_MODEL,
                    temperature=0.2,
                    max_tokens=1500,
                    timeout=settings.LLM_TIMEOUT_SECONDS,
                )
                self.providers.append((f"OpenRouter {settings.OPENROUTER_MODEL}", openrouter_llm))

                if settings.OPENROUTER_FALLBACK_MODEL and settings.OPENROUTER_FALLBACK_MODEL != settings.OPENROUTER_MODEL:
                    openrouter_fallback_llm = ChatOpenAI(
                        base_url="https://openrouter.ai/api/v1",
                        api_key=settings.OPENROUTER_API_KEY,
                        model=settings.OPENROUTER_FALLBACK_MODEL,
                        temperature=0.2,
                        max_tokens=1500,
                        timeout=settings.LLM_TIMEOUT_SECONDS,
                    )
                    self.providers.append(
                        (f"OpenRouter {settings.OPENROUTER_FALLBACK_MODEL}", openrouter_fallback_llm)
                    )
            except Exception as exc:
                logging.warning(f"Lỗi cấu hình OpenRouter provider: {exc}")

        if settings.NVIDIA_API_KEY and should_load("nvidia"):
            try:
                nvidia_llm = ChatOpenAI(
                    base_url="https://integrate.api.nvidia.com/v1",
                    api_key=settings.NVIDIA_API_KEY,
                    model=settings.NVIDIA_MODEL,
                    temperature=0.2,
                    max_tokens=1500,
                    timeout=settings.LLM_TIMEOUT_SECONDS,
                )
                self.providers.append((f"NVIDIA {settings.NVIDIA_MODEL}", nvidia_llm))
            except Exception as exc:
                logging.warning(f"Lỗi cấu hình NVIDIA provider: {exc}")

        if not self.providers:
            logging.warning(
                "Không tìm thấy provider LLM khả dụng nào. Hệ thống sẽ chạy ở chế độ phòng thủ."
            )

    def is_available(self) -> bool:
        return bool(self.providers)

    @retry(
        stop=stop_after_attempt(1),
        wait=wait_exponential(multiplier=1, min=1, max=3),
        retry=retry_if_exception(is_transient_error),
        reraise=True,
    )
    def invoke_with_retry(self, messages: List[BaseMessage]) -> BaseMessage:
        global _llm_active_count

        with _llm_count_lock:
            waiting_count = max(0, _llm_active_count - 3)
        if waiting_count > 0:
            logging.info(
                f"⏳ [SEMAPHORE] Có {waiting_count} tác vụ LLM đang xếp hàng đợi. Đang chờ slot trống..."
            )

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
                except Exception as exc:
                    logging.error(
                        f"Lỗi gọi LLM qua {name}: {exc}. Thử chuyển sang Provider dự phòng tiếp theo..."
                    )
                    last_error = exc

            if last_error is not None:
                raise last_error
            raise ValueError("Không có LLM provider nào khả dụng.")
        finally:
            _LLM_SEMAPHORE.release()
            with _llm_count_lock:
                _llm_active_count -= 1
                current_active = _llm_active_count
            logging.info(f"✅ [SEMAPHORE] Đã giải phóng slot LLM ({current_active}/3 còn hoạt động)")

    def generate_response(self, messages: List[BaseMessage]) -> str:
        if not self.is_available():
            raise LLMTimeoutError(
                "Không có provider LLM khả dụng. Hãy cấu hình GEMINI_API_KEY, OPENROUTER_API_KEY hoặc NVIDIA_API_KEY."
            )

        try:
            response = self.invoke_with_retry(messages)
            return response.content
        except Exception as exc:
            logging.critical(f"LLM hoàn toàn thất bại sau các lần thử: {exc}")
            raise LLMTimeoutError(f"Cổng kết nối AI (LLM) gặp sự cố kéo dài. Lỗi: {exc}")
