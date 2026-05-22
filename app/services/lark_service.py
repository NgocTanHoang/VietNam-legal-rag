import time
import json
import logging
import requests
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from app.core.config import settings

class LarkService:
    def __init__(self):
        """Khởi tạo Lark Service với bộ nhớ đệm Token (Cache)"""
        self.app_id = settings.LARK_APP_ID
        self.app_secret = settings.LARK_APP_SECRET
        self._tenant_access_token = None
        self._token_expires_at = 0

    def get_tenant_access_token(self) -> Optional[str]:
        """
        Lấy Tenant Access Token từ Lark API. 
        Tự động sử dụng lại Token cũ nếu chưa hết hạn (Lark Token có hiệu lực 2 giờ).
        """
        if not self.app_id or not self.app_secret:
            logging.warning("LARK_APP_ID hoặc LARK_APP_SECRET chưa được cấu hình. Bỏ qua lấy Lark Token.")
            return None

        now = time.time()
        # Nếu Token còn hạn ít nhất 5 phút, dùng tiếp
        if self._tenant_access_token and self._token_expires_at - now > 300:
            return self._tenant_access_token

        url = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }

        try:
            logging.info("Đang lấy Tenant Access Token mới từ Lark Suite...")
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            data = response.json()
            
            if data.get("code") == 0:
                self._tenant_access_token = data.get("tenant_access_token")
                # Lark trả về expire tính bằng giây (thường là 7200)
                expires_in = data.get("expire", 7200)
                self._token_expires_at = now + expires_in
                logging.info("Lấy Tenant Access Token thành công!")
                return self._tenant_access_token
            else:
                logging.error(f"Lark API trả về lỗi khi lấy token: {data.get('msg')}")
                return None
        except Exception as e:
            logging.error(f"Lỗi kết nối đến Lark Suite Auth API: {str(e)}")
            return None

    def _build_interactive_card(self, text_content: str) -> Dict[str, Any]:
        """
        Xây dựng cấu trúc Interactive Card chuẩn doanh nghiệp.
        Tự động phân tách phần nội dung và phần cơ sở pháp lý để hiển thị trực quan.
        """
        # 1. Tính thời gian hiện tại theo múi giờ Việt Nam (UTC+7)
        tz_vn = timezone(timedelta(hours=7))
        time_str = datetime.now(tz_vn).strftime("%d/%m/%Y %H:%M")

        # 2. Phân tách phần câu trả lời chính và nguồn trích dẫn
        citation_header = "### 📄 CƠ SỞ PHÁP LÝ VÀ NGUỒN TRÍCH DẪN"
        citation_header_old = "### 📄 Nguồn Trích Dẫn"

        main_text = text_content.strip()
        citations_part = ""

        if citation_header in text_content:
            parts = text_content.split(citation_header)
            main_text = parts[0].strip()
            citations_part = parts[1].strip()
        elif citation_header_old in text_content:
            parts = text_content.split(citation_header_old)
            main_text = parts[0].strip()
            citations_part = parts[1].strip()

        # 3. Phân tích các nguồn trích dẫn thành cấu trúc dữ liệu
        parsed_citations = []
        if citations_part:
            raw_lines = citations_part.split("\n")
            for line in raw_lines:
                line = line.strip()
                if not line:
                    continue
                # Xóa bullet point ở đầu
                line_clean = re.sub(r'^[\s*\-]+', '', line).strip()
                if not line_clean:
                    continue
                
                parts = [p.strip() for p in line_clean.split("|")]
                
                doc_name = ""
                so_hieu = ""
                hieu_luc = ""
                other_info = ""
                
                for p in parts:
                    if p.startswith("**") and p.endswith("**"):
                        doc_name = p.replace("**", "").strip()
                    elif "Số hiệu:" in p:
                        so_hieu = p.replace("Số hiệu:", "").replace("`", "").strip()
                    elif "Trạng thái:" in p:
                        hieu_luc = p.replace("Trạng thái:", "").strip()
                    elif "Hiệu lực:" in p:
                        hieu_luc = p.replace("Hiệu lực:", "").strip()
                    else:
                        if doc_name == "":
                            doc_name = p.replace("**", "").strip()
                        else:
                            other_info = p.strip()
                            
                if doc_name or so_hieu:
                    parsed_citations.append({
                        "doc_name": doc_name or "Văn bản pháp quy",
                        "so_hieu": so_hieu or "Chưa cập nhật",
                        "hieu_luc": hieu_luc or "[Còn hiệu lực]",
                        "other_info": other_info
                    })

        # 4. Xây dựng danh sách các thành phần của Lark Card
        elements = [
            {
                "tag": "div",
                "fields": [
                    {
                        "is_short": True,
                        "text": {
                            "tag": "lark_md",
                            "content": f"**📅 Ngày tra cứu:**\n{time_str}"
                        }
                    },
                    {
                        "is_short": True,
                        "text": {
                            "tag": "lark_md",
                            "content": "**🔍 Phạm vi:**\nToàn bộ hệ thống văn bản QPPL Việt Nam"
                        }
                    }
                ]
            },
            {
                "tag": "hr"
            },
            {
                "tag": "markdown",
                "content": main_text
            }
        ]

        # 5. Nếu có nguồn trích dẫn, bổ sung khối trực quan hóa
        if parsed_citations:
            elements.append({
                "tag": "hr"
            })
            elements.append({
                "tag": "markdown",
                "content": "### 📄 CƠ SỞ PHÁP LÝ VÀ NGUỒN TRÍCH DẪN"
            })
            for cit in parsed_citations:
                elements.append({
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": False,
                            "text": {
                                "tag": "lark_md",
                                "content": f"⚖️ **{cit['doc_name']}**\n🔢 Số hiệu: `{cit['so_hieu']}` | 📌 Hiệu lực: **{cit['hieu_luc']}**"
                            }
                        }
                    ]
                })
        elif citations_part:
            elements.append({
                "tag": "hr"
            })
            elements.append({
                "tag": "markdown",
                "content": f"### 📄 CƠ SỞ PHÁP LÝ VÀ NGUỒN TRÍCH DẪN\n{citations_part}"
            })

        # 6. Thêm khối note chân trang
        elements.append({
            "tag": "note",
            "elements": [
                {
                    "tag": "plain_text",
                    "content": "⚡ Phản hồi được xử lý tự động bằng hệ thống Trợ lý Pháp lý AI Việt Nam."
                }
            ]
        })

        return {
            "config": {
                "wide_screen_mode": True,
                "enable_forward": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "⚖️ HỆ THỐNG TRỢ LÝ PHÁP LÝ AI - VIETNAM LEGAL GRAPHRAG"
                },
                "template": "indigo"
            },
            "elements": elements
        }

    def send_reply(self, message_id: str, text_content: str, use_card: bool = True) -> bool:
        """
        Gửi tin nhắn trả lời (Reply) trực tiếp cho một tin nhắn cụ thể trong chat Lark.
        Hỗ trợ cả dạng Interactive Card (Markdown đẹp) và Plain Text.
        """
        token = self.get_tenant_access_token()
        if not token:
            logging.error("Không thể gửi tin nhắn Lark: Không có Token hợp lệ.")
            return False

        url = f"https://open.larksuite.com/open-apis/im/v1/messages/{message_id}/reply"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        if use_card:
            card_content = self._build_interactive_card(text_content)
            payload = {
                "content": json.dumps(card_content, ensure_ascii=False),
                "msg_type": "interactive"
            }
        else:
            # Format nội dung text thành JSON string theo đúng chuẩn Lark
            content_json = json.dumps({"text": text_content}, ensure_ascii=False)
            payload = {
                "content": content_json,
                "msg_type": "text"
            }

        try:
            logging.info(f"Đang gửi tin nhắn trả lời Lark cho Message ID {message_id} (Dạng {'Card' if use_card else 'Text'})...")
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            res_data = response.json()
            
            if res_data.get("code") == 0:
                logging.info("Gửi phản hồi lên Lark Suite thành công!")
                return True
            else:
                logging.error(f"Lark API trả về lỗi khi gửi tin nhắn: {res_data.get('msg')}. Chi tiết: {res_data}")
                # Nếu gửi card lỗi, thử fallback sang gửi text thường
                if use_card:
                    logging.info("Thử gửi lại dưới dạng plain text do gửi card lỗi...")
                    return self.send_reply(message_id=message_id, text_content=text_content, use_card=False)
                return False
        except Exception as e:
            logging.error(f"Lỗi mạng khi gửi tin nhắn phản hồi Lark: {str(e)}")
            if use_card:
                logging.info("Thử gửi lại dưới dạng plain text do lỗi mạng khi gửi card...")
                return self.send_reply(message_id=message_id, text_content=text_content, use_card=False)
            return False

    def send_message(self, receive_id: str, receive_id_type: str, text_content: str, use_card: bool = True) -> bool:
        """
        Gửi tin nhắn (Send Message) trực tiếp tới một đối tượng (user, chat, v.v.) trong Lark.
        Hỗ trợ cả dạng Interactive Card (Markdown đẹp) và Plain Text.
        """
        token = self.get_tenant_access_token()
        if not token:
            logging.error("Không thể gửi tin nhắn Lark: Không có Token hợp lệ.")
            return False

        url = f"https://open.larksuite.com/open-apis/im/v1/messages?receive_id_type={receive_id_type}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        if use_card:
            card_content = self._build_interactive_card(text_content)
            payload = {
                "receive_id": receive_id,
                "content": json.dumps(card_content, ensure_ascii=False),
                "msg_type": "interactive"
            }
        else:
            content_json = json.dumps({"text": text_content}, ensure_ascii=False)
            payload = {
                "receive_id": receive_id,
                "content": content_json,
                "msg_type": "text"
            }

        try:
            logging.info(f"Đang gửi tin nhắn Lark tới {receive_id_type} {receive_id} (Dạng {'Card' if use_card else 'Text'})...")
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            res_data = response.json()
            
            if res_data.get("code") == 0:
                logging.info("Gửi tin nhắn lên Lark Suite thành công!")
                return True
            else:
                logging.error(f"Lark API trả về lỗi khi gửi tin nhắn: {res_data.get('msg')}. Chi tiết: {res_data}")
                if use_card:
                    logging.info("Thử gửi lại dưới dạng plain text do gửi card lỗi...")
                    return self.send_message(receive_id=receive_id, receive_id_type=receive_id_type, text_content=text_content, use_card=False)
                return False
        except Exception as e:
            logging.error(f"Lỗi mạng khi gửi tin nhắn Lark: {str(e)}")
            if use_card:
                logging.info("Thử gửi lại dưới dạng plain text do lỗi mạng khi gửi card...")
                return self.send_message(receive_id=receive_id, receive_id_type=receive_id_type, text_content=text_content, use_card=False)
            return False
