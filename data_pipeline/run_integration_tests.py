import requests
import time
import json
import sys

def run_scenario(scenario_id, name, query, expected_cached=None):
    url = "http://127.0.0.1:8000/api/v1/chat"
    payload = {"query": query}
    
    print(f"\n==================================================")
    print(f"🚀 CHẠY KỊCH BẢN: {scenario_id} - {name}")
    print(f"Câu hỏi: '{query}'")
    print(f"==================================================")
    
    start_time = time.time()
    try:
        r = requests.post(url, json=payload, timeout=90)
    except Exception as e:
        print(f"❌ Lỗi kết nối tới Server API: {e}")
        print("Vui lòng đảm bảo backend FastAPI đang chạy trên cổng 8000 tại 127.0.0.1.")
        sys.exit(1)
        
    duration = (time.time() - start_time) * 1000
    
    if r.status_code == 200:
        data = r.json()
        print(f"✅ THÀNH CÔNG (Status 200) | Thời gian phản hồi: {duration:.2f} ms")
        print(f"🔍 Từ khóa pháp lý đối chiếu (Query Rewritten): '{data.get('query_rewritten')}'")
        print(f"📦 Cơ sở điều khoản tìm thấy (Qdrant Chunks): {data.get('chunks_count')}")
        print(f"🕸️ Mối liên kết văn bản hệ thống (Neo4j Relations): {data.get('graph_relations_count')}")
        
        # In chi tiết các quan hệ tìm thấy từ Neo4j
        graph_context = data.get("graph_context", [])
        if graph_context:
            print("\n--- Chi tiết các mối quan hệ trên đồ thị Neo4j ---")
            for idx, gc in enumerate(graph_context, 1):
                goc_so_hieu = gc.get("goc_so_hieu") or "Không rõ"
                goc_doc_id = gc.get("goc_doc_id")
                print(f"  📌 Nhóm {idx}: Gốc [ID: {goc_doc_id}, Số hiệu: {goc_so_hieu}] (Hiệu lực: {gc.get('goc_tinh_trang_hieu_luc')})")
                
                # Văn bản thay thế
                thong_tin_thay_the = gc.get("thong_tin_thay_the", [])
                if thong_tin_thay_the:
                    print("    🔄 Bị thay thế/sửa đổi bởi:")
                    for sub in thong_tin_thay_the:
                        print(f"      - ID: {sub.get('doc_id')}, Số hiệu: {sub.get('so_hieu')}, Tiêu đề: {sub.get('tieu_de')}")
                
                # Văn bản hướng dẫn
                van_ban_huong_dan = gc.get("van_ban_huong_dan", [])
                if van_ban_huong_dan:
                    print("    📜 Văn bản hướng dẫn liên quan:")
                    for sub in van_ban_huong_dan:
                        print(f"      - ID: {sub.get('doc_id')}, Số hiệu: {sub.get('so_hieu')}, Tiêu đề: {sub.get('tieu_de')} ({sub.get('hieu_luc')})")
                
                # Quan hệ liên quan khác
                quan_he_lien_quan = gc.get("quan_he_lien_quan", [])
                if quan_he_lien_quan:
                    print("    🔗 Các mối quan hệ liên kết khác:")
                    for sub in quan_he_lien_quan:
                        print(f"      - Loại: {sub.get('loai_quan_he')}, Số hiệu: {sub.get('so_hieu')}, Tiêu đề: {sub.get('tieu_de')} ({sub.get('hieu_luc')})")
        
        # In một phần câu trả lời
        answer = data.get('answer', '')
        print("\n--- Câu trả lời tóm tắt ---")
        lines = answer.split('\n')
        for line in lines[:8]:
            print(f"  {line}")
        if len(lines) > 8:
            print("  ...")
            
        # In nguồn trích dẫn
        print("\n--- Kiểm tra tiêu chuẩn Nguồn Trích Dẫn ---")
        if "### 📄 CƠ SỞ PHÁP LÝ VÀ NGUỒN TRÍCH DẪN" in answer:
            print("🎯 ĐẠT TIÊU CHUẨN: Tìm thấy tiêu đề '### 📄 CƠ SỞ PHÁP LÝ VÀ NGUỒN TRÍCH DẪN' trong câu trả lời.")
            # Tìm phần trích dẫn
            parts = answer.split("### 📄 CƠ SỞ PHÁP LÝ VÀ NGUỒN TRÍCH DẪN")
            print(parts[1].strip()[:400] + "\n..." if len(parts[1].strip()) > 400 else parts[1].strip())
        else:
            print("⚠️ CẢNH BÁO: Không tìm thấy tiêu đề '### 📄 CƠ SỞ PHÁP LÝ VÀ NGUỒN TRÍCH DẪN' ở cuối phản hồi.")
            
        return data, duration
    else:
        print(f"❌ THẤT BẠI (Status {r.status_code})")
        print(r.text)
        return None, duration

if __name__ == "__main__":
    print("=== CHƯƠNG TRÌNH XÁC THỰC BỘ DỮ LIỆU KIỂM THỬ RAG ===")
    
    # TC-001: Kiểm tra tính Chống Ảo Giác và Bộ lọc Auto-Healing Citation
    query_1 = "Quy định về hệ thống kiểm soát nội bộ của ngân hàng thương mại được nêu tại văn bản nào ban hành gần đây? Trích dẫn chính xác số hiệu."
    run_scenario("TC-001", "Kiểm tra chống ảo giác & Auto-Healing Citations", query_1)
    
    # TC-002: Kiểm tra Tốc độ Bộ đệm Phản hồi (Lần 1 - Cache Miss)
    query_2 = "Điều kiện để một văn bản pháp luật được coi là hết hiệu lực hoàn toàn là gì?"
    print("\n--- TC-002: LẦN 1 (Cache Miss) ---")
    data_2_miss, dur_2_miss = run_scenario("TC-002 [Lần 1]", "Xác thực bộ đệm phản hồi - Lần 1 (Cache Miss)", query_2)
    
    # TC-002: Kiểm tra Tốc độ Bộ đệm Phản hồi (Lần 2 - Cache Hit)
    print("\n--- TC-002: LẦN 2 (Cache Hit) ---")
    data_2_hit, dur_2_hit = run_scenario("TC-002 [Lần 2]", "Xác thực bộ đệm phản hồi - Lần 2 (Cache Hit)", query_2)
    
    if dur_2_hit < dur_2_miss:
        reduction = ((dur_2_miss - dur_2_hit) / dur_2_miss) * 100
        print(f"\n⚡ HIỆU QUẢ REDIS CACHE: Giảm thời gian phản hồi {reduction:.2f}% (Từ {dur_2_miss:.1f}ms xuống {dur_2_hit:.1f}ms!)")
    else:
        print("\n⚠️ Thời gian lần 2 không giảm, vui lòng kiểm tra trạng thái hoạt động của Redis.")
        
    # TC-003: Kiểm tra Khả năng Từ chối An toàn ngoài Biên dữ liệu (No-Data Boundary)
    query_3 = "Quy định về việc đăng ký bản quyền hình ảnh kỹ thuật số theo Đạo luật DMCA của Mỹ như thế nào?"
    run_scenario("TC-003", "Kiểm tra từ chối an toàn ngoài biên dữ liệu", query_3)
    
    # TC-004: Kiểm tra Khả năng Xử lý Song song & Distributed Lock
    print("\n\n==================================================")
    print("🔄 TC-004: KIỂM TRA XỬ LÝ SONG SONG (CONCURRENT TEST)")
    print("==================================================")
    print("Bắn đồng thời 3 requests: 2 câu trùng nhau + 1 câu khác biệt")
    print("Kỳ vọng: Tất cả trả về 200 OK, request trùng thứ 2 nhanh hơn nhờ Lock/Cache")
    print("==================================================")
    
    try:
        import asyncio
        import httpx
        
        async def fire_concurrent_requests():
            url = "http://127.0.0.1:8000/api/v1/chat"
            
            # 2 câu trùng nhau + 1 câu khác biệt
            duplicate_query = "Quy định về vốn điều lệ của doanh nghiệp theo Luật Doanh nghiệp?"
            different_query = "Thủ tục đăng ký kinh doanh cho doanh nghiệp tư nhân được quy định như thế nào?"
            
            requests_config = [
                ("REQ-A (Gốc)", {"query": duplicate_query}),
                ("REQ-B (Trùng A)", {"query": duplicate_query}),
                ("REQ-C (Khác biệt)", {"query": different_query}),
            ]
            
            async def send_request(client, label, payload):
                start = time.time()
                try:
                    resp = await client.post(url, json=payload, timeout=90.0)
                    duration = (time.time() - start) * 1000
                    status = resp.status_code
                    data = resp.json() if status == 200 else {}
                    return {
                        "label": label,
                        "status": status,
                        "duration_ms": duration,
                        "answer_len": len(data.get("answer", "")),
                        "chunks_count": data.get("chunks_count", 0),
                    }
                except Exception as e:
                    duration = (time.time() - start) * 1000
                    return {
                        "label": label,
                        "status": "ERROR",
                        "duration_ms": duration,
                        "error": str(e),
                    }
            
            async with httpx.AsyncClient() as client:
                # Bắn đồng thời cả 3 requests
                tasks = [
                    send_request(client, label, payload) 
                    for label, payload in requests_config
                ]
                results = await asyncio.gather(*tasks)
            
            return results
        
        concurrent_results = asyncio.run(fire_concurrent_requests())
        
        # In kết quả
        all_success = True
        for r in concurrent_results:
            status_emoji = "✅" if r["status"] == 200 else "❌"
            print(f"\n  {status_emoji} {r['label']}: Status={r['status']} | "
                  f"Thời gian: {r['duration_ms']:.0f}ms | "
                  f"Độ dài trả lời: {r.get('answer_len', 0)} ký tự | "
                  f"Chunks: {r.get('chunks_count', 0)}")
            if r.get("error"):
                print(f"     ⚠️ Lỗi: {r['error']}")
            if r["status"] != 200:
                all_success = False
        
        # Phân tích kết quả Lock/Cache
        req_a = concurrent_results[0]  # Gốc
        req_b = concurrent_results[1]  # Trùng
        
        if req_a["status"] == 200 and req_b["status"] == 200:
            if req_b["duration_ms"] < req_a["duration_ms"]:
                savings = ((req_a["duration_ms"] - req_b["duration_ms"]) / req_a["duration_ms"]) * 100
                print(f"\n  🔒 DISTRIBUTED LOCK HIỆU QUẢ: Request trùng (REQ-B) nhanh hơn {savings:.1f}% "
                      f"({req_a['duration_ms']:.0f}ms → {req_b['duration_ms']:.0f}ms)")
            else:
                print(f"\n  ℹ️ REQ-B không nhanh hơn REQ-A (có thể do REQ-A hoàn thành trước khi REQ-B gửi). "
                      f"Cả hai đều trả về 200 OK thành công.")
        
        if all_success:
            print("\n  🎯 TC-004 ĐẠT: Tất cả 3 requests đồng thời đều trả về 200 OK ổn định!")
        else:
            print("\n  ❌ TC-004 THẤT BẠI: Một hoặc nhiều requests gặp lỗi khi xử lý đồng thời.")
            
    except ImportError:
        print("\n  ⚠️ Cần cài đặt thư viện httpx: pip install httpx")
        print("  Bỏ qua TC-004.")
    except Exception as e:
        print(f"\n  ❌ Lỗi khi chạy TC-004: {str(e)}")

