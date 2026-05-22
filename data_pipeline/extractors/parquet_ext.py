import os
import pandas as pd
import logging
from data_pipeline.extractors.base import BaseExtractor

class ParquetExtractor(BaseExtractor):
    def extract(self, source_path: str) -> pd.DataFrame:
        """
        Trích xuất dữ liệu từ tệp Parquet.
        """
        if not os.path.exists(source_path):
            logging.error(f"Không tìm thấy tệp Parquet tại: {source_path}")
            return pd.DataFrame()
            
        try:
            logging.info(f"Đang đọc tệp Parquet: {source_path}...")
            df = pd.read_parquet(source_path)
            logging.info(f"Đọc tệp thành công! Kích thước: {df.shape}")
            return df
        except Exception as e:
            logging.error(f"Lỗi khi đọc tệp Parquet: {str(e)}")
            return pd.DataFrame()
