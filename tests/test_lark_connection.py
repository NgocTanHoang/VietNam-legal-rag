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

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import BackgroundTasks
from app.api.v1.lark_webhook import lark_webhook_receiver
from app.core.config import settings

@pytest.mark.anyio
async def test_lark_url_verification_direct():
    """Verify that URL Verification challenge is correctly handled and returned (Direct call)."""
    # Mock Request
    mock_request = MagicMock()
    challenge_payload = {
        "type": "url_verification",
        "challenge": "test_challenge_token_12345"
    }
    body_bytes = json.dumps(challenge_payload).encode("utf-8")
    
    # Async body method
    async def mock_body():
        return body_bytes
    mock_request.body = mock_body
    
    # Mock services
    mock_background_tasks = MagicMock(spec=BackgroundTasks)
    mock_agent = MagicMock()
    mock_lark_service = MagicMock()
    
    # Temporarily clear encrypt key to bypass signature verification
    with patch.object(settings, "LARK_ENCRYPT_KEY", ""):
        response = await lark_webhook_receiver(
            request=mock_request,
            background_tasks=mock_background_tasks,
            agent=mock_agent,
            lark_service=mock_lark_service
        )
        
    assert response == {"challenge": "test_challenge_token_12345"}

@pytest.mark.anyio
async def test_lark_message_received_async_direct():
    """Verify that messages are received and processed asynchronously without blocking (Direct call)."""
    # Mock Request
    mock_request = MagicMock()
    message_payload = {
        "header": {
            "event_type": "im.message.receive_v1"
        },
        "event": {
            "message": {
                "message_id": "om_test_message_id_67890",
                "msg_type": "text",
                "content": json.dumps({"text": "Quy định về thế chấp ngân hàng"})
            }
        }
    }
    body_bytes = json.dumps(message_payload).encode("utf-8")
    
    async def mock_body():
        return body_bytes
    mock_request.body = mock_body
    
    # Mock services
    mock_background_tasks = MagicMock(spec=BackgroundTasks)
    mock_agent = MagicMock()
    mock_lark_service = MagicMock()
    
    # Temporarily clear encrypt key to bypass signature verification
    with patch.object(settings, "LARK_ENCRYPT_KEY", ""):
        response = await lark_webhook_receiver(
            request=mock_request,
            background_tasks=mock_background_tasks,
            agent=mock_agent,
            lark_service=mock_lark_service
        )
        
    assert response == {"status": "success"}
    
    # Verify that background task was enqueued
    mock_background_tasks.add_task.assert_called_once()
    called_args, called_kwargs = mock_background_tasks.add_task.call_args
    # Check the function called and parameters
    assert called_args[0].__name__ == "process_lark_message_async"
    assert called_kwargs["message_id"] == "om_test_message_id_67890"
    assert called_kwargs["user_query"] == "Quy định về thế chấp ngân hàng"

@pytest.mark.anyio
async def test_lark_verification_token_mismatch():
    """Verify that mismatching LARK_VERIFICATION_TOKEN raises an HTTP 401 Exception."""
    from fastapi import HTTPException
    
    # Mock Request
    mock_request = MagicMock()
    challenge_payload = {
        "type": "url_verification",
        "challenge": "test_challenge_token_12345",
        "token": "wrong_token"
    }
    body_bytes = json.dumps(challenge_payload).encode("utf-8")
    
    async def mock_body():
        return body_bytes
    mock_request.body = mock_body
    
    # Mock services
    mock_background_tasks = MagicMock(spec=BackgroundTasks)
    mock_agent = MagicMock()
    mock_lark_service = MagicMock()
    
    # Temporarily set LARK_VERIFICATION_TOKEN to verify it raises HTTPException 401
    with patch.object(settings, "LARK_ENCRYPT_KEY", ""), patch.object(settings, "LARK_VERIFICATION_TOKEN", "valid_token"):
        with pytest.raises(HTTPException) as exc_info:
            await lark_webhook_receiver(
                request=mock_request,
                background_tasks=mock_background_tasks,
                agent=mock_agent,
                lark_service=mock_lark_service
            )
        assert exc_info.value.status_code == 401
        assert "Xác thực verification token thất bại" in exc_info.value.detail

@pytest.mark.anyio
async def test_lark_decryption_and_verification():
    """Verify that encrypted payloads are decrypted and handled correctly."""
    # Mock Request
    mock_request = MagicMock()
    encrypted_payload = {
        "encrypt": "mock_encrypted_string_here"
    }
    body_bytes = json.dumps(encrypted_payload).encode("utf-8")
    
    async def mock_body():
        return body_bytes
    mock_request.body = mock_body
    
    # Mock services
    mock_background_tasks = MagicMock(spec=BackgroundTasks)
    mock_agent = MagicMock()
    mock_lark_service = MagicMock()
    
    # Mock decryptor
    mock_decrypted_payload = {
        "type": "url_verification",
        "challenge": "decrypted_challenge_123"
    }
    
    with patch.object(settings, "LARK_ENCRYPT_KEY", "dummy_encrypt_key"):
        with patch("app.api.v1.lark_webhook.LarkDecryptor") as MockDecryptorClass:
            mock_decryptor_instance = MagicMock()
            mock_decryptor_instance.decrypt.return_value = json.dumps(mock_decrypted_payload)
            MockDecryptorClass.return_value = mock_decryptor_instance
            
            # Call webhook
            response = await lark_webhook_receiver(
                request=mock_request,
                background_tasks=mock_background_tasks,
                x_lark_signature=None,
                x_lark_request_timestamp=None,
                x_lark_request_nonce=None,
                agent=mock_agent,
                lark_service=mock_lark_service
            )
            
            assert response == {"challenge": "decrypted_challenge_123"}
            MockDecryptorClass.assert_called_once_with("dummy_encrypt_key")
            mock_decryptor_instance.decrypt.assert_called_once_with("mock_encrypted_string_here")

def test_process_lark_message_async_task():
    """Verify that process_lark_message_async correctly runs the agent and replies via lark service."""
    from app.api.v1.lark_webhook import process_lark_message_async
    from app.services.redis_service import RedisService
    
    mock_agent = MagicMock()
    mock_agent.run.return_value = {
        "answer": "Đây là câu trả lời thử nghiệm.",
        "query_rewritten": None,
        "context_chunks": [],
        "graph_context": []
    }
    
    mock_lark_service = MagicMock()
    mock_lark_service.send_reply.return_value = True
    
    # Mock RedisService Singleton: reset instance và patch class
    mock_redis_instance = MagicMock()
    mock_redis_instance.get_chat_response.return_value = None  # Không có cache
    mock_redis_instance.acquire_query_lock.return_value = True  # Đặt lock thành công
    mock_redis_instance.release_query_lock.return_value = None
    mock_redis_instance.set_chat_response.return_value = None
    
    # Lưu lại và reset Singleton
    original_instance = RedisService._instance
    RedisService._instance = mock_redis_instance
    
    try:
        process_lark_message_async(
            message_id="om_test_message_id_67890",
            user_query="Câu hỏi luật",
            agent=mock_agent,
            lark_service=mock_lark_service
        )
        
        mock_agent.run.assert_called_once_with("Câu hỏi luật")
        mock_lark_service.send_reply.assert_called_once_with(
            message_id="om_test_message_id_67890",
            text_content="Đây là câu trả lời thử nghiệm."
        )
    finally:
        # Khôi phục Singleton gốc
        RedisService._instance = original_instance
