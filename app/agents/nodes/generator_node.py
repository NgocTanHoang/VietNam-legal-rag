import os
import logging
from typing import Dict, Any
from langchain_core.messages import SystemMessage, AIMessage
from app.services.llm_service import LLMService
from app.agents.state import AgentState

def generator_node(state: AgentState) -> Dict[str, Any]:
    """
    Node tổng hợp thông tin và sinh câu trả lời bằng LLM (Gemini).
    Đọc Prompt hệ thống từ file prompts/system_prompt.txt và tiêm ngữ cảnh Vector + Graph vào.
    """
    logging.info("--- Nodes LangGraph: Đang tổng hợp câu trả lời qua LLM ---")
    
    # 1. Định dạng Vector Context thành chuỗi văn bản rõ ràng
    context_chunks = state.get("context_chunks", [])
    vector_context_str = "Không tìm thấy dữ liệu vector phù hợp."
    if context_chunks:
        chunks_list = []
        for idx, c in enumerate(context_chunks):
            chunks_list.append(
                f"[{idx+1}] Văn bản: {c.get('title')}\n"
                f"Số hiệu: {c.get('so_ky_hieu') or 'Chưa cập nhật'}\n"
                f"Trạng thái hiệu lực: {c.get('tinh_trang_hieu_luc') or 'Còn hiệu lực'}\n"
                f"Nội dung điều luật: {c.get('content')}"
            )
        vector_context_str = "\n\n".join(chunks_list)

    # 2. Định dạng Graph Context thành chuỗi văn bản rõ ràng
    graph_context = state.get("graph_context", [])
    graph_context_str = "Không có thông tin quan hệ đồ thị Neo4j liên quan (Có thể chạy ở chế độ Fallback RAG)."
    if graph_context:
        graph_list = []
        for gc in graph_context:
            summary = (
                f"- Văn bản gốc ID {gc.get('goc_doc_id')} (Số hiệu: {gc.get('goc_so_hieu')}) "
                f"có trạng thái hiệu lực thực tế: '{gc.get('goc_tinh_trang_hieu_luc') or 'Còn hiệu lực'}'.\n"
            )
            
            # Liệt kê văn bản thay thế/sửa đổi
            if gc.get("thong_tin_thay_the"):
                summary += "  => CẢNH BÁO BỊ THAY THẾ/SỬA ĐỔI BỞI:\n"
                for rep in gc.get("thong_tin_thay_the"):
                    summary += f"    * Văn bản: {rep.get('title')} (Số hiệu: {rep.get('so_hieu')})\n"
                    
            # Liệt kê các văn bản hướng dẫn chi tiết
            if gc.get("van_ban_huong_dan"):
                summary += "  => VĂN BẢN HƯỚNG DẪN THI HÀNH (THÔNG TƯ/NGHỊ ĐỊNH CHI TIẾT):\n"
                for gd in gc.get("van_ban_huong_dan"):
                    summary += f"    * Văn bản ID {gd.get('doc_id')} - Số hiệu: {gd.get('so_hieu')} (Hiệu lực: {gd.get('hieu_luc')}) - Tiêu đề: {gd.get('tieu_de')}\n"
                    
            # Liệt kê các quan hệ khác
            if gc.get("quan_he_lien_quan"):
                summary += "  => CÁC QUAN HỆ KHÁC:\n"
                for r in gc.get("quan_he_lien_quan")[:5]: # Giới hạn 5 quan hệ phụ tránh tràn token
                    summary += f"    * [{r.get('loai_quan_he')}] Văn bản {r.get('so_hieu')} ({r.get('hieu_luc')}) - {r.get('tieu_de')}\n"
                    
            graph_list.append(summary)
        graph_context_str = "\n".join(graph_list)

    # 3. Đọc System Prompt từ file tập trung
    prompt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "prompts", "system_prompt.txt")
    system_prompt = "Bạn là trợ lý luật sư AI chuyên nghiệp. Hãy trả lời câu hỏi dựa trên tài liệu pháp lý."
    
    if os.path.exists(prompt_path):
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                system_prompt = f.read()
        except Exception as e:
            logging.error(f"Lỗi khi đọc file system_prompt.txt: {str(e)}")
            
    # Tiêm biến ngữ cảnh vào prompt
    system_prompt_formatted = system_prompt.format(
        vector_context=vector_context_str,
        graph_context=graph_context_str
    )

    # 4. Gửi yêu cầu đến LLM Service
    llm_service = LLMService()
    
    # Chuẩn bị luồng tin nhắn (System prompt đi trước, sau đó là lịch sử hội thoại)
    messages = [SystemMessage(content=system_prompt_formatted)] + state.get("messages", [])
    
    try:
        response_text = llm_service.generate_response(messages)
        
        # [VALIDATION] Đảm bảo cấu trúc trích dẫn chuẩn hóa luôn hiện diện ở cuối bài
        citation_header = "### 📄 CƠ SỞ PHÁP LÝ VÀ NGUỒN TRÍCH DẪN"
        if citation_header not in response_text:
            logging.warning("Phản hồi từ LLM thiếu tiêu đề trích dẫn bắt buộc. Đang tiến hành bổ sung tự động từ dữ liệu ngữ cảnh...")
            citations = []
            # Trích xuất nguồn thực tế đã dùng từ context_chunks để sinh nguồn trích dẫn
            seen_docs = set()
            for c in context_chunks:
                doc_title = c.get('title') or "Văn bản pháp luật"
                so_hieu = c.get('so_ky_hieu') or "Chưa cập nhật"
                hieu_luc = c.get('tinh_trang_hieu_luc') or "Còn hiệu lực"
                if not hieu_luc.startswith("["):
                    hieu_luc = f"[{hieu_luc}]"
                
                doc_key = f"{doc_title}_{so_hieu}"
                if doc_key not in seen_docs:
                    seen_docs.add(doc_key)
                    citations.append(f"* **{doc_title}** | Số hiệu: `{so_hieu}` | Trạng thái: {hieu_luc}")
            
            if citations:
                response_text += f"\n\n{citation_header}\n" + "\n".join(citations)
            else:
                response_text += f"\n\n{citation_header}\n* *Không có dữ liệu trích dẫn chi tiết.*"

        # Trả về kết quả cập nhật trạng thái Graph
        # messages mới sẽ tự động được append nhờ cấu trúc Annotated của LangGraph
        return {
            "answer": response_text,
            "messages": [AIMessage(content=response_text)]
        }
    except Exception as e:
        error_msg = f"Rất tiếc, đã xảy ra lỗi khi tổng hợp câu trả lời từ AI. Chi tiết: {str(e)}"
        return {
            "answer": error_msg,
            "messages": [AIMessage(content=error_msg)]
        }
