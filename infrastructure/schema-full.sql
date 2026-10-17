-- ==============================================================================
-- ERP AI COPILOT - FULL POSTGRESQL SCHEMA SPECIFICATION
-- Database Engine: PostgreSQL 15+ (pgcrypto, pgvector)
-- Last Updated: Phase 4 & Full CRUD Expansion
-- ==============================================================================

-- 1. EXTENSIONS
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. SCHEMAS
CREATE SCHEMA IF NOT EXISTS erp;
CREATE SCHEMA IF NOT EXISTS ai;

-- ==============================================================================
-- SCHEMA: erp (Enterprise Core Models)
-- ==============================================================================

-- Bảng Người dùng (Users & RBAC)
CREATE TABLE IF NOT EXISTS erp.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    phone VARCHAR(30),
    department VARCHAR(100),
    job_title VARCHAR(100),
    role VARCHAR(50) NOT NULL DEFAULT 'sales_rep',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_users_email ON erp.users(email);

-- Bảng Vai trò (Roles)
CREATE TABLE IF NOT EXISTS erp.roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_system BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_roles_code ON erp.roles(code);

-- Bảng Quyền hạn (Permissions)
CREATE TABLE IF NOT EXISTS erp.permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) UNIQUE NOT NULL,
    module VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT
);
CREATE INDEX IF NOT EXISTS idx_permissions_code ON erp.permissions(code);
CREATE INDEX IF NOT EXISTS idx_permissions_module ON erp.permissions(module);

-- Bảng Liên kết Vai trò - Quyền hạn (Role Permissions)
CREATE TABLE IF NOT EXISTS erp.role_permissions (
    role_id UUID NOT NULL REFERENCES erp.roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES erp.permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

-- Bảng Liên kết Người dùng - Vai trò (User Roles)
CREATE TABLE IF NOT EXISTS erp.user_roles (
    user_id UUID NOT NULL REFERENCES erp.users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES erp.roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

-- Bảng Phiên đăng nhập & Refresh Token (User Sessions)
CREATE TABLE IF NOT EXISTS erp.user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES erp.users(id) ON DELETE CASCADE,
    refresh_token_hash VARCHAR(64) UNIQUE NOT NULL,
    user_agent TEXT,
    ip_address VARCHAR(45),
    expires_at TIMESTAMPTZ NOT NULL,
    is_revoked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON erp.user_sessions(refresh_token_hash);
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON erp.user_sessions(user_id);

-- Bảng Khách hàng (Customers)
CREATE TABLE IF NOT EXISTS erp.customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(30) UNIQUE NOT NULL,
    name TEXT NOT NULL,
    email TEXT,
    phone VARCHAR(30),
    address TEXT,
    credit_limit NUMERIC(14, 2) NOT NULL DEFAULT 50000000.00,
    current_debt NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    status TEXT NOT NULL DEFAULT 'active',
    CONSTRAINT check_customer_status CHECK (status IN ('active', 'inactive'))
);
CREATE INDEX IF NOT EXISTS idx_customers_code ON erp.customers(code);

-- Bảng Sản phẩm (Products)
CREATE TABLE IF NOT EXISTS erp.products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sku VARCHAR(50) UNIQUE NOT NULL,
    name TEXT NOT NULL,
    unit_price NUMERIC(14, 2) NOT NULL,
    cost_price NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT check_product_unit_price CHECK (unit_price >= 0),
    CONSTRAINT check_product_cost_price CHECK (cost_price >= 0)
);
CREATE INDEX IF NOT EXISTS idx_products_sku ON erp.products(sku);

-- Bảng Kho hàng (Warehouses)
CREATE TABLE IF NOT EXISTS erp.warehouses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL
);

-- Bảng Tồn kho (Inventory)
CREATE TABLE IF NOT EXISTS erp.inventory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES erp.products(id),
    warehouse_id UUID NOT NULL REFERENCES erp.warehouses(id),
    quantity_on_hand INTEGER NOT NULL DEFAULT 0,
    quantity_reserved INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT check_inventory_on_hand CHECK (quantity_on_hand >= 0),
    CONSTRAINT check_inventory_reserved CHECK (quantity_reserved >= 0),
    CONSTRAINT check_reserved_le_on_hand CHECK (quantity_reserved <= quantity_on_hand)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_product_warehouse ON erp.inventory(product_id, warehouse_id);

-- Bảng Điều chỉnh tồn kho (Stock Adjustments - Phase 1)
CREATE TABLE IF NOT EXISTS erp.stock_adjustments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES erp.products(id),
    warehouse_id UUID NOT NULL REFERENCES erp.warehouses(id),
    sku VARCHAR(50) NOT NULL,
    warehouse_code VARCHAR(50) NOT NULL,
    delta_quantity INTEGER NOT NULL,
    quantity_before INTEGER NOT NULL,
    quantity_after INTEGER NOT NULL,
    reason TEXT NOT NULL,
    adjusted_by UUID NOT NULL REFERENCES erp.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Bảng Đơn bán hàng (Sales Orders)
CREATE TABLE IF NOT EXISTS erp.sales_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number TEXT UNIQUE NOT NULL,
    customer_id UUID NOT NULL REFERENCES erp.customers(id),
    status TEXT NOT NULL DEFAULT 'draft',
    total_amount NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    created_by UUID NOT NULL REFERENCES erp.users(id),
    approved_by UUID REFERENCES erp.users(id),
    rejection_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT check_sales_order_status CHECK (
        status IN ('draft', 'pending_approval', 'confirmed', 'cancelled', 'delivered')
    )
);
CREATE INDEX IF NOT EXISTS idx_sales_orders_customer_id ON erp.sales_orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_sales_orders_status ON erp.sales_orders(status);

-- Bảng Chi tiết đơn bán hàng (Sales Order Items)
CREATE TABLE IF NOT EXISTS erp.sales_order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES erp.sales_orders(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES erp.products(id),
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(14, 2) NOT NULL,
    line_total NUMERIC(14, 2) NOT NULL,
    CONSTRAINT check_sales_order_item_qty CHECK (quantity > 0)
);

-- Bảng Nhật ký kiểm toán bảo mật (Audit Logs - Phase 4)
CREATE TABLE IF NOT EXISTS erp.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id UUID REFERENCES erp.users(id),
    actor_email VARCHAR(255),
    actor_role VARCHAR(50),
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT,
    ip_address VARCHAR(45),
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON erp.audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_id ON erp.audit_logs(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON erp.audit_logs(created_at);

-- Bảng Khóa Idempotency tránh trùng lặp thao tác
CREATE TABLE IF NOT EXISTS erp.idempotency_keys (
    key VARCHAR(255) PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES erp.users(id),
    action TEXT NOT NULL,
    response_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

-- ==============================================================================
-- SCHEMA: ai (RAG & Knowledge Base)
-- ==============================================================================

-- Bảng Tài liệu RAG
CREATE TABLE IF NOT EXISTS ai.documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    content_hash VARCHAR(64) UNIQUE NOT NULL,
    access_scope VARCHAR(50) NOT NULL DEFAULT 'internal',
    owner_id UUID REFERENCES erp.users(id),
    department VARCHAR(100),
    status VARCHAR(50) NOT NULL DEFAULT 'indexed',
    metadata_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_documents_access_scope ON ai.documents(access_scope);
CREATE INDEX IF NOT EXISTS idx_documents_owner_id ON ai.documents(owner_id);

-- Bảng Đoạn cắt văn bản & Vector Embedding (Document Chunks)
CREATE TABLE IF NOT EXISTS ai.document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES ai.documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- HNSW Vector Index cho tìm kiếm ngữ nghĩa
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding 
ON ai.document_chunks USING hnsw (embedding vector_cosine_ops);

-- GIN Index cho tìm kiếm từ khóa Sparse Full-Text Search
CREATE INDEX IF NOT EXISTS idx_document_chunks_fts 
ON ai.document_chunks USING gin (to_tsvector('simple', content));

-- Bảng Phiên hội thoại Copilot (Conversations)
CREATE TABLE IF NOT EXISTS ai.conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES erp.users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Bảng Lịch sử tin nhắn AI (Messages)
CREATE TABLE IF NOT EXISTS ai.messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES ai.conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    thought_steps JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- PHẦN 8: PHASE 5 - THU TIỀN BÁN HÀNG & ĐIỀU CHUYỂN KHO
-- ============================================================================

-- Bảng Phiếu thu tiền bán hàng & Cấn trừ nợ
CREATE TABLE IF NOT EXISTS erp.payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_number VARCHAR(50) UNIQUE NOT NULL,
    customer_id UUID NOT NULL REFERENCES erp.customers(id),
    order_id UUID REFERENCES erp.sales_orders(id),
    amount NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
    payment_method VARCHAR(30) NOT NULL DEFAULT 'bank_transfer',
    reference_code VARCHAR(100),
    note TEXT,
    received_by UUID NOT NULL REFERENCES erp.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_payments_customer_id ON erp.payments(customer_id);
CREATE INDEX IF NOT EXISTS idx_payments_order_id ON erp.payments(order_id);
CREATE INDEX IF NOT EXISTS idx_payments_created_at ON erp.payments(created_at);

-- Bảng Phiếu điều chuyển hàng hóa liên kho nội bộ
CREATE TABLE IF NOT EXISTS erp.stock_transfers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transfer_number VARCHAR(50) UNIQUE NOT NULL,
    source_warehouse_id UUID NOT NULL REFERENCES erp.warehouses(id),
    target_warehouse_id UUID NOT NULL REFERENCES erp.warehouses(id),
    product_id UUID NOT NULL REFERENCES erp.products(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    reason TEXT NOT NULL,
    transferred_by UUID NOT NULL REFERENCES erp.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_transfers_product_id ON erp.stock_transfers(product_id);
CREATE INDEX IF NOT EXISTS idx_transfers_source_wh ON erp.stock_transfers(source_warehouse_id);
CREATE INDEX IF NOT EXISTS idx_transfers_target_wh ON erp.stock_transfers(target_warehouse_id);

-- ============================================================================
-- PHẦN 9: PHASE 6 - MUA HÀNG & NHÀ CUNG CẤP (PURCHASING)
-- ============================================================================

-- Bảng Nhà cung cấp (Suppliers)
CREATE TABLE IF NOT EXISTS erp.suppliers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    tax_code VARCHAR(50),
    contact_email VARCHAR(100),
    phone VARCHAR(50),
    address TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_suppliers_code ON erp.suppliers(code);
CREATE INDEX IF NOT EXISTS idx_suppliers_status ON erp.suppliers(status);

-- Bảng Đơn đặt mua hàng (Purchase Orders)
CREATE TABLE IF NOT EXISTS erp.purchase_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    po_number VARCHAR(50) UNIQUE NOT NULL,
    supplier_id UUID NOT NULL REFERENCES erp.suppliers(id),
    warehouse_id UUID NOT NULL REFERENCES erp.warehouses(id),
    status VARCHAR(30) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'ordered', 'received', 'cancelled')),
    total_amount NUMERIC(14, 2) NOT NULL DEFAULT 0.00 CHECK (total_amount >= 0),
    notes TEXT,
    created_by UUID NOT NULL REFERENCES erp.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_po_supplier_id ON erp.purchase_orders(supplier_id);
CREATE INDEX IF NOT EXISTS idx_po_warehouse_id ON erp.purchase_orders(warehouse_id);
CREATE INDEX IF NOT EXISTS idx_po_status ON erp.purchase_orders(status);
CREATE INDEX IF NOT EXISTS idx_po_created_at ON erp.purchase_orders(created_at);

-- Bảng Chi tiết các mặt hàng mua (Purchase Order Items)
CREATE TABLE IF NOT EXISTS erp.purchase_order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    po_id UUID NOT NULL REFERENCES erp.purchase_orders(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES erp.products(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(14, 2) NOT NULL CHECK (unit_price >= 0),
    line_total NUMERIC(14, 2) NOT NULL CHECK (line_total >= 0)
);
CREATE INDEX IF NOT EXISTS idx_po_items_po_id ON erp.purchase_order_items(po_id);
CREATE INDEX IF NOT EXISTS idx_po_items_product_id ON erp.purchase_order_items(product_id);
