import re
import logging
from bs4 import BeautifulSoup

class TextCleaner:
    @staticmethod
    def clean_html(html_content: str) -> str:
        """
        Làm sạch nội dung HTML thô từ Parquet, loại bỏ thẻ HTML 
        và định dạng lại văn bản pháp luật sạch sẽ.
        """
        if not html_content or not isinstance(html_content, str):
            return ""
            
        try:
            # 1. Sử dụng BeautifulSoup để phân tích cú pháp HTML
            soup = BeautifulSoup(html_content, "html.parser")
            
            # Loại bỏ các thẻ rác không dùng đến
            for junk in soup(["script", "style", "head", "title", "meta"]):
                junk.decompose()
                
            # Xử lý định dạng bảng biểu (nếu có) thành markdown đơn giản
            for table in soup.find_all("table"):
                markdown_table = []
                for row in table.find_all("tr"):
                    cells = [cell.get_text(strip=True) for cell in row.find_all(["td", "th"])]
                    if cells:
                        markdown_table.append("| " + " | ".join(cells) + " |")
                if markdown_table:
                    # Gán chuỗi bảng markdown thay cho thẻ table thô
                    table_str = "\n" + "\n".join(markdown_table) + "\n"
                    table.replace_with(table_str)

            # 2. Lấy văn bản thô sau khi xử lý
            text = soup.get_text()
            
            # 3. Chuẩn hóa khoảng trắng dư thừa
            text = re.sub(r'[ \t]+', ' ', text) # Gộp dấu cách
            text = re.sub(r'\n\s*\n+', '\n\n', text) # Gộp nhiều dòng trống
            
            return text.strip()
        except Exception as e:
            logging.error(f"Lỗi khi làm sạch HTML: {str(e)}")
            # Trả về chuỗi regex fallback thô nếu bs4 lỗi
            clean = re.sub(r'<[^>]*>', '', html_content)
            return clean.strip()
