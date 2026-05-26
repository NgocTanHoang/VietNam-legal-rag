import logging
from typing import Any, Dict, List, Union

from neo4j import GraphDatabase

from app.core.config import settings


class GraphService:
    def __init__(self):
        self.driver = None

        import os

        uri = settings.NEO4J_URI
        if not os.path.exists("/.dockerenv") and "://neo4j" in uri:
            uri = uri.replace("://neo4j", "://127.0.0.1")

        try:
            self.driver = GraphDatabase.driver(
                uri,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                connection_timeout=settings.INFRA_TIMEOUT_SECONDS,
            )
            with self.driver.session(
                connection_acquisition_timeout=settings.INFRA_TIMEOUT_SECONDS
            ) as session:
                session.run("RETURN 1").single()
            logging.info("Kết nối Neo4j thành công!")
        except Exception as exc:
            logging.warning(
                f"Không thể kết nối đến cơ sở dữ liệu đồ thị Neo4j ở {settings.NEO4J_URI}. "
                f"Chi tiết lỗi: {exc}"
            )
            self.driver = None

    def close(self):
        if self.driver:
            self.driver.close()

    def __del__(self):
        self.close()

    def is_healthy(self) -> bool:
        return self.driver is not None

    def get_related_documents(self, doc_id: Union[str, int]) -> List[Dict[str, Any]]:
        if not self.driver:
            return []

        try:
            search_id = str(doc_id)
            with self.driver.session(
                connection_acquisition_timeout=settings.INFRA_TIMEOUT_SECONDS
            ) as session:
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
        except Exception as exc:
            logging.error(f"Lỗi truy vấn Neo4j (get_related_documents): {exc}")
            return []

    def get_guidance_documents(self, doc_id: Union[str, int]) -> List[Dict[str, Any]]:
        if not self.driver:
            return []

        try:
            search_id = str(doc_id)
            with self.driver.session(
                connection_acquisition_timeout=settings.INFRA_TIMEOUT_SECONDS
            ) as session:
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
        except Exception as exc:
            logging.error(f"Lỗi truy vấn Neo4j (get_guidance_documents): {exc}")
            return []

    def check_validity_and_replacements(self, doc_id: Union[str, int]) -> Dict[str, Any]:
        status_info = {
            "tinh_trang_hieu_luc": "Không rõ",
            "bi_thay_the_boi": [],
        }

        if not self.driver:
            return status_info

        try:
            search_id = str(doc_id)
            with self.driver.session(
                connection_acquisition_timeout=settings.INFRA_TIMEOUT_SECONDS
            ) as session:
                status_query = """
                MATCH (d:LegalDocument {id: $doc_id})
                RETURN d.tinh_trang_hieu_luc as hieu_luc, d.so_ky_hieu as so_hieu
                """
                res = session.run(status_query, doc_id=search_id)
                record = res.single()
                if record:
                    status_info["tinh_trang_hieu_luc"] = record["hieu_luc"] or "Không rõ"

                replacement_query = """
                MATCH (d:LegalDocument {id: $doc_id})-[r:LEGAL_RELATION]->(replacing:LegalDocument)
                WHERE r.relation_key IN ["V_N_B_N_H_T_HI_U_L_C", "V_N_B_N_QUY_NH_H_T_HI_U_L_C", "V_N_B_N_C_S_A_I", "V_N_B_N_S_A_I"]
                RETURN replacing.id as doc_id, replacing.so_ky_hieu as so_hieu, replacing.title as tieu_de
                """
                res_repl = session.run(replacement_query, doc_id=search_id)
                status_info["bi_thay_the_boi"] = [record.data() for record in res_repl]

            return status_info
        except Exception as exc:
            logging.error(f"Lỗi truy vấn Neo4j (check_validity_and_replacements): {exc}")
            return status_info
