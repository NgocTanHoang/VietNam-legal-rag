import os
import sys
import logging

# Thêm root project vào sys.path để import app.*
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.nodes.retrieval_node import retrieval_node
from app.agents.state import AgentState

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    print("--- CHẠY THỬ NGHIỆM TRUY VẤN QDRANT THỰC TẾ ---")
    query = "Luật doanh nghiệp quy định thế nào về vốn điều lệ công ty cổ phần?"
    
    # Giả lập state
    state = {
        "messages": [],
        "raw_query": query,
        "query_rewritten": "",
        "context_chunks": [],
        "graph_context": [],
        "answer": "",
        "retry_count": 0
    }
    
    # Gọi retrieval_node
    print(f"Từ khóa truy vấn: '{query}'")
    result = retrieval_node(state)
    
    chunks = result.get("context_chunks", [])
    print(f"\nKết quả tìm thấy: {len(chunks)} đoạn văn bản.")
    for idx, c in enumerate(chunks):
        print(f"\n[{idx+1}] TIÊU ĐỀ: {c['title']}")
        print(f"SỐ HIỆU: {c['so_ky_hieu']}")
        print(f"NỘI DUNG (rút gọn): {c['content'][:300]}...")
        print(f"ĐỘ TƯƠNG ĐỒNG (SCORE): {c['score']}")
