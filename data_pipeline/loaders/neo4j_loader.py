import logging
import re
import unicodedata
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase
from app.core.config import settings

logging.basicConfig(level=logging.INFO)

def sanitize_relationship_type(rel_type: str) -> str:
    """
    Chuẩn hóa loại quan hệ tiếng Việt thành tên quan hệ viết hoa không dấu của Neo4j.
    Ví dụ: 'Văn bản HD, QĐ chi tiết' -> 'VAN_BAN_HD_QD_CHI_TIET'
           'Văn bản sửa đổi' -> 'VAN_BAN_SUA_DOI'
    """
    if not rel_type:
        return "LIEN_QUAN"
        
    # Loại bỏ dấu tiếng Việt
    s = unicodedata.normalize('NFKD', rel_type).encode('ascii', 'ignore').decode('utf-8')
    # Thay thế các ký tự không phải chữ và số thành dấu gạch dưới
    s = re.sub(r'[^a-zA-Z0-9_]', '_', s)
    # Rút gọn nhiều dấu gạch dưới liên tiếp và viết hoa
    s = re.sub(r'_+', '_', s).strip('_').upper()
    return s or "LIEN_QUAN"

class Neo4jLoader:
    def __init__(self):
        try:
            self.driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            # Kiểm tra kết nối
            with self.driver.session() as session:
                session.run("RETURN 1")
            logging.info("Neo4jLoader kết nối thành công tới Neo4j.")
        except Exception as e:
            logging.error(f"Lỗi kết nối Neo4j trong Neo4jLoader: {e}")
            self.driver = None

    def close(self):
        if self.driver:
            self.driver.close()

    def __del__(self):
        self.close()

    def create_constraints(self):
        """Khởi tạo các ràng buộc duy nhất và chỉ mục để tối ưu hóa truy vấn."""
        if not self.driver:
            logging.warning("Neo4j driver ngoại tuyến. Bỏ qua việc tạo ràng buộc.")
            return

        queries = [
            # Tạo unique constraint cho ID của LegalDocument
            "CREATE CONSTRAINT legal_document_id IF NOT EXISTS FOR (d:LegalDocument) REQUIRE d.id IS UNIQUE",
            # Tạo index cho so_ky_hieu để tìm kiếm nhanh
            "CREATE INDEX legal_document_so_ky_hieu IF NOT EXISTS FOR (d:LegalDocument) ON (d.so_ky_hieu)"
        ]
        
        with self.driver.session() as session:
            for q in queries:
                try:
                    session.run(q)
                    logging.info(f"Đã thực thi Cypher tối ưu: {q}")
                except Exception as e:
                    logging.warning(f"Lỗi khi thực thi Cypher tối ưu (có thể do phiên bản Neo4j cũ): {e}")

    def load_nodes_batch(self, nodes: List[Dict[str, Any]], batch_size: int = 1000) -> int:
        """
        Nạp hàng loạt LegalDocument vào Neo4j bằng UNWIND.
        mỗi node trong danh sách:
        {
            "id": int,
            "title": str,
            "so_ky_hieu": str,
            "tinh_trang_hieu_luc": str,
            "loai_van_ban": str,
            "ngay_ban_hanh": str
        }
        """
        if not self.driver or not nodes:
            return 0

        query = """
        UNWIND $batch AS doc
        MERGE (d:LegalDocument {id: doc.id})
        SET d.title = doc.title,
            d.so_ky_hieu = doc.so_ky_hieu,
            d.tinh_trang_hieu_luc = doc.tinh_trang_hieu_luc,
            d.loai_van_ban = doc.loai_van_ban,
            d.ngay_ban_hanh = doc.ngay_ban_hanh
        """
        
        total_loaded = 0
        with self.driver.session() as session:
            for i in range(0, len(nodes), batch_size):
                batch = nodes[i:i + batch_size]
                try:
                    session.run(query, batch=batch)
                    total_loaded += len(batch)
                    logging.info(f"Neo4j đã nạp thành công {total_loaded}/{len(nodes)} nodes.")
                except Exception as e:
                    logging.error(f"Lỗi khi nạp nodes batch tại {i}: {e}")
                    
        return total_loaded

    def load_relationships_batch(self, relationships: List[Dict[str, Any]], batch_size: int = 1000) -> int:
        """
        Nạp hàng loạt quan hệ giữa các LegalDocument vào Neo4j.
        Mỗi quan hệ trong danh sách:
        {
            "doc_id": int,
            "other_doc_id": int,
            "quan_he": str (ví dụ: 'Văn bản HD, QĐ chi tiết')
        }
        Do Cypher không hỗ trợ truyền tham số cho nhãn quan hệ (-[r:$type]->),
        chúng ta sẽ nhóm các quan hệ theo loại đã được chuẩn hóa để tăng hiệu suất.
        """
        if not self.driver or not relationships:
            return 0

        # Nhóm quan hệ theo loại đã chuẩn hóa
        grouped_relations = {}
        for rel in relationships:
            raw_type = rel.get("quan_he") or rel.get("relation_type", "LIEN_QUAN")
            sanitized_type = sanitize_relationship_type(raw_type)
            if sanitized_type not in grouped_relations:
                grouped_relations[sanitized_type] = []
            grouped_relations[sanitized_type].append({
                "doc_id": int(rel["doc_id"]),
                "other_doc_id": int(rel["other_doc_id"])
            })

        total_loaded = 0
        with self.driver.session() as session:
            for rel_type, rel_list in grouped_relations.items():
                logging.info(f"Đang nạp {len(rel_list)} quan hệ loại: {rel_type}...")
                
                # Thực hiện nạp từng batch nhỏ cho loại quan hệ này
                query = f"""
                UNWIND $batch AS edge
                MATCH (a:LegalDocument {{id: edge.doc_id}})
                MATCH (b:LegalDocument {{id: edge.other_doc_id}})
                MERGE (a)-[:{rel_type}]->(b)
                """
                
                for i in range(0, len(rel_list), batch_size):
                    batch = rel_list[i:i + batch_size]
                    try:
                        session.run(query, batch=batch)
                        total_loaded += len(batch)
                    except Exception as e:
                        logging.error(f"Lỗi khi nạp quan hệ loại {rel_type} tại batch {i}: {e}")
                        
        logging.info(f"Neo4j đã nạp thành công tổng cộng {total_loaded} quan hệ.")
        return total_loaded
