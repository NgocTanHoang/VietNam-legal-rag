import pytest
from unittest.mock import MagicMock, patch
from app.services.redis_service import RedisService
from app.services.llm_service import is_transient_error

def test_is_transient_error():
    """Verify that permanent errors are identified and transient ones are permitted for retry."""
    # Permanent client errors should return False
    assert is_transient_error(Exception("404 Not Found")) is False
    assert is_transient_error(Exception("401 Unauthorized access")) is False
    assert is_transient_error(Exception("403 Forbidden details")) is False
    
    # Transient errors should return True
    assert is_transient_error(Exception("503 Service Unavailable")) is True
    assert is_transient_error(Exception("429 Too Many Requests")) is True
    assert is_transient_error(Exception("Connection timeout")) is True

@patch("app.services.redis_service.redis.Redis")
def test_redis_service_bypass_mode(mock_redis_cls):
    """Test RedisService acts in bypass mode gracefully if connection fails."""
    # Setup mock to raise connection error on ping
    mock_client = MagicMock()
    mock_client.ping.side_effect = Exception("Connection refused")
    mock_redis_cls.return_value = mock_client
    
    # Reset singleton instance just for testing
    RedisService._instance = None
    
    service = RedisService()
    
    # Connection should be inactive
    assert service.is_active() is False
    
    # Methods should return None and not crash
    assert service.get_embedding("test query") is None
    assert service.get_chat_response("test chat") is None
    
    # Should not raise exception when setting values
    service.set_embedding("test query", [0.1, 0.2])
    service.set_chat_response("test chat", {"answer": "response"})

@patch("app.services.redis_service.redis.Redis")
def test_redis_service_caching(mock_redis_cls):
    """Test RedisService reads and writes successfully when active."""
    mock_client = MagicMock()
    mock_client.ping.return_value = True
    
    # Setup mock gets and sets
    cached_embed = "[0.1, 0.2, 0.3]"
    cached_chat = '{"answer": "câu trả lời", "query": "câu hỏi"}'
    
    def mock_get(key):
        if "embed" in key:
            return cached_embed
        if "response" in key:
            return cached_chat
        return None
        
    mock_client.get.side_effect = mock_get
    mock_redis_cls.return_value = mock_client
    
    # Reset singleton instance
    RedisService._instance = None
    
    service = RedisService()
    
    assert service.is_active() is True
    
    # Test reading
    embed_res = service.get_embedding("câu hỏi")
    assert embed_res == [0.1, 0.2, 0.3]
    
    chat_res = service.get_chat_response("câu hỏi")
    assert chat_res["answer"] == "câu trả lời"
    assert chat_res["query"] == "câu hỏi"
    
    # Test writing
    service.set_embedding("câu hỏi mới", [0.4, 0.5])
    mock_client.setex.assert_called()
