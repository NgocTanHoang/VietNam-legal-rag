import json
import logging
from fastapi import APIRouter, Request, Depends, BackgroundTasks, Header, HTTPException
from typing import Dict, Any, Optional

from app.core.config import settings
from app.core.security import verify_lark_signature, LarkDecryptor
from app.api.dependencies import get_lark_service, get_legal_agent
from app.services.lark_service import LarkService
from app.agents.legal_agent import LegalAgent

router = APIRouter()

def process_lark_message_async(
    message_id: str, 
    user_query: str, 
    agent: LegalAgent, 
    lark_service: LarkService
):
    """
    Xử lý tác vụ AI Agent Luật sư trong nền (Background) 
    và trả lời người dùng thông qua Lark API khi hoàn tất.
    Tích hợp Redis Cache + Distributed Lock để tránh xử lý trùng lặp.
    """
    logging.info(f"[LARK ASYNC TASK] >>> Bắt đầu xử lý bất đồng bộ cho Message ID: {message_id}")
    logging.info(f"[LARK ASYNC TASK] Nội dung câu hỏi gốc: '{user_query}'")
    try:
        from app.services.redis_service import RedisService
        redis_service = RedisService()
        
        # 1. Kiểm tra Cache trước (trả lời siêu nhanh nếu đã có sẵn)
        cached_res = redis_service.get_chat_response(user_query)
        if cached_res:
            answer = cached_res.get("answer", "")
            logging.info(f"[LARK ASYNC TASK] Cache HIT! Trả lời ngay từ cache ({len(answer)} ký tự).")
            lark_service.send_reply(message_id=message_id, text_content=answer)
            return
        
        # 2. Thử đặt khóa phân tán
        lock_acquired = redis_service.acquire_query_lock(user_query)
        
        if not lock_acquired:
            # Câu hỏi trùng đang được xử lý → đợi kết quả
            logging.info(f"[LARK ASYNC TASK] Phát hiện trùng lặp. Đợi kết quả từ request gốc...")
            waited_result = redis_service.wait_for_cached_result(user_query, max_wait_seconds=30)
            if waited_result:
                answer = waited_result.get("answer", "")
                logging.info(f"[LARK ASYNC TASK] Nhận kết quả từ cache sau khi đợi ({len(answer)} ký tự).")
                lark_service.send_reply(message_id=message_id, text_content=answer)
                return
            else:
                logging.warning(f"[LARK ASYNC TASK] Hết thời gian chờ. Xử lý lại từ đầu.")
                redis_service.acquire_query_lock(user_query)
        
        # 3. Chạy Agent LangGraph (chỉ request đầu tiên mới tới đây)
        try:
            logging.info("[LARK ASYNC TASK] Đang kích hoạt LangGraph AI Agent suy luận...")
            result = agent.run(user_query)
            answer = result.get("answer", "Rất tiếc, tôi không thể tìm thấy câu trả lời phù hợp.")
            logging.info(f"[LARK ASYNC TASK] Agent suy luận thành công. Độ dài câu trả lời: {len(answer)} ký tự.")
            
            # 4. Lưu vào cache để các request trùng lặp đang chờ có thể lấy
            graph_relations_count = 0
            for item in result.get("graph_context", []):
                graph_relations_count += len(item.get("thong_tin_thay_the", []))
                graph_relations_count += len(item.get("van_ban_huong_dan", []))
                graph_relations_count += len(item.get("quan_he_lien_quan", []))
            
            response_data = {
                "query": user_query,
                "answer": answer,
                "query_rewritten": result.get("query_rewritten"),
                "chunks_count": len(result.get("context_chunks", [])),
                "graph_relations_count": graph_relations_count,
                "graph_context": result.get("graph_context", [])
            }
            redis_service.set_chat_response(user_query, response_data)
            
            # 5. Gửi kết quả phản hồi lên Lark
            logging.info(f"[LARK ASYNC TASK] Đang gửi phản hồi trả lời tin nhắn {message_id} qua Lark Service...")
            success = lark_service.send_reply(message_id=message_id, text_content=answer)
            if success:
                logging.info(f"[LARK ASYNC TASK] <<< Gửi phản hồi thành công cho Message ID: {message_id}")
            else:
                logging.error(f"[LARK ASYNC TASK] <<< Gửi phản hồi THẤT BẠI cho Message ID: {message_id}")
        finally:
            # 6. LUÔN giải phóng khóa
            redis_service.release_query_lock(user_query)
    except Exception as e:
        logging.error(f"[LARK ASYNC TASK] Lỗi nghiêm trọng khi xử lý tin nhắn Lark async: {str(e)}", exc_info=True)
        # Gửi tin nhắn báo lỗi
        lark_service.send_reply(
            message_id=message_id, 
            text_content="Đã xảy ra sự cố trong quá trình xử lý câu hỏi pháp lý. Vui lòng thử lại sau ít phút."
        )

@router.post("/webhook", summary="Tiếp nhận Webhook từ Lark Suite")
async def lark_webhook_receiver(
    request: Request,
    background_tasks: BackgroundTasks,
    x_lark_signature: Optional[str] = Header(None, alias="X-Lark-Signature"),
    x_lark_request_timestamp: Optional[str] = Header(None, alias="X-Lark-Request-Timestamp"),
    x_lark_request_nonce: Optional[str] = Header(None, alias="X-Lark-Request-Nonce"),
    agent: LegalAgent = Depends(get_legal_agent),
    lark_service: LarkService = Depends(get_lark_service)
):
    """
    Endpoint tiếp nhận webhook từ Lark Suite.
    - Hỗ trợ URL Verification thách thức cấu hình.
    - Xác thực chữ ký bảo mật.
    - Xử lý giải mã (Decryption) tin nhắn nếu được cấu hình.
    - Chạy bất đồng bộ (Async Background Tasks) để tránh Lark Timeout (3 giây).
    """
    logging.info("==================================================")
    logging.info("📥 [WEBHOOK] NHẬN YÊU CẦU WEBHOOK MỚI TỪ LARK SUITE")
    logging.info("==================================================")
    
    # 1. Đọc Body thô
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")
    logging.info(f"[WEBHOOK] Raw Body length: {len(body_str)} bytes")
    logging.info(f"[WEBHOOK] Headers: X-Lark-Signature={x_lark_signature}, Timestamp={x_lark_request_timestamp}, Nonce={x_lark_request_nonce}")
    
    # 2. Kiểm tra chữ ký bảo mật nếu đã cấu hình key
    if settings.LARK_ENCRYPT_KEY and x_lark_signature:
        logging.info("[WEBHOOK] Đang thực hiện xác thực chữ ký gói tin từ Lark...")
        is_valid = verify_lark_signature(
            timestamp=x_lark_request_timestamp or "",
            nonce=x_lark_request_nonce or "",
            signature=x_lark_signature,
            body=body_str
        )
        if not is_valid:
            logging.warning("[WEBHOOK] Xác thực chữ ký Lark Suite thất bại!")
            raise HTTPException(status_code=401, detail="Xác thực chữ ký Lark Suite thất bại.")
        logging.info("[WEBHOOK] Xác thực chữ ký Lark Suite thành công!")
            
    # 3. Phân tích cú pháp JSON
    try:
        payload = json.loads(body_str)
    except Exception as e:
        logging.error(f"[WEBHOOK] JSON Parse Error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"JSON không hợp lệ: {str(e)}")
        
    # 4. Xử lý giải mã (Decryption) nếu gói tin bị mã hóa bởi Lark
    if "encrypt" in payload:
        logging.info("[WEBHOOK] Phát hiện gói tin bị mã hóa bởi Lark. Bắt đầu giải mã...")
        if not settings.LARK_ENCRYPT_KEY:
            logging.error("[WEBHOOK] Nhận gói tin mã hóa từ Lark nhưng LARK_ENCRYPT_KEY chưa được cấu hình.")
            raise HTTPException(status_code=500, detail="Nhận gói tin mã hóa từ Lark nhưng LARK_ENCRYPT_KEY chưa được cấu hình.")
        try:
            decryptor = LarkDecryptor(settings.LARK_ENCRYPT_KEY)
            decrypted_str = decryptor.decrypt(payload["encrypt"])
            payload = json.loads(decrypted_str)
            logging.info("[WEBHOOK] Giải mã dữ liệu thành công!")
        except Exception as e:
            logging.error(f"[WEBHOOK] Lỗi khi giải mã payload Lark: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Giải mã dữ liệu thất bại: {str(e)}")
        
    # 4.5. Xác thực Verification Token nếu đã cấu hình
    if settings.LARK_VERIFICATION_TOKEN:
        token = payload.get("token") or payload.get("header", {}).get("token")
        if token != settings.LARK_VERIFICATION_TOKEN:
            logging.warning(f"[WEBHOOK] Verification Token không khớp! Expected: {settings.LARK_VERIFICATION_TOKEN}, Got: {token}")
            raise HTTPException(status_code=401, detail="Xác thực verification token thất bại.")
        logging.info("[WEBHOOK] Xác thực Verification Token thành công!")
        
    # 5. Xử lý URL Challenge (Dùng cho cấu hình Webhook Lark Console lần đầu)
    if payload.get("type") == "url_verification":
        challenge = payload.get("challenge")
        logging.info(f"[WEBHOOK] Nhận yêu cầu URL Verification Challenge: challenge_token='{challenge}'")
        logging.info("=== LARK URL VERIFICATION SUCCESSFUL ===")
        return {"challenge": challenge}
        
    # 6. Xử lý sự kiện nhận tin nhắn (Event type im.message.receive_v1)
    event_header = payload.get("header", {})
    event_type = event_header.get("event_type")
    logging.info(f"[WEBHOOK] Loại sự kiện Lark nhận được: event_type='{event_type}'")
    
    if event_type == "im.message.receive_v1":
        event_data = payload.get("event", {})
        message = event_data.get("message", {})
        msg_type = message.get("msg_type")
        message_id = message.get("message_id")
        logging.info(f"[WEBHOOK] Chi tiết tin nhắn: Message ID={message_id}, Type={msg_type}")
        
        # Chỉ xử lý tin nhắn dạng văn bản (Text)
        if msg_type == "text" and message_id:
            try:
                content_str = message.get("content", "{}")
                content_data = json.loads(content_str)
                user_query = content_data.get("text", "").strip()
                
                # Trích xuất bỏ tag bot nếu có (ví dụ: @BotName)
                if user_query:
                    # Loại bỏ phần tag bot dạng @_user_1
                    import re
                    user_query = re.sub(r'@[^\s]+', '', user_query).strip()
                    
                if user_query:
                    logging.info(f"[WEBHOOK] Tin nhắn hợp lệ từ người dùng: '{user_query}'")
                    logging.info(f"[WEBHOOK] Đang chuyển tác vụ cho Background Tasks xử lý bất đồng bộ...")
                    
                    # Chạy Asynchronously trong BackgroundTask để trả về 200 OK ngay lập tức (<3s)
                    background_tasks.add_task(
                        process_lark_message_async,
                        message_id=message_id,
                        user_query=user_query,
                        agent=agent,
                        lark_service=lark_service
                    )
                else:
                    logging.warning("[WEBHOOK] Nội dung câu hỏi rỗng sau khi loại bỏ tag Bot. Bỏ qua.")
            except Exception as e:
                logging.error(f"[WEBHOOK] Lỗi khi xử lý nội dung tin nhắn: {str(e)}")
        else:
            logging.info(f"[WEBHOOK] Nhận loại tin nhắn '{msg_type}' không được hỗ trợ hoặc thiếu Message ID. Bỏ qua.")
                
    # Trả về 200 OK cho Lark ngay lập tức để hoàn thành yêu cầu dưới 3 giây
    logging.info("[WEBHOOK] Phản hồi HTTP 200 OK ngay lập tức về Lark Suite để tránh timeout.")
    return {"status": "success"}
