"""
Unified Database Migration Runner for ERP AI Copilot
Runs all incremental schema migrations safely using IF NOT EXISTS / idempotency.
Usage:
    python scripts/migrate_all.py
"""
import asyncio
import sys
from pathlib import Path

# Add project root and backend directory to sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import async_session_factory, engine  # noqa: E402
import app.erp.models  # noqa: E402, F401
import app.rag.models  # noqa: E402, F401


async def run_all_migrations():
    print("=" * 60)
    print("[*] ERP AI COPILOT: UNIFIED DATABASE MIGRATION RUNNER")
    print("=" * 60)

    # Bước 1: Extensions, Schemas & Base Tables
    async with engine.begin() as conn:
        print("\n[Step 1/5] Ensuring PostgreSQL extensions and schemas...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS erp;"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS ai;"))

        print("[Step 1/5] Creating ORM base tables via metadata.create_all...")
        await conn.run_sync(Base.metadata.create_all)

        # RAG Indexes
        print("[Step 1/5] Ensuring RAG HNSW vector and full-text search indexes...")
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding 
            ON ai.document_chunks USING hnsw (embedding vector_cosine_ops);
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_document_chunks_fts 
            ON ai.document_chunks USING gin (to_tsvector('simple', content));
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_documents_access_scope 
            ON ai.documents (access_scope);
        """))

    async with async_session_factory() as session:
        # Bước 2: User profile & RBAC fields
        print("\n[Step 2/5] Ensuring User RBAC fields...")
        await session.execute(text("""
            ALTER TABLE erp.users 
            ADD COLUMN IF NOT EXISTS phone VARCHAR(30),
            ADD COLUMN IF NOT EXISTS department VARCHAR(100),
            ADD COLUMN IF NOT EXISTS job_title VARCHAR(100),
            ADD COLUMN IF NOT EXISTS is_superuser BOOLEAN DEFAULT FALSE NOT NULL,
            ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP WITH TIME ZONE,
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
        """))

        # Bước 3: Phase 1 (Stock Adjustments & Sales Order Delivered Status)
        print("\n[Step 3/5] Applying Phase 1 schema changes...")
        await session.execute(text("""
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
        """))

        # Bước 4: Phase 2 (Customer Credit & Address)
        print("\n[Step 4/5] Applying Phase 2 schema changes (Customer finances)...")
        await session.execute(text("""
            ALTER TABLE erp.customers 
            ADD COLUMN IF NOT EXISTS credit_limit NUMERIC(14, 2) NOT NULL DEFAULT 50000000,
            ADD COLUMN IF NOT EXISTS current_debt NUMERIC(14, 2) NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS phone VARCHAR(30),
            ADD COLUMN IF NOT EXISTS address TEXT;
        """))

        # Bước 5: Phase 4 & CRUD Expansion (Audit logs, Product cost_price, Constraints)
        print("\n[Step 5/5] Applying Phase 4 & CRUD schema changes (Audit logs, Cost Price, Permissions)...")
        # Audit logs columns
        await session.execute(text("""
            ALTER TABLE erp.audit_logs 
            ADD COLUMN IF NOT EXISTS actor_email VARCHAR(255),
            ADD COLUMN IF NOT EXISTS actor_role VARCHAR(50),
            ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45),
            ADD COLUMN IF NOT EXISTS details JSONB;
        """))

        # Product cost_price
        await session.execute(text("""
            ALTER TABLE erp.products 
            ADD COLUMN IF NOT EXISTS cost_price NUMERIC(14, 2) NOT NULL DEFAULT 0.00;
        """))
        await session.execute(text("""
            UPDATE erp.products 
            SET cost_price = ROUND(unit_price * 0.65, 2) 
            WHERE cost_price IS NULL OR cost_price = 0;
        """))
        await session.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'check_product_cost_price'
                ) THEN
                    ALTER TABLE erp.products ADD CONSTRAINT check_product_cost_price CHECK (cost_price >= 0);
                END IF;
            END
            $$;
        """))

        # Order status constraint update
        await session.execute(text("ALTER TABLE erp.sales_orders DROP CONSTRAINT IF EXISTS check_sales_order_status;"))
        await session.execute(text("""
            ALTER TABLE erp.sales_orders 
            ADD CONSTRAINT check_sales_order_status 
            CHECK (status IN ('draft', 'pending_approval', 'confirmed', 'cancelled', 'delivered'));
        """))

        # Sync Permissions
        permissions = [
            ("customers:write", "customers", "Quản lý khách hàng", "Thêm mới và cập nhật thông tin khách hàng"),
            ("products:write", "products", "Quản lý sản phẩm", "Thêm, cập nhật sản phẩm và giá bán/vốn"),
            ("orders:cancel", "orders", "Hủy đơn hàng", "Hủy đơn hàng và hoàn trả tồn kho dự lưu"),
            ("audit:read", "audit", "Xem nhật ký kiểm toán", "Truy cập và tra cứu audit log hệ thống"),
        ]
        for code, module, name, desc in permissions:
            await session.execute(text("""
                INSERT INTO erp.permissions (id, code, module, name, description)
                VALUES (gen_random_uuid(), :code, :module, :name, :desc)
                ON CONFLICT (code) DO NOTHING;
            """), {"code": code, "module": module, "name": name, "desc": desc})

        # Gán audit:read cho admin nếu có role admin
        await session.execute(text("""
            INSERT INTO erp.role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM erp.roles r, erp.permissions p
            WHERE r.code = 'admin' AND p.code = 'audit:read'
            ON CONFLICT DO NOTHING;
        """))

        await session.commit()

    # Bước 6: Phase 5 - Payments & Transfers
    print("\n[Step 5/6] Running Phase 5 Migrations (Payments & Transfers)...")
    from scripts.migrate_phase5_payments_and_transfers import migrate as migrate_phase5
    await migrate_phase5()

    # Bước 7: Phase 6 - Purchasing & Suppliers
    print("\n[Step 6/7] Running Phase 6 Migrations (Purchasing & Suppliers)...")
    from scripts.migrate_phase6_purchasing import migrate as migrate_phase6
    await migrate_phase6()

    # Bước 8: Phase 7 - Order Ingestion Revamp & Backorders
    print("\n[Step 7/7] Running Phase 7 Migrations (Order Ingestion Revamp & Backorder)...")
    from scripts.migrate_phase7_order_ingestion_revamp import migrate as migrate_phase7
    await migrate_phase7()

    print("\n" + "=" * 60)
    print("[+] ALL DATABASE MIGRATIONS COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_migrations())
