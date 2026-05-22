import logging
import re
from typing import Dict, Any, List
from app.services.graph_service import GraphService
from app.agents.state import AgentState

def graph_node(state: AgentState) -> Dict[str, Any]:
    """
    Node tra cứu cơ sở dữ liệu đồ thị Neo4j.
    Tìm kiếm các văn bản hướng dẫn chi tiết, sửa đổi hoặc hết hiệu lực liên quan đến các kết quả vector.
    """
    chunks = state.get("context_chunks", [])
    if not chunks:
        logging.info("--- Nodes LangGraph: Không có đoạn văn bản vector để tra cứu đồ thị ---")
        return {"graph_context": []}
        
    logging.info("--- Nodes LangGraph: Đang tra cứu thực thể và quan hệ trên đồ thị Neo4j ---")
    
    graph_service = GraphService()
    if not graph_service.is_healthy():
        logging.warning("Neo4j đang offline. Bỏ qua tra cứu đồ thị (Chế độ Fallback RAG).")
        return {"graph_context": []}
        
    graph_results = []
    seen_relations = set() # Tránh trùng lặp quan hệ trùng tên
    
    # Duyệt qua tối đa 3 văn bản hàng đầu từ vector search để tra cứu sâu hơn
    for chunk in chunks[:3]:
        doc_id = chunk.get("doc_id")
        if not doc_id:
            continue
            
        # Clean and standardise doc_id to match 100% with Neo4j string ID format
        try:
            # If doc_id is float or float-like string, convert to int then string
            clean_doc_id = str(int(float(doc_id)))
        except (ValueError, TypeError):
            clean_doc_id = str(doc_id).strip()
        
        # Strip any chunk suffix (e.g., "164373_chunk_0" -> "164373")
        clean_doc_id = re.sub(r'_chunk_\d+$', '', clean_doc_id)
            
        logging.info(f"Đang tìm quan hệ đồ thị cho Văn bản [ID: {clean_doc_id}, Tiêu đề: '{chunk.get('title')}']...")
        
        # 1. Kiểm tra trạng thái hiệu lực & văn bản thay thế
        validity = graph_service.check_validity_and_replacements(clean_doc_id)
        
        # 2. Tìm các văn bản hướng dẫn chi tiết (Circulars/Decrees)
        guidances = graph_service.get_guidance_documents(clean_doc_id)
        
        # 3. Tìm các quan hệ liên quan tổng quát khác
        related = graph_service.get_related_documents(clean_doc_id)
        
        # Tổng hợp kết quả
        rel_summary = {
            "goc_doc_id": clean_doc_id,
            "goc_so_hieu": chunk.get("so_ky_hieu"),
            "goc_tinh_trang_hieu_luc": validity.get("tinh_trang_hieu_luc"),
            "thong_tin_thay_the": validity.get("bi_thay_the_boi", []),
            "van_ban_huong_dan": guidances,
            "quan_he_lien_quan": []
        }
        
        for r in related:
            rel_key = (clean_doc_id, r.get("doc_id"), r.get("quan_he"))
            if rel_key not in seen_relations:
                seen_relations.add(rel_key)
                rel_summary["quan_he_lien_quan"].append({
                    "loai_quan_he": r.get("quan_he"),
                    "so_hieu": r.get("so_hieu"),
                    "tieu_de": r.get("tieu_de"),
                    "hieu_luc": r.get("hieu_luc")
                })
                
        graph_results.append(rel_summary)
        
    logging.info(f"Hoàn thành tra cứu đồ thị. Tìm thấy {len(graph_results)} nhóm quan hệ.")
    return {"graph_context": graph_results}
