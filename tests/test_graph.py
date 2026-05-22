import pytest
from unittest.mock import MagicMock, patch
from app.services.graph_service import GraphService

@patch("app.services.graph_service.GraphDatabase")
def test_get_related_documents(mock_graph_database):
    """Test truy vấn các văn bản liên quan từ Neo4j GraphService với driver giả lập."""
    # Setup mock driver và session
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_graph_database.driver.return_value = mock_driver
    mock_driver.session.return_value.__enter__.return_value = mock_session
    
    # Giả lập dữ liệu trả về từ session.run
    mock_record1 = MagicMock()
    mock_record1.data.return_value = {
        "quan_he": "VAN_BAN_SUA_DOI",
        "doc_id": 9999,
        "so_hieu": "100/2021/QH14",
        "tieu_de": "Luật sửa đổi Luật Doanh nghiệp",
        "hieu_luc": "Còn hiệu lực",
        "ngay_ban_hanh": "2021-11-20"
    }
    
    # Định nghĩa side_effect thông minh phân biệt RETURN 1 và truy vấn chính
    def run_side_effect(query, *args, **kwargs):
        if "RETURN 1" in query:
            return MagicMock()
        return [mock_record1]
        
    mock_session.run.side_effect = run_side_effect
    
    # Chạy test
    service = GraphService()
    related = service.get_related_documents(12345)
    
    # Assertions
    assert len(related) == 1
    assert related[0]["doc_id"] == 9999
    assert related[0]["quan_he"] == "VAN_BAN_SUA_DOI"
    assert related[0]["hieu_luc"] == "Còn hiệu lực"
    assert mock_session.run.call_count == 2

@patch("app.services.graph_service.GraphDatabase")
def test_get_guidance_documents(mock_graph_database):
    """Test truy vấn các văn bản hướng dẫn thi hành từ Neo4j GraphService."""
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_graph_database.driver.return_value = mock_driver
    mock_driver.session.return_value.__enter__.return_value = mock_session
    
    mock_record = MagicMock()
    mock_record.data.return_value = {
        "doc_id": 8888,
        "so_hieu": "01/2021/ND-CP",
        "tieu_de": "Nghị định hướng dẫn Luật Doanh nghiệp",
        "hieu_luc": "Còn hiệu lực"
    }
    
    def run_side_effect(query, *args, **kwargs):
        if "RETURN 1" in query:
            return MagicMock()
        return [mock_record]
        
    mock_session.run.side_effect = run_side_effect
    
    service = GraphService()
    guidance = service.get_guidance_documents(12345)
    
    assert len(guidance) == 1
    assert guidance[0]["doc_id"] == 8888
    assert guidance[0]["so_hieu"] == "01/2021/ND-CP"
    assert mock_session.run.call_count == 2

@patch("app.services.graph_service.GraphDatabase")
def test_check_validity_and_replacements(mock_graph_database):
    """Test kiểm tra tính hiệu lực và tài liệu thay thế của văn bản pháp luật."""
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_graph_database.driver.return_value = mock_driver
    mock_driver.session.return_value.__enter__.return_value = mock_session
    
    # Giả lập cho các lần gọi session.run trong check_validity_and_replacements
    mock_res_status = MagicMock()
    mock_record_status = {
        "hieu_luc": "Hết hiệu lực",
        "so_hieu": "59/2014/QH13"
    }
    mock_res_status.single.return_value = mock_record_status
    
    mock_res_repl = MagicMock()
    mock_record_repl = MagicMock()
    mock_record_repl.data.return_value = {
        "doc_id": 12345,
        "so_hieu": "59/2020/QH14",
        "tieu_de": "Luật Doanh nghiệp 2020"
    }
    mock_res_repl.__iter__.return_value = [mock_record_repl]
    
    def run_side_effect(query, *args, **kwargs):
        if "RETURN 1" in query:
            return MagicMock()
        elif "d.tinh_trang_hieu_luc as hieu_luc" in query:
            return mock_res_status
        else:
            return mock_res_repl
            
    mock_session.run.side_effect = run_side_effect
    
    service = GraphService()
    status_info = service.check_validity_and_replacements(77777)
    
    assert status_info["tinh_trang_hieu_luc"] == "Hết hiệu lực"
    assert len(status_info["bi_thay_the_boi"]) == 1
    assert status_info["bi_thay_the_boi"][0]["doc_id"] == 12345
    assert status_info["bi_thay_the_boi"][0]["so_hieu"] == "59/2020/QH14"
    assert mock_session.run.call_count == 3
