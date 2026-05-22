import os
import sys
import argparse
import logging
import pandas as pd
from typing import List, Dict, Any

# Bổ sung thư mục gốc vào Python Path để chạy file độc lập không bị ModuleNotFoundError
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_pipeline.extractors.parquet_ext import ParquetExtractor
from data_pipeline.transformers.cleaner import TextCleaner
from data_pipeline.transformers.chunker import LegalTextChunker
from data_pipeline.transformers.legal_metadata import MetadataTransformer
from data_pipeline.loaders.qdrant_loader import QdrantLoader
from data_pipeline.loaders.neo4j_loader import Neo4jLoader

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def main():
    parser = argparse.ArgumentParser(description="Vietnamese Legal GraphRAG Data Ingestion Pipeline")
    parser.add_argument("--sample-size", type=int, default=None, help="Số lượng bản ghi mẫu cần nạp để test (mặc định là nạp toàn bộ)")
    parser.add_argument("--skip-qdrant", action="store_true", help="Bỏ qua nạp vào Qdrant Cloud")
    parser.add_argument("--skip-neo4j", action="store_true", help="Bỏ qua nạp vào Neo4j")
    parser.add_argument("--collection", type=str, default=None, help="Tên collection Qdrant tùy chỉnh")
    parser.add_argument("--content-path", type=str, default="D:/cv/mo_n8n/VietNam_Legal_rag_n8n/data/raw/legal_content.parquet", help="Đường dẫn file content")
    parser.add_argument("--metadata-path", type=str, default="D:/cv/mo_n8n/VietNam_Legal_rag_n8n/data/raw/legal_metadata.parquet", help="Đường dẫn file metadata")
    parser.add_argument("--relations-path", type=str, default="D:/cv/mo_n8n/VietNam_Legal_rag_n8n/data/raw/legal_relationships.parquet", help="Đường dẫn file relationships")
    args = parser.parse_args()

    logging.info("=== BẮT ĐẦU PIPELINE NHẬP DỮ LIỆU PHÁP LUẬT VIỆT NAM ===")
    
    # 1. TRÍCH XUẤT (EXTRACT)
    extractor = ParquetExtractor()
    
    logging.info("Đang đọc dữ liệu metadata...")
    df_meta_raw = extractor.extract(args.metadata_path)
    if df_meta_raw.empty:
        logging.error("Không có dữ liệu metadata! Kết thúc pipeline.")
        return
        
    logging.info("Đang đọc dữ liệu content...")
    df_content_raw = extractor.extract(args.content_path)
    if df_content_raw.empty:
        logging.error("Không có dữ liệu content! Kết thúc pipeline.")
        return
        
    logging.info("Đang đọc dữ liệu relationships...")
    df_rel_raw = extractor.extract(args.relations_path)

    # 2. XỬ LÝ LẤY MẪU (SAMPLING) NẾU CÓ
    if args.sample_size:
        logging.info(f"Chế độ chạy mẫu: Chỉ lấy {args.sample_size} văn bản đầu tiên.")
        df_meta = df_meta_raw.head(args.sample_size).copy()
        # Lọc content tương ứng với danh sách metadata mẫu
        sample_ids = set(df_meta["id"].tolist())
        # Tránh lỗi kiểu dữ liệu khi so khớp id
        df_content_raw["id_str"] = df_content_raw["id"].astype(str)
        sample_ids_str = {str(i) for i in sample_ids}
        df_content = df_content_raw[df_content_raw["id_str"].isin(sample_ids_str)].copy()
        df_content.drop(columns=["id_str"], inplace=True)
    else:
        df_meta = df_meta_raw.copy()
        df_content = df_content_raw.copy()

    logging.info(f"Dữ liệu sau khi lọc - Metadata: {df_meta.shape[0]} dòng, Content: {df_content.shape[0]} dòng.")

    # 3. BIẾN ĐỔI (TRANSFORM) METADATA VÀ CHUNKS
    logging.info("--- Bắt đầu giai đoạn biến đổi dữ liệu (Transform) ---")
    
    # Chuyển đổi metadata thành dict để tra cứu nhanh
    meta_dict = {}
    nodes_to_load = []
    
    for _, row in df_meta.iterrows():
        try:
            transformed = MetadataTransformer.transform_row(row)
            doc_id = transformed["id"]
            meta_dict[doc_id] = transformed
            
            # Neo4j Node dict
            nodes_to_load.append({
                "id": doc_id,
                "title": transformed["title"],
                "so_ky_hieu": transformed["so_ky_hieu"],
                "tinh_trang_hieu_luc": transformed["tinh_trang_hieu_luc"],
                "loai_van_ban": transformed["loai_van_ban"],
                "ngay_ban_hanh": str(transformed["ngay_ban_hanh"]) if transformed["ngay_ban_hanh"] else ""
            })
        except Exception as e:
            logging.warning(f"Lỗi biến đổi metadata tại dòng ID {row.get('id')}: {e}")

    # Chuyển đổi và cắt nhỏ văn bản (HTML Clean & Chunk)
    chunks_to_load = []
    chunker = LegalTextChunker(chunk_size=1000, chunk_overlap=150)
    
    # Chuẩn hóa id của df_content thành int để khớp với metadata
    df_content["doc_id_clean"] = pd.to_numeric(df_content["id"], errors="coerce")
    
    logging.info("Đang tiến hành làm sạch HTML và cắt đoạn văn bản pháp luật...")
    for _, row in df_content.iterrows():
        doc_id = row["doc_id_clean"]
        if pd.isna(doc_id):
            continue
        doc_id = int(doc_id)
        
        # Chỉ chunk các văn bản nằm trong tập metadata đã lọc
        if doc_id not in meta_dict:
            continue
            
        html_content = row.get("content_html", "")
        if not html_content:
            continue
            
        clean_text = TextCleaner.clean_html(html_content)
        chunks = chunker.split_text(clean_text)
        
        for idx, ch in enumerate(chunks):
            chunks_to_load.append({
                "doc_id": doc_id,
                "chunk_index": idx,
                "content": ch,
                "metadata": meta_dict[doc_id]
            })

    logging.info(f"Biến đổi hoàn tất! Tạo ra tổng cộng {len(chunks_to_load)} text chunks.")

    # 4. NẠP DỮ LIỆU (LOAD)
    
    # 4.1 Nạp Qdrant Cloud
    if not args.skip_qdrant:
        logging.info("--- Bắt đầu nạp dữ liệu vào Qdrant Cloud ---")
        try:
            q_loader = QdrantLoader(collection_name=args.collection)
            q_loader.create_collection_if_not_exists()
            total_qdrant = q_loader.upsert_chunks_batch(chunks_to_load, batch_size=50)
            logging.info(f"Hoàn thành nạp Qdrant: Đã nạp thành công {total_qdrant} points.")
        except Exception as e:
            logging.error(f"Lỗi nạp Qdrant Cloud: {e}", exc_info=True)
    else:
        logging.info("Bỏ qua giai đoạn nạp Qdrant theo tùy chọn --skip-qdrant.")

    # 4.2 Nạp Neo4j Graph
    if not args.skip_neo4j and not df_rel_raw.empty:
        logging.info("--- Bắt đầu nạp dữ liệu vào Neo4j Database ---")
        try:
            n_loader = Neo4jLoader()
            if n_loader.driver:
                n_loader.create_constraints()
                
                # Nạp các node văn bản pháp luật trước
                logging.info(f"Đang nạp {len(nodes_to_load)} nodes vào Neo4j...")
                total_nodes = n_loader.load_nodes_batch(nodes_to_load, batch_size=500)
                logging.info(f"Đã nạp {total_nodes} nodes.")
                
                # Lọc và nạp các mối quan hệ (Relationships) tương ứng
                logging.info("Đang lọc và chuẩn bị nạp các quan hệ...")
                # Chuẩn hóa kiểu dữ liệu cho cột doc_id và other_doc_id của df_rel
                df_rel_raw["doc_id_clean"] = pd.to_numeric(df_rel_raw["doc_id"], errors="coerce")
                df_rel_raw["other_doc_id_clean"] = pd.to_numeric(df_rel_raw["other_doc_id"], errors="coerce")
                
                # Nếu chạy chế độ mẫu, chỉ giữ các quan hệ mà cả 2 đầu node đều nằm trong danh sách mẫu
                if args.sample_size:
                    df_rel = df_rel_raw[
                        df_rel_raw["doc_id_clean"].isin(sample_ids) & 
                        df_rel_raw["other_doc_id_clean"].isin(sample_ids)
                    ].copy()
                else:
                    # Chạy toàn bộ: bỏ qua các dòng quan hệ bị lỗi chuyển đổi ID
                    df_rel = df_rel_raw.dropna(subset=["doc_id_clean", "other_doc_id_clean"]).copy()
                    
                relationships_to_load = []
                for _, row in df_rel.iterrows():
                    relationships_to_load.append({
                        "doc_id": int(row["doc_id_clean"]),
                        "other_doc_id": int(row["other_doc_id_clean"]),
                        "quan_he": str(row.get("relationship") or row.get("quan_he") or "Liên quan").strip()
                    })
                    
                logging.info(f"Đang nạp {len(relationships_to_load)} quan hệ vào Neo4j...")
                total_rels = n_loader.load_relationships_batch(relationships_to_load, batch_size=500)
                logging.info(f"Nạp hoàn tất: Đã nạp thành công {total_rels} quan hệ.")
            else:
                logging.error("Không thể kết nối đến driver Neo4j. Bỏ qua nạp Graph.")
        except Exception as e:
            logging.error(f"Lỗi nạp Neo4j Graph: {e}", exc_info=True)
    else:
        if args.skip_neo4j:
            logging.info("Bỏ qua giai đoạn nạp Neo4j theo tùy chọn --skip-neo4j.")
        else:
            logging.warning("Không tìm thấy dữ liệu quan hệ hợp lệ để nạp.")

    logging.info("=== HOÀN THÀNH PIPELINE NHẬP DỮ LIỆU PHÁP LUẬT VIỆT NAM ===")

if __name__ == "__main__":
    main()
