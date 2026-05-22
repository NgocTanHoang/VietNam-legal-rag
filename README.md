<div align="center">

# 🏛️ Vietnamese Legal GraphRAG

### Trợ Lý Pháp Lý AI — Hệ thống Hỏi Đáp Pháp Luật Việt Nam Thông Minh

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agentic_AI-FF6F00?logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![Tests](https://img.shields.io/badge/Tests-14%2F14_Passed-brightgreen?logo=pytest&logoColor=white)](#-kiểm-thử-testing-suite)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

*Kiến trúc GraphRAG kết hợp song song **Qdrant Cloud** (Vector Search) và **Neo4j** (Graph Traversal), điều phối bởi **LangGraph Agent** — hỗ trợ cả Web UI và Lark Suite Chatbot.*

</div>

---

## 📌 Tổng Quan Dự Án

**Vietnamese Legal GraphRAG** là hệ thống Trợ lý Pháp lý AI cấp doanh nghiệp, cho phép nhân viên, ban giám đốc và luật sư tra cứu, hỏi đáp về hệ thống pháp luật Việt Nam bằng ngôn ngữ tự nhiên thông qua:

- **Web UI** (Vite + React) trên cổng `3000`
- **Lark Suite Chatbot** (Webhook Async) tích hợp trực tiếp vào không gian làm việc doanh nghiệp

### Điểm nổi bật

| Tính năng | Mô tả |
|-----------|-------|
| 🔍 **Dual-Database RAG** | Qdrant Cloud (vector similarity) + Neo4j (graph traversal) chạy song song |
| 🧠 **LangGraph Agent** | Đồ thị trạng thái đa bước: Query Rewrite → Vector Retrieval → Graph Lookup → LLM Generation |
| 🔒 **Redis Distributed Lock** | Đánh chặn request trùng lặp, tránh chạy LangGraph 2 lần cho cùng câu hỏi |
| ⚡ **LLM Semaphore** | Giới hạn 3 slots gọi API LLM đồng thời, tránh lỗi 429 Rate Limit |
| 💬 **Lark Suite Integration** | Async Webhook phản hồi HTTP 200 < 100ms, xử lý AI trong Background Tasks |
| 📦 **Redis Response Cache** | Cache Hit giảm **99.95%** thời gian phản hồi (15,581ms → 7.5ms) |
| 🏗️ **Auto-Healing Citations** | Tự động trích dẫn số hiệu văn bản từ ngữ cảnh thực tế, chống ảo giác (hallucination) |

---

## 🏗️ Kiến Trúc Hệ Thống

```
┌──────────────────────────────────────────────────────────────────┐
│                       CLIENT LAYER                               │
│  ┌──────────────┐    ┌──────────────────────────────────┐       │
│  │  Web UI       │    │  Lark Suite (Webhook Async)      │       │
│  │  Port 3000    │    │  POST → 200 OK < 100ms           │       │
│  └──────┬───────┘    └──────────────┬───────────────────┘       │
└─────────┼───────────────────────────┼───────────────────────────┘
          │                           │
          ▼                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND (Port 8000)                    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │           CONCURRENCY CONTROL LAYER                     │     │
│  │  ┌─────────────────┐  ┌──────────────────────────┐    │     │
│  │  │ Redis Dist. Lock │  │ LLM Semaphore (3 slots)  │    │     │
│  │  │ SET NX + TTL 60s │  │ threading.Semaphore(3)   │    │     │
│  │  └─────────────────┘  └──────────────────────────┘    │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │              LANGGRAPH AGENT PIPELINE                   │     │
│  │                                                         │     │
│  │  [Query Rewrite] → [Qdrant Retrieval] → [Neo4j Graph]  │     │
│  │                          ↓                               │     │
│  │              [LLM Response Generator]                    │     │
│  └────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
          │                    │                    │
          ▼                    ▼                    ▼
┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Qdrant Cloud │  │ Neo4j Graph DB   │  │ Redis Cache      │
│ 116K+ chunks │  │ 116K+ nodes      │  │ Embedding + RAG  │
│ Vector Search│  │ 669K+ relations  │  │ Response Cache   │
└──────────────┘  └──────────────────┘  └──────────────────┘
```

### Luồng xử lý Concurrency (Chi tiết)

```
Request A (Web UI) ─────┐
                        ├──→ Redis Lock: SET NX "lock:query:{hash}"
Request B (Lark) ───────┘      │
                               ├─ Lock ✅ (Request A) → Chạy LangGraph → Save Cache → Release Lock
                               │
                               └─ Lock ❌ (Request B) → wait_for_cached_result()
                                                           │
                                                           ├─ Poll cache mỗi 0.5s
                                                           └─ Cache Hit → Trả kết quả (< 100ms)
```

---

## ⚙️ Hướng Dẫn Cài Đặt & Cấu Hình

### Yêu cầu hệ thống

- **Python** 3.11+
- **Docker** & Docker Compose (cho cụm database)
- **Node.js** 18+ (cho Frontend — tùy chọn)

### Bước 1: Clone dự án

```bash
git clone https://github.com/<your-org>/VietNam-legal-rag.git
cd VietNam-legal-rag
```

### Bước 2: Khởi chạy cụm cơ sở dữ liệu

```bash
cd infra
docker compose up -d
```

Lệnh trên sẽ khởi động:

| Service | Container | Port | Mô tả |
|---------|-----------|------|-------|
| PostgreSQL 15 | `legal_postgres` | `5432` | Lưu trữ bền vững |
| Redis Alpine | `legal_redis` | `6379` | Cache & Distributed Lock |
| Qdrant | `legal_qdrant` | `6333`, `6334` | Vector Database (local) |
| Neo4j | `legal_neo4j` | `7474`, `7687` | Graph Database |

> **Lưu ý:** Dự án hỗ trợ cả **Qdrant Cloud** (khuyến nghị cho production) lẫn Qdrant local. Cấu hình qua biến `QDRANT_HOST` trong `.env`.

### Bước 3: Cấu hình biến môi trường

Tạo file `.env` tại thư mục gốc với cấu trúc sau:

```env
# ═══════════════════════════════════════════════════════════════
# 🤖 AI / LLM API Keys (Cần ít nhất 1 trong 3)
# ═══════════════════════════════════════════════════════════════
GEMINI_API_KEY=your_google_gemini_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
NVIDIA_API_KEY=your_nvidia_api_key_here

# ═══════════════════════════════════════════════════════════════
# 🗄️ Databases
# ═══════════════════════════════════════════════════════════════
# PostgreSQL
POSTGRES_USER=admin
POSTGRES_PASSWORD=your_postgres_password
POSTGRES_DB=legal_rag_db
POSTGRES_HOST=postgres

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Qdrant (Cloud hoặc Local)
QDRANT_HOST=https://your-cluster-id.cloud.qdrant.io
QDRANT_PORT=6333
QDRANT_API_KEY=your_qdrant_api_key_here

# Neo4j
NEO4J_URI=bolt://neo4j:7687
NEO4J_PASSWORD=your_neo4j_password

# ═══════════════════════════════════════════════════════════════
# 📂 Data Paths
# ═══════════════════════════════════════════════════════════════
RAW_DATA_DIR=./data/raw
PROCESSED_DATA_DIR=./data/processed

# ═══════════════════════════════════════════════════════════════
# 💬 Lark Suite Integration (Tùy chọn)
# ═══════════════════════════════════════════════════════════════
LARK_APP_ID=your_lark_app_id
LARK_APP_SECRET=your_lark_app_secret
LARK_ENCRYPT_KEY=
LARK_VERIFICATION_TOKEN=
```

### Bước 4: Cài đặt thư viện Python

```bash
python -m venv venv
# Windows
.\venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### Bước 5: Khởi chạy Backend

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

API sẽ hoạt động tại:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redocs
- **Health Check**: http://localhost:8000/api/v1/health

---

## 🔄 Pipeline Nạp Dữ Liệu (Data Ingestion)

Pipeline ETL tự động: **Extract** (Parquet) → **Transform** (HTML Clean + Chunk) → **Load** (Qdrant + Neo4j).

### Chạy nạp mẫu (Test nhanh)

```bash
python data_pipeline/ingest.py --sample-size 100
```

### Chạy nạp toàn bộ dữ liệu

```bash
python data_pipeline/ingest.py
```

### Tham số tùy chỉnh

| Tham số | Mặc định | Mô tả |
|---------|----------|-------|
| `--sample-size N` | Toàn bộ | Chỉ nạp N văn bản đầu tiên để test |
| `--skip-qdrant` | `False` | Bỏ qua nạp Qdrant |
| `--skip-neo4j` | `False` | Bỏ qua nạp Neo4j |
| `--collection NAME` | Từ `.env` | Tên collection Qdrant tùy chỉnh |
| `--content-path PATH` | Mặc định | Đường dẫn file `legal_content.parquet` |
| `--metadata-path PATH` | Mặc định | Đường dẫn file `legal_metadata.parquet` |
| `--relations-path PATH` | Mặc định | Đường dẫn file `legal_relationships.parquet` |

---

## 🧪 Kiểm Thử (Testing Suite)

### Unit Tests (14 test cases)

```bash
python -m pytest tests/ -v
```

```
tests/test_caching_and_tenacity.py    ✅ 3/3  (Redis Cache, Bypass Mode, Transient Error)
tests/test_graph.py                   ✅ 3/3  (Related Docs, Guidance Docs, Validity Check)
tests/test_lark_connection.py         ✅ 5/5  (URL Verify, Message, Token, Decrypt, Async Task)
tests/test_qdrant.py                  ✅ 3/3  (Search, Get by ID, Count by Year)
─────────────────────────────────────────────────────────────────
TỔNG CỘNG                            ✅ 14/14 PASSED
```

### Integration Tests (4 kịch bản — Yêu cầu server đang chạy)

```bash
# Khởi động server trước
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Chạy integration tests
python data_pipeline/run_integration_tests.py
```

| Kịch bản | Mô tả | Tiêu chí đạt |
|----------|-------|---------------|
| **TC-001** | Chống ảo giác & Auto-Healing Citations | Tìm thấy header `📄 CƠ SỞ PHÁP LÝ VÀ NGUỒN TRÍCH DẪN` |
| **TC-002** | Redis Response Cache | Lần 2 nhanh hơn Lần 1 (Cache Hit < 100ms) |
| **TC-003** | Từ chối an toàn ngoài biên dữ liệu | Trả lời đúng cho câu hỏi ngoài phạm vi VN |
| **TC-004** | Concurrent Test (3 requests song song) | 3/3 trả về HTTP 200 OK ổn định |

---

## 📁 Cấu Trúc Dự Án

```
VietNam-legal-rag/
├── app/                          # 🏗️ Backend FastAPI Application
│   ├── main.py                   #    Entry point, CORS, Router registration
│   ├── agents/                   #    LangGraph Agent (Nodes + Edges + State)
│   │   ├── legal_agent.py        #    StateGraph compiler & runner
│   │   ├── nodes/                #    retrieval_node, graph_node, generator_node
│   │   ├── edges.py              #    query_rewriter_node, route_after_retrieval
│   │   └── state.py              #    AgentState TypedDict
│   ├── api/v1/                   #    REST API Endpoints
│   │   ├── endpoints.py          #    /chat, /health (with Distributed Lock)
│   │   └── lark_webhook.py       #    /webhook (Async Background Tasks)
│   ├── core/                     #    Config, Security, Exceptions
│   └── services/                 #    Business Logic Services
│       ├── graph_service.py      #    Neo4j Cypher queries (directed →)
│       ├── llm_service.py        #    Multi-provider LLM + Semaphore(3)
│       ├── qdrant_service.py     #    Vector search client
│       ├── redis_service.py      #    Cache + Distributed Lock
│       └── lark_service.py       #    Lark API client (Interactive Cards)
├── data_pipeline/                # 🔄 ETL Data Ingestion Pipeline
│   ├── ingest.py                 #    Main pipeline orchestrator
│   ├── extractors/               #    Parquet file reader
│   ├── transformers/             #    HTML cleaner, text chunker, metadata
│   ├── loaders/                  #    Qdrant loader, Neo4j loader
│   └── run_integration_tests.py  #    Integration test runner (TC-001~TC-004)
├── frontend/                     # 🎨 Vite + React Web UI
├── infra/                        # 🐳 Docker Infrastructure
│   ├── docker-compose.yml        #    PostgreSQL, Redis, Qdrant, Neo4j
│   └── Dockerfile                #    Python app container
├── prompts/                      # 📝 System prompt templates
├── tests/                        # 🧪 Unit Tests (pytest)
├── .github/workflows/ci.yml      # 🔁 GitHub Actions CI Pipeline
├── .env                          # 🔐 Environment variables (git-ignored)
├── requirements.txt              # 📦 Python dependencies
└── README.md                     # 📖 This file
```

---

## 🔁 CI/CD Pipeline

Dự án sử dụng **GitHub Actions** để tự động kiểm thử trên mọi `push` và `pull_request` vào nhánh `main`/`master`.

Xem cấu hình: [`.github/workflows/ci.yml`](.github/workflows/ci.yml)

---

## 📄 License

Dự án được phát hành dưới giấy phép [MIT License](LICENSE).

---

<div align="center">

**Được phát triển bởi đội ngũ Vietnamese Legal GraphRAG** 🇻🇳

*Hệ thống Trợ lý Pháp lý AI thế hệ mới — Chính xác, Nhanh chóng, Đáng tin cậy.*

</div>