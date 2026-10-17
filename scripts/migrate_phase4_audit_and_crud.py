"""
Migration script for Phase 4 & CRUD Expansion:
- Expand erp.audit_logs: add actor_email, actor_role, ip_address, details (JSONB)
- Expand erp.products: add cost_price (NUMERIC 14,2) and check_product_cost_price constraint
- Expand erp.customers: ensure phone, address, credit_limit, current_debt exist
- Update erp.sales_orders: ensure check_sales_order_status includes 'cancelled' and 'delivered'
- Update erp.permissions: ensure customers:write, products:write, orders:cancel, audit:read exist
"""
import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text  # noqa: E402
from app.db.session import async_session_factory  # noqa: E402


async def migrate():
    print("[*] Starting Phase 4 & CRUD Schema Migration...")
    async with async_session_factory() as session:
        # 1. Bổ sung các cột mới vào erp.audit_logs
        print("1. Migrating erp.audit_logs...")
        await session.execute(text("""
            ALTER TABLE erp.audit_logs 
            ADD COLUMN IF NOT EXISTS actor_email VARCHAR(255),
            ADD COLUMN IF NOT EXISTS actor_role VARCHAR(50),
            ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45),
            ADD COLUMN IF NOT EXISTS details JSONB;
        """))

        # 2. Bổ sung cost_price vào erp.products
        print("2. Migrating erp.products (cost_price & constraint)...")
        await session.execute(text("""
            ALTER TABLE erp.products 
            ADD COLUMN IF NOT EXISTS cost_price NUMERIC(14, 2) NOT NULL DEFAULT 0.00;
        """))
        # Tính toán giá vốn mặc định cho các sản phẩm chưa có cost_price
        await session.execute(text("""
            UPDATE erp.products 
            SET cost_price = ROUND(unit_price * 0.65, 2) 
            WHERE cost_price IS NULL OR cost_price = 0;
        """))
        # Check constraint cho cost_price
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

        # 3. Đảm bảo erp.customers có đủ các trường tài chính & liên hệ
        print("3. Ensuring erp.customers fields...")
        await session.execute(text("""
            ALTER TABLE erp.customers 
            ADD COLUMN IF NOT EXISTS credit_limit NUMERIC(14, 2) NOT NULL DEFAULT 50000000,
            ADD COLUMN IF NOT EXISTS current_debt NUMERIC(14, 2) NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS phone VARCHAR(30),
            ADD COLUMN IF NOT EXISTS address TEXT;
        """))

        # 4. Đảm bảo trạng thái đơn hàng đầy đủ
        print("4. Updating erp.sales_orders status check constraint...")
        await session.execute(text("ALTER TABLE erp.sales_orders DROP CONSTRAINT IF EXISTS check_sales_order_status;"))
        await session.execute(text("""
            ALTER TABLE erp.sales_orders 
            ADD CONSTRAINT check_sales_order_status 
            CHECK (status IN ('draft', 'pending_approval', 'confirmed', 'cancelled', 'delivered'));
        """))

        # 5. Đảm bảo các quyền nguyên tử (permissions) cho CRUD mới
        print("5. Syncing new permissions into erp.permissions...")
        new_permissions = [
            ("customers:write", "customers", "Quản lý khách hàng", "Thêm mới và cập nhật thông tin khách hàng"),
            ("products:write", "products", "Quản lý sản phẩm", "Thêm, cập nhật sản phẩm và giá bán/vốn"),
            ("orders:cancel", "orders", "Hủy đơn hàng", "Hủy đơn hàng và hoàn trả tồn kho dự lưu"),
            ("audit:read", "audit", "Xem nhật ký kiểm toán", "Truy cập và tra cứu audit log hệ thống"),
        ]
        for code, module, name, desc in new_permissions:
            await session.execute(text("""
                INSERT INTO erp.permissions (id, code, module, name, description)
                VALUES (gen_random_uuid(), :code, :module, :name, :desc)
                ON CONFLICT (code) DO NOTHING;
            """), {"code": code, "module": module, "name": name, "desc": desc})

        # Gán quyền audit:read cho admin
        await session.execute(text("""
            INSERT INTO erp.role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM erp.roles r, erp.permissions p
            WHERE r.code = 'admin' AND p.code = 'audit:read'
            ON CONFLICT DO NOTHING;
        """))

        await session.commit()
        print("[+] Phase 4 & CRUD Migration completed successfully!")


if __name__ == "__main__":
    asyncio.run(migrate())
