import os
import logging
from data_pipeline.extractors.base import BaseExtractor

class PDFExtractor(BaseExtractor):
    def extract(self, source_path: str) -> str:
        """
        Trích xuất văn bản thô từ tệp PDF.
        """
        if not os.path.exists(source_path):
            logging.error(f"Không tìm thấy tệp PDF tại: {source_path}")
            return ""
            
        try:
            # Lazy import để tránh lỗi nếu thư viện pypdf chưa được cài
            import pypdf
            logging.info(f"Đang trích xuất văn bản từ tệp PDF: {source_path}...")
            
            reader = pypdf.PdfReader(source_path)
            text_parts = []
            for idx, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            
            full_text = "\n".join(text_parts)
            logging.info(f"Trích xuất thành công {len(reader.pages)} trang PDF.")
            return full_text
        except ImportError:
            logging.warning("Thư viện 'pypdf' chưa được cài đặt. Vui lòng cài đặt bằng: pip install pypdf")
            return ""
        except Exception as e:
            logging.error(f"Lỗi khi trích xuất PDF: {str(e)}")
            return ""
