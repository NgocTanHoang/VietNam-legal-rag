from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List, Tuple

import httpx
import requests


API_BASE_URL = os.getenv("LEXORA_API_BASE_URL", "http://127.0.0.1:8888").rstrip("/")
CHAT_ENDPOINT = f"{API_BASE_URL}/api/v1/chat"


def ensure_utf8_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def print_json(label: str, payload: Dict[str, Any]) -> None:
    print(f"{label}: {json.dumps(payload, ensure_ascii=False)}")


def run_scenario(scenario_id: str, query: str) -> Tuple[int, float, Dict[str, Any]]:
    started_at = time.perf_counter()
    response = requests.post(CHAT_ENDPOINT, json={"query": query}, timeout=90)
    duration_ms = (time.perf_counter() - started_at) * 1000
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw_text": response.text}
    return response.status_code, duration_ms, payload


async def run_concurrent_test() -> List[Dict[str, Any]]:
    queries = [
        ("REQ-A", "Quy định về vốn điều lệ của doanh nghiệp theo Luật Doanh nghiệp?"),
        ("REQ-B", "Quy định về vốn điều lệ của doanh nghiệp theo Luật Doanh nghiệp?"),
        ("REQ-C", "Thủ tục đăng ký kinh doanh cho doanh nghiệp tư nhân được quy định như thế nào?"),
    ]

    async def send_one(client: httpx.AsyncClient, label: str, query: str) -> Dict[str, Any]:
        started_at = time.perf_counter()
        response = await client.post(CHAT_ENDPOINT, json={"query": query}, timeout=90.0)
        duration_ms = (time.perf_counter() - started_at) * 1000
        try:
            payload = response.json()
        except ValueError:
            payload = {"raw_text": response.text}
        return {
            "label": label,
            "status": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "answer_preview": str(payload.get("answer", ""))[:120],
            "chunks_count": payload.get("chunks_count", 0),
        }

    async with httpx.AsyncClient() as client:
        return await asyncio.gather(*(send_one(client, label, query) for label, query in queries))


def main() -> int:
    ensure_utf8_stdout()

    print("=== KIỂM THỬ TÍCH HỢP LEXORA ===")
    print(f"API đích: {CHAT_ENDPOINT}")

    scenarios = [
        ("TC-001", "Quy định về hệ thống kiểm soát nội bộ của ngân hàng thương mại được nêu tại văn bản nào ban hành gần đây?"),
        ("TC-002", "Điều kiện để một văn bản pháp luật được coi là hết hiệu lực hoàn toàn là gì?"),
        ("TC-003", "Quy định về việc đăng ký bản quyền hình ảnh kỹ thuật số theo Đạo luật DMCA của Mỹ như thế nào?"),
    ]

    failures = 0
    for scenario_id, query in scenarios:
        try:
            status_code, duration_ms, payload = run_scenario(scenario_id, query)
        except requests.RequestException as exc:
            failures += 1
            print(f"{scenario_id}: lỗi kết nối tới backend Lexora: {exc}")
            continue

        summary = {
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "query_rewritten": payload.get("query_rewritten"),
            "chunks_count": payload.get("chunks_count", 0),
            "graph_relations_count": payload.get("graph_relations_count", 0),
            "answer_preview": str(payload.get("answer", ""))[:180],
        }
        print_json(scenario_id, summary)
        if status_code != 200:
            failures += 1

    try:
        concurrent_results = asyncio.run(run_concurrent_test())
    except Exception as exc:
        failures += 1
        print(f"TC-004: lỗi concurrent test: {exc}")
    else:
        for item in concurrent_results:
            print_json(item["label"], item)
            if item["status"] != 200:
                failures += 1

    print(f"KẾT THÚC: {'PASS' if failures == 0 else 'FAIL'} | lỗi={failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
