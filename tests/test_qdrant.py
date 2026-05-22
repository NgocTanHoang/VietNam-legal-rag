import pytest
from unittest.mock import MagicMock, patch
from app.services.qdrant_service import QdrantService
from qdrant_client.http.models import ScoredPoint

@patch("app.services.qdrant_service.QdrantClient")
def test_search_legal_documents(mock_qdrant_client_cls):
    """Test tìm kiếm văn bản pháp luật trong QdrantService với mock client."""
    # Setup mock
    mock_client = MagicMock()
    mock_qdrant_client_cls.return_value = mock_client
    
    # Tạo danh sách ScoredPoint giả lập
    mock_hit = MagicMock(spec=ScoredPoint)
    mock_hit.id = "point-uuid-123"
    mock_hit.score = 0.85
    mock_hit.payload = {
        "id": 12345,
        "title": "Luật Doanh nghiệp 2020",
        "content": "Điều 1: Phạm vi điều chỉnh...",
        "so_ky_hieu": "59/2020/QH14",
        "tinh_trang_hieu_luc": "Còn hiệu lực",
        "loai_van_ban": "Luật",
        "ngay_ban_hanh": "2020-06-17"
    }
    
    mock_client.search.return_value = [mock_hit]
    
    # Chạy test
    service = QdrantService()
    results = service.search_legal_documents(query_vector=[0.1] * 384, limit=1)
    
    # Kiểm tra các khẳng định (Assertions)
    assert len(results) == 1
    assert results[0]["doc_id"] == 12345
    assert results[0]["title"] == "Luật Doanh nghiệp 2020"
    assert results[0]["score"] == 0.85
    assert results[0]["so_ky_hieu"] == "59/2020/QH14"
    
    # Kiểm tra phương thức search của client được gọi đúng cách
    mock_client.search.assert_called_once()

@patch("app.services.qdrant_service.QdrantClient")
def test_get_document_by_id(mock_qdrant_client_cls):
    """Test lấy tài liệu bằng ID trong QdrantService."""
    mock_client = MagicMock()
    mock_qdrant_client_cls.return_value = mock_client
    
    # Setup mock scroll response
    mock_point = MagicMock()
    mock_point.id = "point-uuid-abc"
    mock_point.payload = {
        "id": 54321,
        "title": "Luật Đầu tư 2020",
        "content": "Nội dung Luật Đầu tư...",
        "so_ky_hieu": "61/2020/QH14",
        "tinh_trang_hieu_luc": "Còn hiệu lực"
    }
    
    # scroll trả về Tuple (List[Record], Optional[str])
    mock_client.scroll.return_value = ([mock_point], None)
    
    service = QdrantService()
    doc = service.get_document_by_id("54321")
    
    assert doc is not None
    assert doc["doc_id"] == 54321
    assert doc["title"] == "Luật Đầu tư 2020"
    assert doc["so_ky_hieu"] == "61/2020/QH14"
    mock_client.scroll.assert_called_once()

@patch("app.services.qdrant_service.QdrantClient")
def test_count_documents_by_year(mock_qdrant_client_cls):
    """Test đếm tài liệu theo năm trong QdrantService."""
    mock_client = MagicMock()
    mock_qdrant_client_cls.return_value = mock_client
    
    # Setup mock count
    mock_count_result = MagicMock()
    mock_count_result.count = 42
    mock_client.count.return_value = mock_count_result
    
    service = QdrantService()
    count = service.count_documents_by_year(2020)
    
    assert count == 42
    mock_client.count.assert_called_once()
