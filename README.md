# 🚀 ERP AI Copilot (MVP)

> **Hệ thống ERP Demo tích hợp Trợ lý AI hội thoại thông minh**  
> Quản lý bán hàng, tồn kho, báo cáo doanh thu, hỏi đáp tài liệu RAG và trích xuất email tạo đơn hàng nháp với quy trình phê duyệt Human-In-The-Loop.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16_pgvector-4169E1?style=flat&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Google Gemini](https://img.shields.io/badge/LLM-Gemini_3.5_Flash_Lite-4285F4?style=flat&logo=google&logoColor=white)](https://ai.google.dev/)
[![Embedding](https://img.shields.io/badge/Embedding-Gemini_Embedding_2-4285F4?style=flat&logo=google&logoColor=white)](https://ai.google.dev/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Orchestrator-FF6F00?style=flat)](https://docs.langchain.com/oss/python/langgraph/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)

---

## 📌 1. Giới thiệu tổng quan

**ERP AI Copilot** là giải pháp kết hợp giữa hệ thống quản trị doanh nghiệp (ERP) tinh gọn và trợ lý trí tuệ nhân tạo (AI Copilot):
1. **Truy vấn ERP thời gian thực**: Tra cứu tức thì số lượng tồn kho theo kho (`on_hand`, `reserved`, `available`), thông tin khách hàng, sản phẩm, trạng thái đơn hàng.
2. **Báo cáo doanh thu chuẩn xác (UC-02)**: Đối chiếu doanh thu thực tế theo kỳ (tháng/năm) qua SQL/View chuẩn, loại bỏ đơn hủy.
3. **Tự động hóa Email-to-Draft**: Đọc email/PDF đặt hàng, trích xuất thực thể có cấu trúc và tạo **đơn hàng nháp (`draft`)**.
4. **Phê duyệt Human-In-The-Loop (HITL)**: Mọi thao tác ghi nhạy cảm đều phải qua bước phê duyệt từ người có thẩm quyền trước khi chốt đơn.
5. **Hỏi đáp tài liệu (RAG)**: Tra cứu quy định, chính sách công ty kèm trích dẫn nguồn (`citation`) chính xác và phân quyền (`ACL`).

### 🛡️ Nguyên tắc thiết kế cốt lõi
- **LLM không phải nguồn sự thật nghiệp vụ**: Mọi số liệu giao dịch, giá bán, tồn kho do ERP Domain Services tính toán và quản lý.
- **LLM không có quyền ghi DB trực tiếp**: Agent chỉ được gọi các Read Tools và đề xuất tạo bản nháp (`draft`). Không bao giờ tự ý chuyển trạng thái đơn sang `confirmed`.
- **Idempotency & Audit Trail**: Mọi thao tác ghi hỗ trợ header `Idempotency-Key` chống tạo đơn trùng lặp khi mạng retry; kiểm tra `payload_hash` và lưu audit log.

---

## 🏗️ 2. Kiến trúc hệ thống

```mermaid
flowchart TB
  U[Người dùng] --> FE[Frontend: Next.js Dashboard / Chat / Approval]
  FE --> API[FastAPI: Auth JWT, RBAC, Validation, OpenAPI]
  API --> ERP[ERP Domain Services: Customers / Products / Inventory / Orders / Reporting]
  API --> AG[LangGraph Orchestrator]
  API --> DOC[Document AI: Parse / OCR / Extract]
  AG --> TOOLS[ERP Tools - Allowlist Read-Only]
  AG --> RAG[RAG Retrieval Service]
  TOOLS --> ERP
  DOC --> RAG
  ERP --> PG[(PostgreSQL 16: erp schema)]
  RAG --> PGV[(pgvector + FTS: ai schema)]
  AG --> LLM[Google Gemini 3.5 Flash-Lite]
  DOC --> LLM
  API --> AUD[Audit Logs & Telemetry]
```

---

## 📁 3. Cấu trúc mã nguồn

Dự án được tổ chức theo mô hình **Modular Monolith**:

```text
erp-ai-copilot/
├── backend/
│   ├── app/
│   │   ├── api/v1/                 # REST API Routers
│   │   │   ├── auth.py             # Login, current user
│   │   │   ├── erp.py              # Endpoints: Customers, Products, Inventory, Orders, Reporting
│   │   │   └── router.py           # V1 API Root Registry
│   │   ├── auth/                   # Xác thực JWT, Security (bcrypt), get_current_user dependency
│   │   ├── core/                   # Cấu hình Settings (.env Pydantic v2), AppException
│   │   ├── db/                     # Base DeclarativeBase, AsyncSession factory
│   │   ├── erp/                    # Nghiệp vụ lõi ERP
│   │   │   ├── models.py           # Database Entities: Users, Customers, Products, Orders, Inventory,...
│   │   │   ├── schemas.py          # Pydantic v2 DTOs: Request / Response contracts
│   │   │   └── services/           # Domain Services đã chia nhỏ theo module
│   │   │       ├── customer.py     # CustomerService
│   │   │       ├── product.py      # ProductService
│   │   │       ├── inventory.py    # InventoryService (available calculation)
│   │   │       ├── order.py        # SalesOrderService (draft creation, idempotency)
│   │   │       └── reporting.py    # ReportingService (revenue analytics)
│   │   ├── ai/                     # LangGraph state, agents, allowlisted tools, prompts
│   │   ├── rag/                    # Ingestion, chunking, pgvector embedding, retrieval
│   │   ├── document_ai/            # Parser EML/PDF, structured extraction
│   │   └── main.py                 # FastAPI Application Entrypoint & CORS
│   ├── tests/
│   │   ├── unit/                   # Unit tests kiểm thử Invariants tồn kho
│   │   └── integration/            # Integration tests kiểm thử toàn bộ API endpoints
│   ├── pyproject.toml              # Cấu hình package & pytest-asyncio
│   └── requirements.txt            # Dependencies (FastAPI, SQLAlchemy 2.0, pgvector, LangGraph, Google GenAI)
├── frontend/                       # Next.js App (Dashboard, Chat, Approval Inbox)
├── infrastructure/
│   └── init-db.sql                 # Kích hoạt extension pgcrypto, vector & schemas
├── scripts/
│   └── seed_demo_data.py           # Script nạp dữ liệu mô phỏng (Deterministic & Idempotent)
├── data/
│   └── sample_documents/           # File PDF/EML mẫu cho kiểm thử RAG
├── evals/                          # Golden dataset & benchmark test cases
├── docker-compose.yml              # Container PostgreSQL 16 + pgvector
├── .env.example                    # Mẫu biến môi trường (an toàn trên git)
└── ERP_AI_Copilot_MVP_Technical_Blueprint.md # Bản đặc tả kỹ thuật chi tiết
```

---

## ⚡ 4. Hướng dẫn cài đặt & Khởi chạy nhanh

### Yêu cầu hệ thống (Prerequisites)
- [Python 3.11+](https://www.python.org/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (đã cài đặt và đang chạy)
- [Git](https://git-scm.com/)

---

### Bước 1: Khởi chạy Database (PostgreSQL 16 + pgvector)

Từ thư mục gốc dự án:
```powershell
docker compose up -d
```
> Container `erp-postgres` sẽ khởi chạy tại cổng `5432`, tự động tạo database `erp_copilot` và kích hoạt sẵn extensions `vector`, `pgcrypto`.

---

### Bước 2: Thiết lập môi trường Backend Python

1. Tạo môi trường ảo và kích hoạt:
   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\activate
   ```

2. Cài đặt các thư viện cần thiết:
   ```powershell
   pip install -r requirements.txt
   ```

3. Cấu hình biến môi trường:
   - Đảm bảo file `.env` đã có tại thư mục gốc (hoặc copy từ `.env.example`):
     ```env
     # LLM & Embedding Models
     GEMINI_API_KEY=your_gemini_api_key_here
     GEMINI_MODEL=gemini-3.5-flash-lite
     EMBEDDING_MODEL=gemini-embedding-2
     EMBEDDING_DIMENSION=1536
     ```

---

### Bước 3: Nạp dữ liệu mô phỏng (Seed Demo Data)

Khởi tạo các bảng cơ sở dữ liệu (`erp.*`, `ai.*`), tạo tài khoản demo và nạp dữ liệu mẫu:
```powershell
# Chạy từ thư mục gốc dự án
python scripts\seed_demo_data.py
```
Kết quả hiển thị:
```text
[*] Starting ERP demo data seeding...
[+] Demo data seeded successfully!
```

#### 🔑 Tài khoản đăng nhập Demo:
| Email | Mật khẩu | Quyền hạn (Role) |
|---|---|---|
| `admin@erpcopilot.vn` | `admin123` | Quản trị hệ thống (`admin`) |
| `sales@erpcopilot.vn` | `sales123` | Nhân viên bán hàng (`sales_rep`) |

---

### Bước 4: Khởi chạy Backend Server

Di chuyển vào thư mục `backend` và chạy máy chủ Uvicorn:
```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

Mở trình duyệt truy cập:
- **Swagger UI Interactive Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **OpenAPI Schema**: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- **API V1 Status**: [http://127.0.0.1:8000/api/v1/status](http://127.0.0.1:8000/api/v1/status)

---

## 🌐 5. Danh sách API Endpoints hiện tại (Sprint 2)

| Module | Method | Endpoint | Mô tả & Ràng buộc |
|---|---|---|---|
| **Auth** | `POST` | `/api/v1/auth/login` | Đăng nhập tài khoản demo, trả về JWT Access Token |
| | `GET` | `/api/v1/auth/me` | Lấy thông tin user hiện tại (yêu cầu Bearer Token) |
| **Customers** | `GET` | `/api/v1/customers` | Danh sách khách hàng (hỗ trợ phân trang, lọc trạng thái) |
| | `GET` | `/api/v1/customers/{code}` | Chi tiết khách hàng (ví dụ: `CUS-0001`) |
| **Products** | `GET` | `/api/v1/products` | Danh mục sản phẩm & giá niêm yết |
| | `GET` | `/api/v1/products/{sku}` | Chi tiết sản phẩm theo SKU (ví dụ: `SKU-001`) |
| **Inventory** | `GET` | `/api/v1/inventory` | Tra cứu tồn kho live: `available = on_hand - reserved` |
| **Orders** | `GET` | `/api/v1/sales-orders` | Danh sách đơn hàng bán |
| | `GET` | `/api/v1/sales-orders/{id}` | Chi tiết đơn hàng và các dòng sản phẩm |
| | `POST` | `/api/v1/sales-orders/drafts` | **Tạo đơn nháp**: Server snapshot giá, tính tiền trong transaction, hỗ trợ header `Idempotency-Key` |
| **Reporting** | `GET` | `/api/v1/reporting/revenue` | Báo cáo doanh thu theo kỳ/tháng thực tế từ DB (UC-02) |

---

## 🧪 6. Chạy Kiểm thử (Automated Tests)

Chạy toàn bộ bộ test tự động (bao gồm Unit tests và Integration tests):
```powershell
cd backend
pytest -v
```

Kết quả: **14/14 test cases Passed 100%**:
- `test_get_customers_list` & `test_get_customer_detail_found` & `not_found`
- `test_get_products_list_and_detail`
- `test_get_inventory_by_sku`
- `test_create_sales_order_draft_success` (Snapshot giá & tính tổng tiền tự động)
- `test_create_sales_order_draft_unknown_sku` (Bắt lỗi 404)
- `test_create_sales_order_draft_zero_quantity` (Bắt lỗi 422)
- `test_auth_login_success` & `test_auth_login_invalid_password` & `test_auth_me_authenticated`
- `test_reporting_revenue_summary` (Doanh thu thực tế)
- `test_create_order_draft_idempotency` (Chống tạo đơn trùng khi retry)
- `test_inventory_available_calculation` (Logic tồn kho)

---

## 🗺️ 7. Lộ trình phát triển (16 tuần / 8 Sprints)

| Sprint | Nội dung trọng tâm | Trạng thái |
|:---:|:---|:---:|
| **S1** | **Foundation**: Hạ tầng Docker, Schema PostgreSQL pgvector, Seed Data, Skeleton API | ✅ **Hoàn thành** |
| **S2** | **ERP Core**: Domain Services chia nhỏ, Auth JWT, Idempotency, Báo cáo Doanh thu, CRUD APIs | ✅ **Hoàn thành** |
| **S3** | **RAG Ingestion**: Upload tài liệu, trích xuất text/table, semantic chunking, vector embedding | ⏳ *Tiếp theo* |
| **S4** | **RAG Retrieval**: Hybrid search (FTS + vector), rerank, trích dẫn citation, phân quyền ACL | 📋 Kế hoạch |
| **S5** | **Agent Orchestrator**: LangGraph state machine, intent routing, tool calling an toàn | 📋 Kế hoạch |
| **S6** | **Document AI**: Phân tích email/đơn hàng, trích xuất Pydantic DTO, tạo draft order | 📋 Kế hoạch |
| **S7** | **Frontend & HITL**: Next.js Dashboard, Chatbox, Hộp thư phê duyệt Approval Inbox | 📋 Kế hoạch |
| **S8** | **Hardening & Eval**: Benchmark 200+ test cases, chống prompt injection, demo hoàn chỉnh | 📋 Kế hoạch |

Chi tiết lộ trình kỹ thuật và thiết kế kiến trúc xem tại [ERP_AI_Copilot_MVP_Technical_Blueprint.md](ERP_AI_Copilot_MVP_Technical_Blueprint.md).

---

## 📄 Bản quyền & Đóng góp
Dự án được xây dựng phục vụ mục đích nghiên cứu, trình diễn và phát triển giải pháp AI Copilot trong môi trường ERP Doanh nghiệp.
