import json
import logging
import redis
from typing import Optional, List, Dict, Any
from app.core.config import settings

class RedisService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        """Singleton pattern to share a single connection pool across requests."""
        if not cls._instance:
            cls._instance = super(RedisService, cls).__new__(cls, *args, **kwargs)
            cls._instance._init_redis()
        return cls._instance

    def _init_redis(self):
        """Khởi tạo kết nối Redis với cơ chế tự động chuyển đổi host cục bộ và bỏ qua lỗi nếu offline."""
        self.client = None
        import os
        
        # 1. Thử kết nối với host được định nghĩa trong .env (e.g. 'redis' hoặc IP cụ thể)
        primary_host = settings.REDIS_HOST or "localhost"
        port = settings.REDIS_PORT or 6379
        
        # Kiểm tra nếu chạy ngoài Docker container, tự động đổi 'redis' -> '127.0.0.1' để tránh DNS Timeout
        is_outside_docker = not os.path.exists("/.dockerenv")
        if primary_host == "redis" and is_outside_docker:
            logging.info("Phát hiện đang chạy ngoài Docker container. Tự động chuyển đổi host 'redis' thành '127.0.0.1'.")
            primary_host = "127.0.0.1"
            
        logging.info(f"Đang thử kết nối Redis (Primary) tại {primary_host}:{port}...")
        try:
            client = redis.Redis(
                host=primary_host,
                port=port,
                db=0,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
                decode_responses=True
            )
            # Thử ping để đảm bảo kết nối thực tế hoạt động
            client.ping()
            self.client = client
            logging.info(f"Kết nối Redis thành công tới {primary_host}:{port}!")
            return
        except Exception as e:
            logging.warning(
                f"Không thể kết nối tới Redis Primary '{primary_host}:{port}': {str(e)}. "
                "Đang thử kết nối dự phòng tới '127.0.0.1'..."
            )

        # 2. Thử kết nối dự phòng tới 'localhost' (Thích hợp khi chạy local ngoài Docker)
        if primary_host != "localhost":
            try:
                client = redis.Redis(
                    host="localhost",
                    port=port,
                    db=0,
                    socket_connect_timeout=1.5,
                    socket_timeout=1.5,
                    decode_responses=True
                )
                client.ping()
                self.client = client
                logging.info(f"Kết nối dự phòng Redis thành công tới localhost:{port}!")
                return
            except Exception as ex:
                logging.warning(f"Kết nối dự phòng Redis tới localhost:{port} cũng thất bại: {str(ex)}")
                
        logging.warning("=== REDIS ĐANG OFFLINE. Hệ thống kích hoạt chế độ BYPASS CACHE (Bỏ qua bộ đệm) ===")
        self.client = None

    def is_active(self) -> bool:
        """Kiểm tra Redis có đang kết nối và sẵn sàng hoạt động hay không."""
        if self.client is None:
            return False
        try:
            return bool(self.client.ping())
        except Exception:
            return False

    # --- KHU VỰC CACHE EMBEDDING VECTORS ---

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """Lấy vector embedding đã lưu trong cache cho đoạn văn bản text."""
        if not self.is_active():
            return None
        try:
            # Tạo key hash từ văn bản để tránh key quá dài
            import hashlib
            text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
            key = f"embed:{text_hash}"
            
            cached_val = self.client.get(key)
            if cached_val:
                logging.info(f"Redis Cache HIT: Tìm thấy Vector Cache cho từ khóa: '{text[:20]}...'")
                return json.loads(cached_val)
        except Exception as e:
            logging.error(f"Lỗi khi đọc Vector từ Redis Cache: {str(e)}")
        return None

    def set_embedding(self, text: str, vector: List[float], expire_seconds: int = 86400):
        """Lưu vector embedding của đoạn văn bản vào cache (mặc định hết hạn sau 24h)."""
        if not self.is_active() or not vector:
            return
        try:
            import hashlib
            text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
            key = f"embed:{text_hash}"
            
            self.client.setex(key, expire_seconds, json.dumps(vector))
            logging.info(f"Redis Cache SET: Đã lưu Vector Cache thành công cho từ khóa: '{text[:20]}...'")
        except Exception as e:
            logging.error(f"Lỗi khi ghi Vector vào Redis Cache: {str(e)}")

    # --- KHU VỰC CACHE RAG RESPONSES ---

    def get_chat_response(self, query: str) -> Optional[Dict[str, Any]]:
        """Lấy câu trả lời RAG đã tổng hợp sẵn từ cache cho câu hỏi query."""
        if not self.is_active():
            return None
        try:
            import hashlib
            query_hash = hashlib.md5(query.strip().encode("utf-8")).hexdigest()
            key = f"response:{query_hash}"
            
            cached_val = self.client.get(key)
            if cached_val:
                logging.info(f"Redis Cache HIT: Tìm thấy Câu trả lời RAG Cache cho câu hỏi: '{query[:20]}...'")
                return json.loads(cached_val)
        except Exception as e:
            logging.error(f"Lỗi khi đọc RAG Response từ Redis Cache: {str(e)}")
        return None

    def set_chat_response(self, query: str, response_data: Dict[str, Any], expire_seconds: int = 3600):
        """Lưu câu trả lời RAG tổng hợp vào cache (mặc định hết hạn sau 1 giờ)."""
        if not self.is_active() or not response_data:
            return
        try:
            import hashlib
            query_hash = hashlib.md5(query.strip().encode("utf-8")).hexdigest()
            key = f"response:{query_hash}"
            
            self.client.setex(key, expire_seconds, json.dumps(response_data))
            logging.info(f"Redis Cache SET: Đã lưu Câu trả lời RAG Cache thành công cho câu hỏi: '{query[:20]}...'")
        except Exception as e:
            logging.error(f"Lỗi khi ghi RAG Response vào Redis Cache: {str(e)}")

    # --- KHU VỰC KHÓA PHÂN TÁN (DISTRIBUTED LOCK) ---

    def acquire_query_lock(self, query: str, lock_ttl_seconds: int = 60) -> bool:
        """
        Thử đặt khóa phân tán cho một câu hỏi cụ thể.
        Trả về True nếu đặt khóa thành công (request đầu tiên).
        Trả về False nếu khóa đã tồn tại (có request trùng đang xử lý).
        """
        if not self.is_active():
            return True  # Nếu Redis offline, cho phép xử lý bình thường (không block)
        try:
            import hashlib
            query_hash = hashlib.md5(query.strip().encode("utf-8")).hexdigest()
            lock_key = f"lock:query:{query_hash}"
            
            # SET NX (Set if Not eXists) - atomic operation, tránh race condition
            acquired = self.client.set(lock_key, "processing", nx=True, ex=lock_ttl_seconds)
            if acquired:
                logging.info(f"🔒 [LOCK] Đặt khóa phân tán thành công cho câu hỏi: '{query[:30]}...'")
                return True
            else:
                logging.info(f"⏳ [LOCK] Phát hiện câu hỏi trùng lặp đang được xử lý: '{query[:30]}...'")
                return False
        except Exception as e:
            logging.error(f"Lỗi khi đặt khóa phân tán Redis: {str(e)}")
            return True  # Fallback: cho phép xử lý nếu Redis lỗi

    def release_query_lock(self, query: str):
        """Giải phóng khóa phân tán sau khi xử lý xong."""
        if not self.is_active():
            return
        try:
            import hashlib
            query_hash = hashlib.md5(query.strip().encode("utf-8")).hexdigest()
            lock_key = f"lock:query:{query_hash}"
            
            self.client.delete(lock_key)
            logging.info(f"🔓 [LOCK] Đã giải phóng khóa phân tán cho câu hỏi: '{query[:30]}...'")
        except Exception as e:
            logging.error(f"Lỗi khi giải phóng khóa phân tán Redis: {str(e)}")

    def wait_for_cached_result(self, query: str, max_wait_seconds: int = 30, poll_interval: float = 0.5) -> Optional[Dict[str, Any]]:
        """
        Đợi kết quả cache xuất hiện khi phát hiện câu hỏi trùng đang xử lý.
        Poll Redis cache mỗi poll_interval giây, tối đa max_wait_seconds giây.
        Trả về kết quả cache nếu tìm thấy, None nếu hết thời gian chờ.
        """
        if not self.is_active():
            return None
        try:
            import time
            import hashlib
            query_hash = hashlib.md5(query.strip().encode("utf-8")).hexdigest()
            response_key = f"response:{query_hash}"
            lock_key = f"lock:query:{query_hash}"
            
            elapsed = 0.0
            while elapsed < max_wait_seconds:
                # Kiểm tra cache đã có kết quả chưa
                cached_val = self.client.get(response_key)
                if cached_val:
                    logging.info(f"✅ [LOCK] Đã nhận kết quả từ cache sau {elapsed:.1f}s chờ đợi cho: '{query[:30]}...'")
                    return json.loads(cached_val)
                
                # Kiểm tra lock còn tồn tại không (nếu lock đã hết mà chưa có cache = lỗi)
                if not self.client.exists(lock_key):
                    logging.warning(f"⚠️ [LOCK] Khóa đã được giải phóng nhưng không tìm thấy cache cho: '{query[:30]}...'")
                    return None
                
                time.sleep(poll_interval)
                elapsed += poll_interval
                
            logging.warning(f"⏰ [LOCK] Hết thời gian chờ ({max_wait_seconds}s) cho câu hỏi trùng lặp: '{query[:30]}...'")
            return None
        except Exception as e:
            logging.error(f"Lỗi khi chờ kết quả cache: {str(e)}")
            return None

