import argparse
import logging
import os
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data_pipeline" / "data"
RAW_DIR = DATA_DIR / "raw"

sys.path.append(str(PROJECT_ROOT))

from data_pipeline.extractors.parquet_ext import ParquetExtractor
from data_pipeline.loaders.neo4j_loader import Neo4jLoader
from data_pipeline.loaders.qdrant_loader import QdrantLoader
from data_pipeline.transformers.chunker import LegalTextChunker
from data_pipeline.transformers.cleaner import TextCleaner
from data_pipeline.transformers.legal_metadata import MetadataTransformer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def default_data_path(filename: str) -> str:
    return str(RAW_DIR / filename)


def main():
    parser = argparse.ArgumentParser(description="Vietnamese Legal GraphRAG Data Ingestion Pipeline")
    parser.add_argument("--sample-size", type=int, default=None)
    parser.add_argument("--skip-qdrant", action="store_true")
    parser.add_argument("--skip-neo4j", action="store_true")
    parser.add_argument("--collection", type=str, default=None)
    parser.add_argument(
        "--content-path",
        type=str,
        default=os.getenv("LEGAL_CONTENT_PATH", default_data_path("legal_content.parquet")),
    )
    parser.add_argument(
        "--metadata-path",
        type=str,
        default=os.getenv("LEGAL_METADATA_PATH", default_data_path("legal_metadata.parquet")),
    )
    parser.add_argument(
        "--relations-path",
        type=str,
        default=os.getenv("LEGAL_RELATIONS_PATH", default_data_path("legal_relationships.parquet")),
    )
    args = parser.parse_args()

    extractor = ParquetExtractor()
    df_meta_raw = extractor.extract(args.metadata_path)
    df_content_raw = extractor.extract(args.content_path)
    df_rel_raw = extractor.extract(args.relations_path)

    if df_meta_raw.empty or df_content_raw.empty:
        logging.error("Thiếu dữ liệu metadata hoặc content. Kết thúc pipeline.")
        return

    if args.sample_size:
        df_meta = df_meta_raw.head(args.sample_size).copy()
        sample_ids = {str(item) for item in df_meta["id"].tolist()}
        df_content_raw["id_str"] = df_content_raw["id"].astype(str)
        df_content = df_content_raw[df_content_raw["id_str"].isin(sample_ids)].copy()
        df_content.drop(columns=["id_str"], inplace=True)
    else:
        df_meta = df_meta_raw.copy()
        df_content = df_content_raw.copy()

    meta_dict = {}
    nodes_to_load = []
    for _, row in df_meta.iterrows():
        transformed = MetadataTransformer.transform_row(row)
        meta_dict[transformed["id"]] = transformed
        nodes_to_load.append(
            {
                "id": transformed["id"],
                "title": transformed["title"],
                "so_ky_hieu": transformed["so_ky_hieu"],
                "tinh_trang_hieu_luc": transformed["tinh_trang_hieu_luc"],
                "loai_van_ban": transformed["loai_van_ban"],
                "ngay_ban_hanh": str(transformed["ngay_ban_hanh"]) if transformed["ngay_ban_hanh"] else "",
            }
        )

    chunker = LegalTextChunker(chunk_size=1000, chunk_overlap=150)
    chunks_to_load = []
    df_content["doc_id_clean"] = pd.to_numeric(df_content["id"], errors="coerce")
    for _, row in df_content.iterrows():
        doc_id = row["doc_id_clean"]
        if pd.isna(doc_id):
            continue
        doc_id = int(doc_id)
        if doc_id not in meta_dict:
            continue
        clean_text = TextCleaner.clean_html(row.get("content_html", ""))
        for idx, chunk in enumerate(chunker.split_text(clean_text)):
            chunks_to_load.append(
                {
                    "doc_id": doc_id,
                    "chunk_index": idx,
                    "content": chunk,
                    "metadata": meta_dict[doc_id],
                }
            )

    if not args.skip_qdrant:
        try:
            q_loader = QdrantLoader(collection_name=args.collection)
            q_loader.create_collection_if_not_exists()
            total_qdrant = q_loader.upsert_chunks_batch(chunks_to_load, batch_size=50)
            logging.info(f"Đã nạp {total_qdrant} points vào Qdrant.")
        except Exception as exc:
            logging.error(f"Lỗi nạp Qdrant: {exc}", exc_info=True)

    if not args.skip_neo4j and not df_rel_raw.empty:
        try:
            n_loader = Neo4jLoader()
            if n_loader.driver:
                n_loader.create_constraints()
                n_loader.load_nodes_batch(nodes_to_load, batch_size=500)
                df_rel_raw["doc_id_clean"] = pd.to_numeric(df_rel_raw["doc_id"], errors="coerce")
                df_rel_raw["other_doc_id_clean"] = pd.to_numeric(df_rel_raw["other_doc_id"], errors="coerce")
                df_rel = df_rel_raw.dropna(subset=["doc_id_clean", "other_doc_id_clean"]).copy()
                relationships_to_load = [
                    {
                        "doc_id": int(row["doc_id_clean"]),
                        "other_doc_id": int(row["other_doc_id_clean"]),
                        "quan_he": str(row.get("relationship") or row.get("quan_he") or "Liên quan").strip(),
                    }
                    for _, row in df_rel.iterrows()
                ]
                n_loader.load_relationships_batch(relationships_to_load, batch_size=500)
        except Exception as exc:
            logging.error(f"Lỗi nạp Neo4j: {exc}", exc_info=True)


if __name__ == "__main__":
    main()
