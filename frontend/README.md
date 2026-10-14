# 💻 ERP AI Copilot - Frontend Web Application

Giao diện người dùng Web hiện đại dành cho hệ thống **ERP AI Copilot**, xây dựng trên **Next.js 16 (App Router)**, **React 19**, **Tailwind CSS v4** và **Lucide Icons**.

---

## 🌟 Tính năng chính

1. **🔐 Authentication & Phân quyền (RBAC)**:
   - Đăng nhập xác thực JWT, tự động lưu token vào `localStorage` và đồng bộ qua Context.
   - Hỗ trợ tài khoản `admin` (toàn quyền) và `sales_rep` (giới hạn quyền hạn).
   - Bảo vệ toàn bộ các trang nội bộ (chuyển hướng về `/login` nếu chưa đăng nhập).

2. **🤖 AI Copilot Workspace (`/copilot`)**:
   - **Realtime SSE Streaming**: Nhận phản hồi từng token theo thời gian thực (Time-to-first-token < 1s).
   - **Luồng suy nghĩ của AI (Thought Process Stream)**: Hiển thị minh bạch từng bước xử lý của AI (Phân tích ý định, kết nối CSDL ERP, truy xuất kho tài liệu RAG, lập đơn hàng nháp, v.v.).
   - Quản lý lịch sử hội thoại đa vòng (Multi-turn conversation sessions), tạo phiên mới và xóa phiên chat.
   - Hiển thị Markdown phong phú (Bảng biểu số liệu, danh sách, khối cảnh báo, citations nguồn tài liệu).

3. **📥 Hộp thư Phê duyệt Human-in-The-Loop (`/approvals`)**:
   - Quản lý các đơn đặt hàng nháp được AI trích xuất tự động từ Email/Tài liệu.
   - Xem chi tiết đơn hàng, danh sách sản phẩm, cảnh báo lệch giá hoặc tồn kho.
   - Thao tác phê duyệt (Chuyển sang `confirmed`, giữ chỗ tồn kho) hoặc từ chối kèm lý do.

4. **📊 Báo cáo Doanh thu & Thống kê (`/revenue`)**:
   - Thống kê doanh thu thực tế từ CSDL theo tháng/kỳ.
   - Biểu đồ và bảng dữ liệu doanh thu chi tiết.

5. **📚 Quản trị Tài liệu Doanh nghiệp (`/documents`)**:
   - Tải lên tài liệu chính sách, quy chế công ty (PDF, Word, TXT, Markdown).
   - Tải trực tiếp tài liệu gốc thông qua MinIO S3 Presigned URL an toàn.

---

## 🚀 Khởi chạy ứng dụng

### Yêu cầu:
- [Node.js 18+](https://nodejs.org/)
- Backend FastAPI đang chạy tại cổng `8000` (`http://localhost:8000`)

### Cài đặt và Chạy:
```bash
# Cài đặt dependencies
npm install

# Khởi chạy server phát triển
npm run dev
```

Truy cập: **[http://localhost:3000](http://localhost:3000)**

---

## 📁 Cấu trúc thư mục

```text
frontend/
├── app/
│   ├── approvals/page.tsx      # Trang Hộp thư Phê duyệt HITL
│   ├── copilot/page.tsx        # Trang AI Copilot Workspace
│   ├── documents/page.tsx      # Trang Quản trị Tài liệu Doanh nghiệp
│   ├── login/page.tsx          # Trang Đăng nhập hệ thống
│   ├── revenue/page.tsx        # Trang Báo cáo Doanh thu & Thống kê
│   ├── layout.tsx              # Root Layout
│   └── page.tsx                # Trang chủ điều hướng
├── components/
│   ├── ai-thought-process.tsx  # Component hiển thị luồng suy nghĩ của AI
│   ├── app-layout-wrapper.tsx  # Wrapper bố cục chính kèm Auth check
│   ├── header.tsx              # Top Header thông tin người dùng
│   └── sidebar.tsx             # Thanh điều hướng bên trái
├── lib/
│   ├── api.ts                  # Client SDK gọi REST API & SSE Stream backend
│   └── auth-context.tsx        # React Context quản lý phiên đăng nhập
└── public/                     # Static assets
```
