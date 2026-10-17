"""
Migration script for Phase 5:
- Create erp.payments table for AR Cash / Bank receipt & debt deduction
- Create erp.stock_transfers table for inter-warehouse stock transfer
- Register permissions: payments:read, payments:create, inventory:transfer
- Assign new permissions to admin, sales_manager, warehouse_keeper
"""
import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text  # noqa: E402
from app.db.session import async_session_factory  # noqa: E402


async def migrate():
    print("[*] Starting Phase 5 Migration (Payments & Stock Transfers)...")
    async with async_session_factory() as session:
        # 1. Bảng erp.payments
        print("1. Creating erp.payments table...")
        await session.execute(text("""
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
        """))
        await session.execute(text("CREATE INDEX IF NOT EXISTS idx_payments_customer_id ON erp.payments(customer_id);"))
        await session.execute(text("CREATE INDEX IF NOT EXISTS idx_payments_order_id ON erp.payments(order_id);"))
        await session.execute(text("CREATE INDEX IF NOT EXISTS idx_payments_created_at ON erp.payments(created_at);"))

        # 2. Bảng erp.stock_transfers
        print("2. Creating erp.stock_transfers table...")
        await session.execute(text("""
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
        """))
        await session.execute(text("CREATE INDEX IF NOT EXISTS idx_transfers_product_id ON erp.stock_transfers(product_id);"))
        await session.execute(text("CREATE INDEX IF NOT EXISTS idx_transfers_source_wh ON erp.stock_transfers(source_warehouse_id);"))
        await session.execute(text("CREATE INDEX IF NOT EXISTS idx_transfers_target_wh ON erp.stock_transfers(target_warehouse_id);"))

        # 3. Đồng bộ Quyền hạn (Permissions)
        print("3. Registering new permissions...")
        new_permissions = [
            ("payments:read", "payments", "Xem phiếu thu tiền", "Xem danh sách và chi tiết phiếu thu tiền khách hàng"),
            ("payments:create", "payments", "Lập phiếu thu tiền", "Tạo phiếu thu tiền và cấn trừ công nợ bán hàng"),
            ("inventory:transfer", "inventory", "Điều chuyển kho", "Thực hiện điều chuyển hàng hóa giữa các kho nội bộ"),
        ]
        for code, module, name, desc in new_permissions:
            await session.execute(text("""
                INSERT INTO erp.permissions (id, code, module, name, description)
                VALUES (gen_random_uuid(), :code, :module, :name, :desc)
                ON CONFLICT (code) DO NOTHING;
            """), {"code": code, "module": module, "name": name, "desc": desc})

        # 4. Gán quyền vào Roles
        print("4. Granting permissions to standard roles...")
        role_assignments = [
            ("admin", ["payments:read", "payments:create", "inventory:transfer"]),
            ("director", ["payments:read"]),
            ("sales_manager", ["payments:read", "payments:create"]),
            ("warehouse_keeper", ["inventory:transfer"]),
        ]
        for role_code, perm_codes in role_assignments:
            for p_code in perm_codes:
                await session.execute(text("""
                    INSERT INTO erp.role_permissions (role_id, permission_id)
                    SELECT r.id, p.id
                    FROM erp.roles r, erp.permissions p
                    WHERE r.code = :role_code AND p.code = :perm_code
                    ON CONFLICT DO NOTHING;
                """), {"role_code": role_code, "perm_code": p_code})

        await session.commit()
        print("[+] Phase 5 Migration completed successfully!")


if __name__ == "__main__":
    asyncio.run(migrate())
