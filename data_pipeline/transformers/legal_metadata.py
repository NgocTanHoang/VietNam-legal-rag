import re
import pandas as pd
import logging
from typing import Dict, Any, Optional

class MetadataTransformer:
    @staticmethod
    def extract_year(date_str: Optional[str]) -> Optional[int]:
        """Trích xuất năm từ chuỗi ngày tháng dạng YYYY-MM-DD hoặc DD/MM/YYYY"""
        if not date_str or not isinstance(date_str, str):
            return None
            
        # Tìm cụm 4 chữ số liên tục đại diện cho năm
        match = re.search(r'\b(19|20)\d{2}\b', date_str)
        if match:
            return int(match.group(0))
        return None

    @classmethod
    def transform_row(cls, row: pd.Series) -> Dict[str, Any]:
        """
        Chuyển đổi một dòng dữ liệu từ DataFrame legal_metadata thành 
        cấu trúc Python dictionary chuẩn hóa và sạch sẽ.
        """
        row_dict = row.to_dict()
        
        # Đọc ngày ban hành
        ngay_ban_hanh = row_dict.get("ngay_ban_hanh")
        if pd.isna(ngay_ban_hanh):
            ngay_ban_hanh = None
            
        # Trích xuất năm ban hành để hỗ trợ filter Qdrant nhanh
        nam_ban_hanh = cls.extract_year(ngay_ban_hanh)
        
        return {
            "id": int(row_dict.get("id")),
            "title": str(row_dict.get("title", "")).strip(),
            "so_ky_hieu": str(row_dict.get("so_ky_hieu", "")).strip(),
            "ngay_ban_hanh": ngay_ban_hanh,
            "nam_ban_hanh": nam_ban_hanh,
            "loai_van_ban": str(row_dict.get("loai_van_ban", "")).strip() if not pd.isna(row_dict.get("loai_van_ban")) else "Luật",
            "ngay_co_hieu_luc": str(row_dict.get("ngay_co_hieu_luc", "")) if not pd.isna(row_dict.get("ngay_co_hieu_luc")) else None,
            "ngay_het_hieu_luc": str(row_dict.get("ngay_het_hieu_luc", "")) if not pd.isna(row_dict.get("ngay_het_hieu_luc")) else None,
            "nganh": str(row_dict.get("nganh", "")) if not pd.isna(row_dict.get("nganh")) else None,
            "linh_vuc": str(row_dict.get("linh_vuc", "")) if not pd.isna(row_dict.get("linh_vuc")) else None,
            "co_quan_ban_hanh": str(row_dict.get("co_quan_ban_hanh", "")) if not pd.isna(row_dict.get("co_quan_ban_hanh")) else None,
            "nguoi_ky": str(row_dict.get("nguoi_ky", "")) if not pd.isna(row_dict.get("nguoi_ky")) else None,
            "pham_vi": str(row_dict.get("pham_vi", "")) if not pd.isna(row_dict.get("pham_vi")) else "Toàn quốc",
            "tinh_trang_hieu_luc": str(row_dict.get("tinh_trang_hieu_luc", "Còn hiệu lực")).strip()
        }
