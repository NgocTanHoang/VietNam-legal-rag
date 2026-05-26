import json
import sys
import time
import types
from unittest.mock import MagicMock, patch

import pytest
from fastapi import BackgroundTasks

try:
    import langchain_core.pydantic_v1
except ModuleNotFoundError:
    import pydantic.v1 as v1

    pydantic_v1 = types.ModuleType("langchain_core.pydantic_v1")
    for name in dir(v1):
        setattr(pydantic_v1, name, getattr(v1, name))
    sys.modules["langchain_core.pydantic_v1"] = pydantic_v1

from app.api.v1.lark_webhook import lark_webhook_receiver
from app.core.config import settings


@pytest.mark.anyio
async def test_lark_url_verification_direct():
    mock_request = MagicMock()
    challenge_payload = {
        "type": "url_verification",
        "challenge": "test_challenge_token_12345",
    }

    async def mock_body():
        return json.dumps(challenge_payload).encode("utf-8")

    mock_request.body = mock_body
    mock_background_tasks = MagicMock(spec=BackgroundTasks)

    with patch.object(settings, "LARK_ENCRYPT_KEY", ""):
        response = await lark_webhook_receiver(
            request=mock_request,
            background_tasks=mock_background_tasks,
            agent=MagicMock(),
            lark_service=MagicMock(),
        )

    assert response == {"challenge": "test_challenge_token_12345"}


@pytest.mark.anyio
async def test_lark_message_received_async_direct_under_100ms():
    mock_request = MagicMock()
    message_payload = {
        "header": {
            "event_type": "im.message.receive_v1"
        },
        "event": {
            "message": {
                "message_id": "om_test_message_id_67890",
                "msg_type": "text",
                "content": json.dumps({"text": "Quy định về thế chấp ngân hàng"}),
            }
        },
    }

    async def mock_body():
        return json.dumps(message_payload).encode("utf-8")

    mock_request.body = mock_body
    mock_background_tasks = MagicMock(spec=BackgroundTasks)

    started_at = time.perf_counter()
    with patch.object(settings, "LARK_ENCRYPT_KEY", ""):
        response = await lark_webhook_receiver(
            request=mock_request,
            background_tasks=mock_background_tasks,
            agent=MagicMock(),
            lark_service=MagicMock(),
        )
    elapsed_ms = (time.perf_counter() - started_at) * 1000

    assert response == {"status": "success"}
    assert elapsed_ms < 100

    mock_background_tasks.add_task.assert_called_once()
    called_args, called_kwargs = mock_background_tasks.add_task.call_args
    assert called_args[0].__name__ == "process_lark_message_async"
    assert called_kwargs["message_id"] == "om_test_message_id_67890"
    assert called_kwargs["user_query"] == "Quy định về thế chấp ngân hàng"


@pytest.mark.anyio
async def test_lark_verification_token_mismatch():
    from fastapi import HTTPException

    mock_request = MagicMock()
    challenge_payload = {
        "type": "url_verification",
        "challenge": "test_challenge_token_12345",
        "token": "wrong_token",
    }

    async def mock_body():
        return json.dumps(challenge_payload).encode("utf-8")

    mock_request.body = mock_body

    with patch.object(settings, "LARK_ENCRYPT_KEY", ""), patch.object(settings, "LARK_VERIFICATION_TOKEN", "valid_token"):
        with pytest.raises(HTTPException) as exc_info:
            await lark_webhook_receiver(
                request=mock_request,
                background_tasks=MagicMock(spec=BackgroundTasks),
                agent=MagicMock(),
                lark_service=MagicMock(),
            )
    assert exc_info.value.status_code == 401
    assert "Xác thực verification token thất bại" in exc_info.value.detail


@pytest.mark.anyio
async def test_lark_decryption_and_verification():
    mock_request = MagicMock()
    encrypted_payload = {"encrypt": "mock_encrypted_string_here"}

    async def mock_body():
        return json.dumps(encrypted_payload).encode("utf-8")

    mock_request.body = mock_body
    mock_decrypted_payload = {
        "type": "url_verification",
        "challenge": "decrypted_challenge_123",
    }

    with patch.object(settings, "LARK_ENCRYPT_KEY", "dummy_encrypt_key"):
        with patch("app.api.v1.lark_webhook.LarkDecryptor") as decryptor_class:
            decryptor_instance = MagicMock()
            decryptor_instance.decrypt.return_value = json.dumps(mock_decrypted_payload)
            decryptor_class.return_value = decryptor_instance

            response = await lark_webhook_receiver(
                request=mock_request,
                background_tasks=MagicMock(spec=BackgroundTasks),
                x_lark_signature=None,
                x_lark_request_timestamp=None,
                x_lark_request_nonce=None,
                agent=MagicMock(),
                lark_service=MagicMock(),
            )

    assert response == {"challenge": "decrypted_challenge_123"}
    decryptor_class.assert_called_once_with("dummy_encrypt_key")
    decryptor_instance.decrypt.assert_called_once_with("mock_encrypted_string_here")


def test_process_lark_message_async_task():
    from app.api.v1.lark_webhook import process_lark_message_async
    from app.services.redis_service import RedisService

    mock_agent = MagicMock()
    mock_agent.run.return_value = {
        "answer": "Đây là câu trả lời thử nghiệm.",
        "query_rewritten": None,
        "context_chunks": [],
        "graph_context": [],
    }
    mock_lark_service = MagicMock()
    mock_lark_service.send_reply.return_value = True

    mock_redis_instance = MagicMock()
    mock_redis_instance.get_chat_response.return_value = None
    mock_redis_instance.acquire_query_lock.return_value = True
    mock_redis_instance.release_query_lock.return_value = None
    mock_redis_instance.set_chat_response.return_value = None

    original_instance = RedisService._instance
    RedisService._instance = mock_redis_instance

    try:
        process_lark_message_async(
            message_id="om_test_message_id_67890",
            user_query="Câu hỏi luật",
            agent=mock_agent,
            lark_service=mock_lark_service,
        )
    finally:
        RedisService._instance = original_instance

    mock_agent.run.assert_called_once_with("Câu hỏi luật")
    mock_lark_service.send_reply.assert_called_once_with(
        message_id="om_test_message_id_67890",
        text_content="Đây là câu trả lời thử nghiệm.",
    )
