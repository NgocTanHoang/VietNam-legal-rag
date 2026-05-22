import requests
import json

if __name__ == "__main__":
    url = "http://localhost:8000/api/v1/chat"
    payload = {
        "query": "Quy định về hệ thống kiểm soát nội bộ của ngân hàng thương mại?"
    }
    
    print("Đang gửi yêu cầu tới API...")
    r = requests.post(url, json=payload)
    
    if r.status_code == 200:
        data = r.json()
        print("\n--- KẾT QUẢ TRUY VẤN RAG THÀNH CÔNG ---")
        print(f"Câu hỏi gốc: {data['query']}")
        print(f"Câu hỏi tối ưu: {data['query_rewritten']}")
        print(f"Số lượng đoạn văn bản khớp (Qdrant): {data['chunks_count']}")
        print(f"Số lượng quan hệ đồ thị khớp (Neo4j): {data['graph_relations_count']}")
        
        # Ghi câu trả lời đầy đủ ra file TXT dưới định dạng UTF-8
        output_file = "data_pipeline/rag_response.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(data["answer"])
        print(f"\nĐã ghi câu trả lời tiếng Việt đầy đủ vào file: {output_file}")
    else:
        print(f"Lỗi API: Status {r.status_code}")
        print(r.text)
