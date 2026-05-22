import logging
from typing import List, Dict, Any, Union, Optional
from neo4j import GraphDatabase
from app.core.config import settings

class GraphService:
    def __init__(self):
        """Khởi tạo Neo4j Driver với cơ chế tự động báo lỗi khi DB offline"""
        self.driver = None
        import os
        uri = settings.NEO4J_URI
        if not os.path.exists("/.dockerenv") and "://neo4j" in uri:
            uri = uri.replace("://neo4j", "://127.0.0.1")
        try:
            self.driver = GraphDatabase.driver(
                uri, 
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            # Kiểm tra nhanh kết nối bằng cách ping thử session
            with self.driver.session() as session:
                session.run("RETURN 1")
            logging.info("Kết nối Neo4j thành công!")
        except Exception as e:
            logging.warning(
                f"Không thể kết nối đến cơ sở dữ liệu đồ thị Neo4j ở {settings.NEO4J_URI}. "
                f"Vui lòng đảm bảo cụm Infra Neo4j đang chạy. Chi tiết lỗi: {str(e)}"
            )
            # Không crash ứng dụng ngay, gán driver = None để chạy chế độ Fallback RAG chỉ dùng Qdrant
            self.driver = None

    def close(self):
        if self.driver:
            self.driver.close()

    def __del__(self):
        self.close()

    def is_healthy(self) -> bool:
        return self.driver is not None

    def get_related_documents(self, doc_id: Union[str, int]) -> List[Dict[str, Any]]:
        """
        Lấy các văn bản liên quan trực tiếp đến văn bản hiện tại (chỉ theo hướng outgoing).
        Sử dụng quan hệ có hướng (->) để tránh truy ngược các văn bản không liên quan.
        """
        if not self.driver:
            return []
            
        try:
            search_id = str(doc_id)
            with self.driver.session() as session:
                query = """
                MATCH (target:LegalDocument {id: $doc_id})-[r:LEGAL_RELATION]->(related:LegalDocument)
                WHERE r.relation_key IN [
                    "V_N_B_N_HD_Q_CHI_TI_T", "V_N_B_N_C_HD_Q_CHI_TI_T", 
                    "V_N_B_N_S_A_I", "V_N_B_N_C_S_A_I", 
                    "V_N_B_N_B_SUNG", "V_N_B_N_C_B_SUNG", 
                    "V_N_B_N_H_T_HI_U_L_C", "V_N_B_N_QUY_NH_H_T_HI_U_L_C", 
                    "V_N_B_N_QUY_NH_H_T_HI_U_L_C_1_PH_N", "V_N_B_N_B_H_T_HI_U_L_C_1_PH_N", 
                    "V_N_B_N_NH_CH", "V_N_B_N_B_NH_CH", 
                    "V_N_B_N_NH_CH_1_PH_N", "V_N_B_N_B_NH_CH_1_PH_N"
                ]
                RETURN 
                    r.relationship as quan_he,
                    related.id as doc_id,
                    related.so_ky_hieu as so_hieu, 
                    related.title as tieu_de, 
                    related.tinh_trang_hieu_luc as hieu_luc,
                    related.ngay_ban_hanh as ngay_ban_hanh
                LIMIT 20
                """
                result = session.run(query, doc_id=search_id)
                return [record.data() for record in result]
        except Exception as e:
            logging.error(f"Lỗi truy vấn Neo4j (get_related_documents): {str(e)}")
            return []

    def get_guidance_documents(self, doc_id: Union[str, int]) -> List[Dict[str, Any]]:
        """
        Tìm các văn bản hướng dẫn thi hành (Văn bản HD, QĐ chi tiết) của văn bản gốc.
        """
        if not self.driver:
            return []
            
        try:
            search_id = str(doc_id)
            with self.driver.session() as session:
                query = """
                MATCH (target:LegalDocument {id: $doc_id})-[r:LEGAL_RELATION]->(guidance:LegalDocument)
                WHERE r.relation_key IN ["V_N_B_N_HD_Q_CHI_TI_T", "V_N_B_N_C_HD_Q_CHI_TI_T"]
                RETURN 
                    guidance.id as doc_id,
                    guidance.so_ky_hieu as so_hieu, 
                    guidance.title as tieu_de, 
                    guidance.tinh_trang_hieu_luc as hieu_luc
                """
                result = session.run(query, doc_id=search_id)
                return [record.data() for record in result]
        except Exception as e:
            logging.error(f"Lỗi truy vấn Neo4j (get_guidance_documents): {str(e)}")
            return []

    def check_validity_and_replacements(self, doc_id: Union[str, int]) -> Dict[str, Any]:
        """
        Kiểm tra tình trạng hiệu lực của văn bản và tìm văn bản thay thế (nếu có).
        """
        status_info = {
            "tinh_trang_hieu_luc": "Không rõ",
            "bi_thay_the_boi": []
        }
        
        if not self.driver:
            return status_info
            
        try:
            search_id = str(doc_id)
            with self.driver.session() as session:
                # 1. Lấy trạng thái của chính nó
                status_query = """
                MATCH (d:LegalDocument {id: $doc_id})
                RETURN d.tinh_trang_hieu_luc as hieu_luc, d.so_ky_hieu as so_hieu
                """
                res = session.run(status_query, doc_id=search_id)
                record = res.single()
                if record:
                    status_info["tinh_trang_hieu_luc"] = record["hieu_luc"] or "Không rõ"
                    
                # 2. Tìm văn bản thay thế (Văn bản hết hiệu lực / Văn bản sửa đổi)
                replacement_query = """
                MATCH (d:LegalDocument {id: $doc_id})-[r:LEGAL_RELATION]->(replacing:LegalDocument)
                WHERE r.relation_key IN ["V_N_B_N_H_T_HI_U_L_C", "V_N_B_N_QUY_NH_H_T_HI_U_L_C", "V_N_B_N_C_S_A_I", "V_N_B_N_S_A_I"]
                RETURN replacing.id as doc_id, replacing.so_ky_hieu as so_hieu, replacing.title as tieu_de
                """
                res_repl = session.run(replacement_query, doc_id=search_id)
                status_info["bi_thay_the_boi"] = [r.data() for r in res_repl]
                
            return status_info
        except Exception as e:
            logging.error(f"Lỗi truy vấn Neo4j (check_validity_and_replacements): {str(e)}")
            return status_info