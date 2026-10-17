"""
Migration script for Phase 6:
- Create erp.suppliers table
- Create erp.purchase_orders table
- Create erp.purchase_order_items table
- Register permissions: purchasing:read, purchasing:create, purchasing:receive, purchasing:cancel
- Assign new permissions to admin, sales_manager, warehouse_keeper, director
- Seed demo suppliers
"""
import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text  # noqa: E402
from app.db.session import async_session_factory  # noqa: E402


async def migrate():
    print("[*] Starting Phase 6 Migration (Purchasing & Suppliers)...")
    async with async_session_factory() as session:
        # 1. Bảng erp.suppliers
        print("1. Creating erp.suppliers table...")
        await session.execute(text("""
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
        """))
        await session.execute(text("CREATE INDEX IF NOT EXISTS idx_suppliers_code ON erp.suppliers(code);"))
        await session.execute(text("CREATE INDEX IF NOT EXISTS idx_suppliers_status ON erp.suppliers(status);"))

        # 2. Bảng erp.purchase_orders
        print("2. Creating erp.purchase_orders table...")
        await session.execute(text("""
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
        """))
        await session.execute(text("CREATE INDEX IF NOT EXISTS idx_po_supplier_id ON erp.purchase_orders(supplier_id);"))
        await session.execute(text("CREATE INDEX IF NOT EXISTS idx_po_warehouse_id ON erp.purchase_orders(warehouse_id);"))
        await session.execute(text("CREATE INDEX IF NOT EXISTS idx_po_status ON erp.purchase_orders(status);"))
        await session.execute(text("CREATE INDEX IF NOT EXISTS idx_po_created_at ON erp.purchase_orders(created_at);"))

        # 3. Bảng erp.purchase_order_items
        print("3. Creating erp.purchase_order_items table...")
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS erp.purchase_order_items (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                po_id UUID NOT NULL REFERENCES erp.purchase_orders(id) ON DELETE CASCADE,
                product_id UUID NOT NULL REFERENCES erp.products(id),
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                unit_price NUMERIC(14, 2) NOT NULL CHECK (unit_price >= 0),
                line_total NUMERIC(14, 2) NOT NULL CHECK (line_total >= 0)
            );
        """))
        await session.execute(text("CREATE INDEX IF NOT EXISTS idx_po_items_po_id ON erp.purchase_order_items(po_id);"))
        await session.execute(text("CREATE INDEX IF NOT EXISTS idx_po_items_product_id ON erp.purchase_order_items(product_id);"))

        # 4. Đồng bộ Quyền hạn (Permissions)
        print("4. Registering purchasing permissions...")
        new_permissions = [
            ("purchasing:read", "purchasing", "Xem đơn mua hàng", "Xem danh sách và chi tiết đơn mua hàng PO"),
            ("purchasing:create", "purchasing", "Tạo đơn mua hàng", "Lập đơn mua hàng PO mới và gửi nhà cung cấp"),
            ("purchasing:receive", "purchasing", "Nhập kho đơn mua hàng", "Xác nhận nhận hàng từ PO và tăng số lượng tồn kho"),
            ("purchasing:cancel", "purchasing", "Hủy đơn mua hàng", "Hủy đơn mua hàng chưa nhập kho"),
        ]
        for code, module, name, desc in new_permissions:
            await session.execute(text("""
                INSERT INTO erp.permissions (id, code, module, name, description)
                VALUES (gen_random_uuid(), :code, :module, :name, :desc)
                ON CONFLICT (code) DO UPDATE SET 
                    module = EXCLUDED.module,
                    name = EXCLUDED.name,
                    description = EXCLUDED.description;
            """), {"code": code, "module": module, "name": name, "desc": desc})

        # 5. Gán quyền cho Roles
        print("5. Assigning permissions to roles...")
        role_assignments = {
            "warehouse_keeper": ["purchasing:read", "purchasing:receive"],
            "sales_manager": ["purchasing:read", "purchasing:create", "purchasing:cancel"],
            "director": ["purchasing:read"],
        }

        for role_name, perm_codes in role_assignments.items():
            for perm_code in perm_codes:
                await session.execute(text("""
                    INSERT INTO erp.role_permissions (role_id, permission_id)
                    SELECT r.id, p.id
                    FROM erp.roles r, erp.permissions p
                    WHERE (r.code = :role_name OR r.name = :role_name) AND p.code = :perm_code
                    ON CONFLICT DO NOTHING;
                """), {"role_name": role_name, "perm_code": perm_code})

        # Ensure column ID defaults
        await session.execute(text("ALTER TABLE erp.suppliers ALTER COLUMN id SET DEFAULT gen_random_uuid();"))
        await session.execute(text("ALTER TABLE erp.purchase_orders ALTER COLUMN id SET DEFAULT gen_random_uuid();"))
        await session.execute(text("ALTER TABLE erp.purchase_order_items ALTER COLUMN id SET DEFAULT gen_random_uuid();"))

        # 6. Seed demo suppliers
        print("6. Seeding demo suppliers...")
        demo_suppliers = [
            ("NCC-HP", "Công ty TNHH HP Vietnam", "0100109106", "contact@hp.com.vn", "024-3935-1234", "Tòa nhà Landmark 72, Phạm Hùng, Hà Nội"),
            ("NCC-DELL", "Công ty TNHH Dell Technologies Vietnam", "0304910283", "sales@dell.com.vn", "028-3823-9999", "Tòa nhà Sun Wah Tower, Nguyễn Huệ, Q.1, TP.HCM"),
            ("NCC-SAMSUNG", "Công ty TNHH Điện tử Samsung Vina", "0301111928", "b2b.vn@samsung.com", "028-3915-7310", "Tòa nhà Bitexco Financial Tower, Q.1, TP.HCM"),
        ]
        for code, name, tax, email, phone, addr in demo_suppliers:
            await session.execute(text("""
                INSERT INTO erp.suppliers (id, code, name, tax_code, contact_email, phone, address, status)
                VALUES (gen_random_uuid(), :code, :name, :tax, :email, :phone, :addr, 'active')
                ON CONFLICT (code) DO NOTHING;
            """), {"code": code, "name": name, "tax": tax, "email": email, "phone": phone, "addr": addr})

        await session.commit()
        print("[+] Phase 6 Migration completed successfully!")


if __name__ == "__main__":
    asyncio.run(migrate())
