from typing import List
import logging

class LegalTextChunker:
    def __init__(self, chunk_size: int = 1200, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> List[str]:
        """
        Cắt văn bản pháp luật thành các đoạn nhỏ chồng lấp lên nhau (Overlap).
        Cố gắng cắt tại dấu dòng mới hoặc dấu chấm câu để giữ nguyên ý nghĩa của điều khoản.
        """
        if not text:
            return []
            
        chunks = []
        text_len = len(text)
        
        # Nếu văn bản ngắn hơn kích thước chunk, trả về chính nó
        if text_len <= self.chunk_size:
            return [text]
            
        start = 0
        while start < text_len:
            end = start + self.chunk_size
            
            # Nếu chưa chạm đến cuối văn bản, tìm điểm ngắt đẹp nhất (dấu chấm câu, ngắt dòng)
            if end < text_len:
                # Tìm ngắt dòng tốt nhất trong phạm vi overlap
                best_break = -1
                search_range = text[end - self.chunk_overlap : end]
                
                # Tìm ngắt đoạn (\n\n) trước, sau đó là ngắt dòng (\n), rồi đến dấu chấm (.)
                for separator in ["\n\n", "\n", ". "]:
                    idx = search_range.rfind(separator)
                    if idx != -1:
                        best_break = (end - self.chunk_overlap) + idx + len(separator)
                        break
                        
                if best_break != -1:
                    end = best_break
            
            # Trích xuất đoạn chunk
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
                
            # Dịch chuyển start dựa trên overlap
            start = end - self.chunk_overlap
            
            # Đề phòng lặp vô tận do điểm ngắt không hợp lệ
            if start >= end:
                start = end
                
        return chunks
