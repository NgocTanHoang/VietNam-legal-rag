from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data_pipeline" / "data" / "raw"


def build_mock_documents() -> pd.DataFrame:
    rows = [
        {
            "doc_id": f"mock-doc-{index:02d}",
            "document_id": f"mock-doc-{index:02d}",
            "id": f"mock-doc-{index:02d}",
            "title": title,
            "so_ky_hieu": so_hieu,
            "content": content,
            "text": content,
            "tinh_trang_hieu_luc": "Còn hiệu lực",
            "ngay_ban_hanh": issue_date,
            "linh_vuc": topic,
        }
        for index, (title, so_hieu, issue_date, topic, content) in enumerate(
            [
                (
                    "Bộ luật Dân sự 2015 - Điều 351",
                    "91/2015/QH13",
                    "2015-11-24",
                    "Dân sự",
                    "Bên có nghĩa vụ phải chịu trách nhiệm dân sự nếu không thực hiện đúng nghĩa vụ, trừ trường hợp bất khả kháng hoặc bên có quyền chấp nhận."
                ),
                (
                    "Bộ luật Dân sự 2015 - Điều 428",
                    "91/2015/QH13",
                    "2015-11-24",
                    "Dân sự",
                    "Một bên có quyền đơn phương chấm dứt thực hiện hợp đồng khi bên kia vi phạm nghiêm trọng nghĩa vụ theo hợp đồng hoặc theo luật."
                ),
                (
                    "Luật Thương mại 2005 - Điều 301",
                    "36/2005/QH11",
                    "2005-06-14",
                    "Thương mại",
                    "Mức phạt vi phạm đối với nghĩa vụ hợp đồng thương mại không vượt quá tám phần trăm giá trị phần nghĩa vụ hợp đồng bị vi phạm."
                ),
                (
                    "Luật Thương mại 2005 - Điều 294",
                    "36/2005/QH11",
                    "2005-06-14",
                    "Thương mại",
                    "Bên vi phạm được miễn trách nhiệm trong trường hợp xảy ra sự kiện bất khả kháng hoặc hành vi vi phạm hoàn toàn do lỗi của bên kia."
                ),
                (
                    "Luật Thương mại 2005 - Điều 295",
                    "36/2005/QH11",
                    "2005-06-14",
                    "Thương mại",
                    "Bên gặp sự kiện bất khả kháng phải thông báo kịp thời cho bên kia về trường hợp miễn trách nhiệm và hậu quả có thể xảy ra."
                ),
                (
                    "Bộ luật Lao động 2019 - Điều 35",
                    "45/2019/QH14",
                    "2019-11-20",
                    "Lao động",
                    "Người lao động có quyền đơn phương chấm dứt hợp đồng lao động nhưng phải báo trước trong thời hạn luật định, trừ một số trường hợp đặc biệt."
                ),
                (
                    "Bộ luật Lao động 2019 - Điều 36",
                    "45/2019/QH14",
                    "2019-11-20",
                    "Lao động",
                    "Người sử dụng lao động có quyền đơn phương chấm dứt hợp đồng lao động trong các trường hợp luật định và phải tuân thủ điều kiện báo trước."
                ),
                (
                    "Luật Trọng tài thương mại 2010 - Điều 16",
                    "54/2010/QH12",
                    "2010-06-17",
                    "Trọng tài",
                    "Thỏa thuận trọng tài phải được lập bằng văn bản và xác định rõ phạm vi tranh chấp được đưa ra giải quyết bằng trọng tài."
                ),
                (
                    "Nghị quyết 326/2016/UBTVQH14 - Án phí dân sự sơ thẩm",
                    "326/2016/UBTVQH14",
                    "2016-12-30",
                    "Án phí",
                    "Án phí dân sự sơ thẩm đối với tranh chấp không có giá ngạch là ba trăm nghìn đồng; tranh chấp có giá ngạch áp dụng theo các mức lũy tiến."
                ),
                (
                    "Luật Doanh nghiệp 2020 - Vốn điều lệ",
                    "59/2020/QH14",
                    "2020-06-17",
                    "Doanh nghiệp",
                    "Doanh nghiệp tự quyết định mức vốn điều lệ khi đăng ký thành lập, trừ trường hợp pháp luật chuyên ngành quy định vốn pháp định."
                ),
                (
                    "Luật Đất đai 2024 - Bồi thường khi thu hồi đất",
                    "31/2024/QH15",
                    "2024-01-18",
                    "Đất đai",
                    "Phương án bồi thường, hỗ trợ, tái định cư phải được phê duyệt trước khi ban hành quyết định thu hồi đất đối với các trường hợp đủ điều kiện."
                ),
                (
                    "Luật Các tổ chức tín dụng 2024 - Kiểm soát nội bộ",
                    "32/2024/QH15",
                    "2024-01-18",
                    "Ngân hàng",
                    "Tổ chức tín dụng phải thiết lập hệ thống kiểm soát nội bộ, cơ chế giám sát tuân thủ và quản trị rủi ro độc lập."
                ),
            ],
            start=1,
        )
    ]
    return pd.DataFrame(rows)


def build_mock_relationships() -> pd.DataFrame:
    rows = [
        {
            "source_id": "mock-doc-03",
            "target_id": "mock-doc-04",
            "relation_key": "V_N_B_N_C_B_SUNG",
            "relationship": "Bổ sung quy định miễn trách nhiệm thương mại",
        },
        {
            "source_id": "mock-doc-04",
            "target_id": "mock-doc-05",
            "relation_key": "V_N_B_N_HD_Q_CHI_TI_T",
            "relationship": "Hướng dẫn nghĩa vụ thông báo bất khả kháng",
        },
        {
            "source_id": "mock-doc-06",
            "target_id": "mock-doc-07",
            "relation_key": "V_N_B_N_C_B_SUNG",
            "relationship": "Bổ sung nghĩa vụ báo trước trong lao động",
        },
        {
            "source_id": "mock-doc-02",
            "target_id": "mock-doc-08",
            "relation_key": "V_N_B_N_LIEN_QUAN",
            "relationship": "Liên quan điều khoản giải quyết tranh chấp",
        },
    ]
    return pd.DataFrame(rows)


def main() -> None:
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    documents = build_mock_documents()
    relationships = build_mock_relationships()

    content_path = RAW_DATA_DIR / "legal_content_mock.parquet"
    metadata_path = RAW_DATA_DIR / "legal_metadata_mock.parquet"
    relationships_path = RAW_DATA_DIR / "legal_relations_mock.parquet"

    documents.to_parquet(content_path, index=False)
    documents.drop(columns=["content", "text"]).to_parquet(metadata_path, index=False)
    relationships.to_parquet(relationships_path, index=False)

    manifest = {
      "content_path": str(content_path),
      "metadata_path": str(metadata_path),
      "relationships_path": str(relationships_path),
      "document_count": int(len(documents)),
      "relationship_count": int(len(relationships)),
    }
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
