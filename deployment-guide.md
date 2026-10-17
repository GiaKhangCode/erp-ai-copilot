# HƯỚNG DẪN TRIỂN KHAI HỆ THỐNG ERP AI COPILOT "0 ĐỒNG VĨNH VIỄN"
*(Zero-Cost Stack: Azure Free Tier + Supabase Free + GitHub Packages)*

Tài liệu này hướng dẫn chi tiết từng bước (Step-by-Step) cách triển khai toàn bộ hệ thống **ERP AI Copilot** lên môi trường Production mà **hoàn toàn không tốn một đồng chi phí nào (0 VNĐ)**, không cần thẻ tín dụng để kích hoạt tài khoản phụ, và duy trì hoạt động lâu dài.

---

## I. KIẾN TRÚC TỔNG QUAN "ZERO-COST STACK"

| Thành phần | Dịch vụ được chọn | Vai trò | Gói dịch vụ & Hạn mức Always Free |
| :--- | :--- | :--- | :--- |
| **Frontend** | **Azure Static Web Apps** | Giao diện Next.js SPA | **Always Free**: 100 GB băng thông/tháng, SSL miễn phí, CI/CD tự động |
| **Backend** | **Azure Container Apps** | API FastAPI + RAG Engine | **Always Free**: 180.000 vCPU-s, 360.000 GiB-s, 2 triệu request/tháng |
| **Image Registry** | **GitHub Packages (`ghcr.io`)** | Chứa Docker Image backend | **Always Free**: 500 MB storage, băng thông kéo miễn phí từ GitHub |
| **Database** | **Supabase (PostgreSQL 16)** | Lưu dữ liệu ERP + Vector HNSW | **Always Free**: 500 MB DB, đầy đủ `pgvector` & `pgcrypto` |
| **Storage** | **Supabase Storage** | Lưu file tài liệu PDF/Excel RAG | **Always Free**: 1 GB lưu trữ, hỗ trợ S3 API Protocol |
| **AI LLM** | **Google AI Studio (Gemini)** | Mô hình suy luận & Embedding | **Free Tier**: Miễn phí theo hạn mức RPM/RPD của Gemini 2.5 Flash |
| **Keep-Alive** | **Cron-job.org / GitHub Actions** | Chống "ngủ" Supabase sau 7 ngày | **Always Free**: Tự động gửi request ping định kỳ |

---

## II. CÁC RÀNG BUỘC KỸ THUẬT BẮT BUỘC (ĐỂ DUY TRÌ 0 ĐỒNG)

Để hệ thống không bao giờ bị tính phí hoặc bị tạm dừng, bạn **bắt buộc tuân thủ 5 nguyên tắc** sau:

1. **Ràng buộc 1 - Container Apps Scale to 0**:
   - Khi tạo Azure Container Apps, giá trị `minReplicas` **BẮT BUỘC PHẢI BẰNG 0** (`minReplicas = 0`).
   - *Lý do*: Nếu để `minReplicas = 1`, container sẽ chạy 720 giờ/tháng (= 2.592.000 vCPU-giây) $\rightarrow$ vượt quá 180.000 vCPU-giây miễn phí. Khi đặt bằng `0`, khi không có truy cập container sẽ ngủ, chỉ tốn 0 vCPU.
   - *Hệ quả*: Request đầu tiên sau một thời gian dài sẽ mất 10–20 giây để khởi động ("Cold start"), các request sau đó sẽ phản hồi tức thì.
2. **Ràng buộc 2 - Không dùng Azure Container Registry (ACR)**:
   - Tuyệt đối không tạo tài nguyên ACR trên Azure vì ACR không có Always Free (~$5/tháng).
   - Hãy dùng **GitHub Container Registry (`ghcr.io`)** có sẵn trong tài khoản GitHub của bạn.
3. **Ràng buộc 3 - Chống Auto-pause Supabase (7 ngày)**:
   - Supabase Free sẽ tự động "ngủ" (pause) dự án nếu trong 7 ngày liên tục không nhận được bất kỳ query database nào.
   - Bạn cần thiết lập Cron-job ping endpoint `/health` của backend mỗi 2-3 ngày/lần.
4. **Ràng buộc 4 - Giới hạn dung lượng Supabase (500 MB)**:
   - Cơ sở dữ liệu và vector chỉ dùng trong giới hạn 500 MB (đủ cho hàng chục nghìn dòng dữ liệu ERP và hàng nghìn đoạn văn bản tài liệu).
5. **Ràng buộc 5 - Gia hạn Azure Student định kỳ**:
   - Mỗi năm 1 lần, khi nhận được thông báo hết hạn 12 tháng từ Azure, hãy vào **Azure Education Hub** xác minh lại email trường để gia hạn quyền lợi học sinh/sinh viên.

---

## III. HƯỚNG DẪN TRIỂN KHAI CHI TIẾT (5 BƯỚC)

```mermaid
flowchart TD
    subgraph Step1 ["Bước 1: Supabase Setup"]
        DB[(PostgreSQL + pgvector)]
        S3[Supabase Storage S3]
        Seed[Chạy seed_demo_data.py từ local]
    end

    subgraph Step2 ["Bước 2: Đóng gói Backend"]
        Code[FastAPI Source Code] --> Docker[Build Docker Image]
        Docker --> GHCR[Push to ghcr.io]
    end

    subgraph Step3 ["Bước 3: Azure Container Apps"]
        GHCR --> ACA[Azure Container Apps]
        ACA -->|minReplicas = 0| DB
        ACA --> S3
    end

    subgraph Step4 ["Bước 4: Azure Static Web Apps"]
        Next[Next.js App] --> SWA[Azure Static Web Apps]
        SWA -->|NEXT_PUBLIC_API_URL| ACA
    end

    subgraph Step5 ["Bước 5: Keep-Alive"]
        Cron[Cron-job.org / GitHub Action] -->|Ping mỗi 2 ngày| ACA
    end
```

---

### BƯỚC 1: CẤU HÌNH DATABASE & STORAGE TRÊN SUPABASE

1. **Tạo tài khoản và dự án Supabase**:
   - Truy cập [supabase.com](https://supabase.com) $\rightarrow$ Đăng nhập bằng **GitHub** (không yêu cầu thẻ tín dụng).
   - Bấm **New Project** $\rightarrow$ Chọn Region gần nhất (ví dụ: `Southeast Asia (Singapore)`).
   - Đặt Database Password mạnh và **lưu lại mật khẩu này**.
2. **Kích hoạt Extension `vector`**:
   - Vào mục **SQL Editor** trong thanh menu bên trái, paste câu lệnh sau và bấm **Run**:
     ```sql
     CREATE EXTENSION IF NOT EXISTS pgcrypto;
     CREATE EXTENSION IF NOT EXISTS vector;
     CREATE SCHEMA IF NOT EXISTS erp;
     CREATE SCHEMA IF NOT EXISTS ai;
     ```
3. **Lấy chuỗi kết nối Database**:
   - Vào **Project Settings** (biểu tượng bánh răng) $\rightarrow$ **Database** $\rightarrow$ mục **Connection string** $\rightarrow$ chọn tab **URI** (hoặc Session pooler port `5432`).
   - Chuỗi kết nối có dạng:
     ```text
     postgresql://postgres.[PROJECT_REF]:[YOUR_PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres
     ```
   - Chuyển đổi thành 2 chuỗi kết nối cho backend:
     - `DATABASE_URL`: Thay `postgresql://` bằng `postgresql+asyncpg://`
     - `DATABASE_URL_SYNC`: Giữ nguyên `postgresql://`
4. **Cấu hình Supabase Storage (S3-Compatible)**:
   - Vào **Storage** $\rightarrow$ Bấm **New Bucket** $\rightarrow$ Đặt tên: `erp-documents` $\rightarrow$ Chọn **Private bucket**.
   - Vào **Project Settings** $\rightarrow$ **Storage** $\rightarrow$ mục **S3 Access Keys** $\rightarrow$ Bấm **Create new key**:
     - Lưu lại: `Access Key ID`, `Secret Access Key`, và `Endpoint URL` (thường là `https://[PROJECT_REF].supabase.co/storage/v1/s3`).
5. **Chạy script khởi tạo bảng & dữ liệu mẫu từ máy local**:
   - Mở terminal tại thư mục gốc của dự án `d:\PROJECTS\erp-ai-copilot`:
   - Tạo tạm file `.env` hoặc truyền biến môi trường trỏ thẳng vào Supabase:
     ```bash
     # Cài đặt tạm biến môi trường trên PowerShell (thay YOUR_PASSWORD và PROJECT_REF)
     $env:DATABASE_URL="postgresql+asyncpg://postgres.[PROJECT_REF]:[YOUR_PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"
     $env:DATABASE_URL_SYNC="postgresql://postgres.[PROJECT_REF]:[YOUR_PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"
     
     # Chạy script khởi tạo toàn bộ schema, bảng ERP, vector indexes và demo data
     python scripts/seed_demo_data.py
     ```
   - Khi terminal thông báo `[+] Demo data seeded successfully!`, toàn bộ bảng biểu và tài khoản mẫu (`admin@erp.com`, `sale@erp.com`) đã nằm an toàn trên Supabase.

---

### BƯỚC 2: BUILD VÀ ĐẨY DOCKER IMAGE BACKEND LÊN GHCR.IO

Dự án đã có sẵn file [backend/Dockerfile](file:///d:/PROJECTS/erp-ai-copilot/backend/Dockerfile) và [.dockerignore](file:///d:/PROJECTS/erp-ai-copilot/backend/.dockerignore).

1. **Tạo GitHub Personal Access Token (Classic)**:
   - Truy cập: `https://github.com/settings/tokens` $\rightarrow$ **Generate new token (classic)**.
   - Note: `ghcr-token`.
   - Tích chọn quyền: `write:packages`, `read:packages`, `delete:packages`.
   - Copy mã token (chuỗi `ghp_...`).
2. **Đăng nhập và Build Image từ máy local**:
   - Mở PowerShell:
     ```powershell
     # 1. Đăng nhập vào GitHub Container Registry (thay GITHUB_USERNAME và TOKEN)
     echo "ghp_YOUR_TOKEN" | docker login ghcr.io -u GITHUB_USERNAME --password-stdin

     # 2. Chuyển vào thư mục backend và build image
     cd d:\PROJECTS\erp-ai-copilot\backend
     docker build -t ghcr.io/GITHUB_USERNAME/erp-backend:v1.0.0 -t ghcr.io/GITHUB_USERNAME/erp-backend:latest .

     # 3. Đẩy image lên GitHub
     docker push ghcr.io/GITHUB_USERNAME/erp-backend:latest
     docker push ghcr.io/GITHUB_USERNAME/erp-backend:v1.0.0
     ```
3. **Chuyển gói Package sang chế độ Public (để Azure Container Apps kéo không cần cấu hình secret phức tạp)**:
   - Trên GitHub của bạn, vào trang cá nhân $\rightarrow$ mục **Packages** $\rightarrow$ bấm vào `erp-backend`.
   - Chọn **Package settings** $\rightarrow$ kéo xuống dưới cùng mục **Danger Zone** $\rightarrow$ chọn **Change visibility** $\rightarrow$ chuyển sang **Public**.

---

### BƯỚC 3: TRIỂN KHAI BACKEND LÊN AZURE CONTAINER APPS

1. **Tạo Container App trên Azure Portal**:
   - Truy cập [Azure Portal](https://portal.azure.com).
   - Tìm kiếm thanh trên cùng: **Container Apps** $\rightarrow$ Bấm **Create**.
   - **Basics**:
     - *Resource Group*: Tạo mới, ví dụ `rg-erp-copilot`.
     - *Container App Name*: `erp-backend-api` (hoặc tên tuỳ chọn).
     - *Region*: `Southeast Asia` hoặc `East Asia`.
     - *Container Apps Environment*: Bấm tạo mới (chọn gói **Consumption** - Miễn phí).
   - **Container**:
     - Bỏ tick *Use quickstart image*.
     - *Image source*: **Other public or private registry**.
     - *Registry login server*: `ghcr.io`.
     - *Image and tag*: `ghcr.io/GITHUB_USERNAME/erp-backend:latest`.
     - *CPU and Memory*: Chọn mức nhỏ nhất: **0.25 vCPU, 0.5 GiB** (tối ưu hạn mức miễn phí).
   - **Ingress**:
     - *Enable Ingress*: **Checked (Bật)**.
     - *Ingress traffic*: **Accepting traffic from anywhere (External)**.
     - *Target port*: `8000`.
   - Bấm **Review + Create** $\rightarrow$ **Create**.

2. **Cấu hình Ràng buộc Miễn phí (`minReplicas = 0`)**:
   - Sau khi tạo xong, vào tài nguyên Container App của bạn.
   - Chọn menu bên trái: **Scale and replicas** $\rightarrow$ Bấm **Edit and deploy**.
   - Chuyển tab **Scale**:
     - *Min replicas*: Nhập **`0`** (Bắt buộc!).
     - *Max replicas*: Nhập **`1`** hoặc **`2`**.
   - Bấm **Deploy**.

3. **Thiết lập Biến Môi Trường (Environment Variables)**:
   - Vào menu bên trái: **Configuration** $\rightarrow$ Chuyển tab **Environment variables**:
   - Bấm **Add** và điền các biến môi trường:
     - `APP_ENV`: `production`
     - `DEBUG`: `False`
     - `SECRET_KEY`: `[CHUỖI_RANDOM_BẢO_MẬT_CỦA_BẠN]`
     - `DATABASE_URL`: `postgresql+asyncpg://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres`
     - `DATABASE_URL_SYNC`: `postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres`
     - `STORAGE_TYPE`: `s3`
     - `S3_ENDPOINT_URL`: `https://[PROJECT_REF].supabase.co/storage/v1/s3`
     - `S3_ACCESS_KEY`: `[SUPABASE_S3_ACCESS_KEY]`
     - `S3_SECRET_KEY`: `[SUPABASE_S3_SECRET_KEY]`
     - `S3_BUCKET_NAME`: `erp-documents`
     - `S3_REGION`: `ap-southeast-1`
     - `GEMINI_API_KEY`: `[YOUR_GEMINI_API_KEY]`
     - `GEMINI_MODEL`: `gemini-2.5-flash`
     - `EMBEDDING_MODEL`: `gemini-embedding-2`
     - `CORS_ORIGINS`: `["*"]` *(Tạm thời để `["*"]` để frontend dễ dàng kết nối, sau khi có link frontend sẽ cập nhật lại)*
   - Bấm **Save** để áp dụng.

4. **Kiểm tra Backend**:
   - Quay lại trang **Overview**, copy đường dẫn **Application Url** (ví dụ: `https://erp-backend-api.ambitiousgrass-12345.southeastasia.azurecontainerapps.io`).
   - Mở trình duyệt gõ: `https://[URL-CỦA-BẠN]/health`.
   - Kết quả trả về JSON `{"status": "ok", "app": "ERP AI Copilot", "env": "production"}` nghĩa là backend đã sẵn sàng 100%!

---

### BƯỚC 4: TRIỂN KHAI FRONTEND LÊN AZURE STATIC WEB APPS

1. **Tạo tài nguyên Azure Static Web Apps**:
   - Trên Azure Portal, tìm kiếm: **Static Web Apps** $\rightarrow$ Bấm **Create**.
   - **Basics**:
     - *Subscription*: Azure for Students.
     - *Resource Group*: Chọn `rg-erp-copilot`.
     - *Name*: `erp-frontend-app`.
     - *Plan type*: **Free (For personal/hobby projects)** $\rightarrow$ Bắt buộc chọn gói này!
     - *Region*: `East Asia` hoặc `Southeast Asia`.
     - *Source*: Chọn **GitHub** $\rightarrow$ Bấm **Sign in with GitHub** và cấp quyền.
   - **Deployment details**:
     - *Organization*: Tên GitHub của bạn.
     - *Repository*: `erp-ai-copilot`.
     - *Branch*: `main`.
     - *Build Presets*: Chọn **Next.js**.
     - *App location*: `/frontend`
     - *Api location*: để trống.
     - *Output location*: để trống (tự động theo Next.js build).
   - Bấm **Review + Create** $\rightarrow$ **Create**.

2. **Cấu hình Biến Môi Trường (API URL) cho Frontend**:
   - Khi Azure tạo xong Static Web App, nó sẽ tự động commit một file GitHub Actions workflow vào repo của bạn.
   - Trên Azure Portal, vào Static Web App vừa tạo $\rightarrow$ Vào menu bên trái: **Configuration**.
   - Bấm **+ Add**:
     - *Name*: `NEXT_PUBLIC_API_URL`
     - *Value*: `https://[BACKEND_CONTAINER_APP_URL]/api/v1` (Lưu ý: có đuôi `/api/v1`).
   - Bấm **Save**.
   - Vào GitHub Repo $\rightarrow$ tab **Actions**, bạn sẽ thấy quy trình build tự động đang chạy. Chờ quy trình hoàn thành (tích xanh).

3. **Trải nghiệm ứng dụng**:
   - Mở đường dẫn của Azure Static Web Apps (dạng `https://gentle-ocean-0abc123.azurestaticapps.net`).
   - Đăng nhập bằng tài khoản demo:
     - **Admin**: `admin@erp.com` / `admin123`
     - **Sales Rep**: `sale@erp.com` / `sale123`
   - Thử nghiệm chat AI, xem báo cáo doanh thu, đơn hàng, tồn kho và upload tài liệu.

---

### BƯỚC 5: CÀI ĐẶT KEEP-ALIVE (CHỐNG NGỦ SUPABASE 7 NGÀY)

Để Supabase không bao giờ bị pause do không có truy cập quá 7 ngày:

1. Truy cập dịch vụ [cron-job.org](https://cron-job.org) (Miễn phí vĩnh viễn, không cần thẻ tín dụng).
2. Tạo tài khoản $\rightarrow$ Bấm **Create Cronjob**.
3. Cấu hình:
   - *Title*: `Keep Supabase Alive - ERP Copilot`
   - *URL*: `https://[BACKEND_CONTAINER_APP_URL]/health`
   - *Schedule*: Chọn **Every 2 days** (Cứ mỗi 2 ngày chạy 1 lần).
4. Bấm **Create**.
5. Mỗi 2 ngày cronjob sẽ gửi 1 request đến backend, backend sẽ thức dậy và duy trì kết nối với Supabase, đảm bảo hệ thống luôn luôn ở trạng thái trực tuyến.

---

## IV. CHECKLIST KIỂM TRA TRƯỚC KHI BÀN GIAO / ĐÁNH GIÁ

- [ ] `minReplicas` trên Azure Container Apps đã đặt chính xác là **`0`**.
- [ ] Docker image backend được lưu trên **`ghcr.io`**, không tạo Azure Container Registry.
- [ ] Plan của Azure Static Web Apps là gói **Free (0đ)**.
- [ ] Database Supabase đã chạy `seed_demo_data.py` và tạo đủ index HNSW cho pgvector.
- [ ] Supabase Storage đã tạo bucket `erp-documents` và gắn đúng S3 key.
- [ ] Biến `NEXT_PUBLIC_API_URL` trên Frontend trỏ chính xác về domain backend.
- [ ] Đã cài đặt Cron-job ping định kỳ mỗi 2 ngày.
- [ ] Đặt cảnh báo chi phí (Budget Alert) $10 trên Azure Portal để giám sát chi phí tổng thể = 0.
