"""
Seed Demo Data Script for ERP AI Copilot
Creates deterministic sample data:
- Users (admin, sales_rep)
- Customers (CUS-0001 ...)
- Products (SKU-001 ...)
- Warehouses (WH-HN, WH-HCM)
- Inventory levels
- Sample Sales Orders
"""

import asyncio
import sys
import os
from decimal import Decimal
from datetime import datetime, timezone

# Ensure backend/ directory is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import Base
from app.db.session import engine, async_session_factory
from app.erp.models import User, Customer, Product, Warehouse, Inventory, SalesOrder, SalesOrderItem
from app.auth.security import get_password_hash
import app.rag.models  # noqa: F401


async def seed_data():
    print("[*] Starting ERP demo data seeding...")
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS erp;"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS ai;"))
        await conn.run_sync(Base.metadata.create_all)

        # Ensure RAG specific vector and full-text indexes exist
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding "
                "ON ai.document_chunks USING hnsw (embedding vector_cosine_ops);"
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_document_chunks_fts "
                "ON ai.document_chunks USING gin (to_tsvector('simple', content));"
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_documents_access_scope "
                "ON ai.documents (access_scope);"
            )
        )
        # Ensure User table has newly added RBAC fields
        await conn.execute(text("ALTER TABLE erp.users ADD COLUMN IF NOT EXISTS phone VARCHAR(30);"))
        await conn.execute(text("ALTER TABLE erp.users ADD COLUMN IF NOT EXISTS department VARCHAR(100);"))
        await conn.execute(text("ALTER TABLE erp.users ADD COLUMN IF NOT EXISTS job_title VARCHAR(100);"))
        await conn.execute(text("ALTER TABLE erp.users ADD COLUMN IF NOT EXISTS is_superuser BOOLEAN DEFAULT FALSE NOT NULL;"))
        await conn.execute(text("ALTER TABLE erp.users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP WITH TIME ZONE;"))
        await conn.execute(text("ALTER TABLE erp.users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();"))


        await conn.execute(
            text(
                "TRUNCATE erp.sales_order_items, erp.sales_orders, erp.inventory, "
                "erp.products, erp.customers, erp.warehouses, erp.user_sessions, "
                "erp.user_roles, erp.role_permissions, erp.permissions, erp.roles, "
                "erp.users, erp.idempotency_keys RESTART IDENTITY CASCADE;"
            )
        )

    from app.erp.models import Role, Permission, RolePermission, UserRole
    import uuid

    async with async_session_factory() as session:
        # 1. Khởi tạo danh mục Permissions (Quyền hạn nguyên tử)
        permissions_data = [
            # Đơn hàng
            ("orders:read", "orders", "Xem đơn hàng", "Xem danh sách và chi tiết đơn hàng"),
            ("orders:read_all", "orders", "Xem toàn bộ đơn hàng", "Xem đơn hàng của tất cả nhân viên"),
            ("orders:create", "orders", "Tạo đơn hàng", "Tạo mới đơn hàng nháp"),
            ("orders:approve", "orders", "Phê duyệt đơn hàng", "Phê duyệt đơn hàng nháp"),
            ("orders:reject", "orders", "Từ chối đơn hàng", "Từ chối đơn hàng nháp"),
            ("orders:cancel", "orders", "Hủy đơn hàng", "Hủy đơn hàng do mình tạo"),
            # Khách hàng
            ("customers:read", "customers", "Xem khách hàng", "Tra cứu thông tin khách hàng"),
            ("customers:write", "customers", "Quản lý khách hàng", "Thêm mới và cập nhật thông tin khách hàng"),
            # Sản phẩm & Tồn kho
            ("products:read", "products", "Xem sản phẩm & giá", "Tra cứu sản phẩm và giá niêm yết"),
            ("products:write", "products", "Quản lý sản phẩm", "Thêm, cập nhật sản phẩm và giá bán"),
            ("inventory:read", "inventory", "Xem tồn kho", "Tra cứu số lượng tồn kho và khả dụng"),
            ("inventory:write", "inventory", "Điều chỉnh kho", "Cập nhật số lượng kiểm kê và chuyển kho"),
            # Báo cáo
            ("reports:revenue_view", "reports", "Xem báo cáo doanh thu", "Xem báo cáo doanh thu và biểu đồ phân tích"),
            ("reports:export", "reports", "Xuất báo cáo", "Xuất file báo cáo tài chính"),
            # Tài liệu & RAG
            ("documents:read", "documents", "Tra cứu tài liệu", "Xem và tìm kiếm tài liệu chung"),
            ("documents:read_confidential", "documents", "Xem tài liệu mật", "Đọc các tài liệu quản trị nội bộ bí mật"),
            ("documents:upload", "documents", "Tải lên tài liệu", "Nạp tài liệu vào hệ thống RAG"),
            ("documents:delete", "documents", "Xóa tài liệu", "Xóa tài liệu khỏi hệ thống"),
            # Quản trị
            ("users:read", "users", "Xem người dùng", "Xem danh sách nhân sự"),
            ("users:write", "users", "Quản lý người dùng", "Tạo, cập nhật và khóa tài khoản nhân sự"),
            ("roles:manage", "roles", "Quản lý phân quyền", "Tạo vai trò và cấu hình ma trận quyền hạn"),
        ]

        perm_dict = {}
        for code, mod, name, desc in permissions_data:
            p = Permission(
                id=uuid.uuid4(),
                code=code,
                module=mod,
                name=name,
                description=desc,
            )
            session.add(p)
            perm_dict[code] = p

        await session.flush()

        # 2. Khởi tạo 5 Vai trò chuẩn (5 Core Roles)
        roles_data = [
            ("admin", "Quản Trị Viên", "Toàn quyền cấu hình, quản trị người dùng và giám sát hệ thống", True),
            ("director", "Ban Giám Đốc", "Xem báo cáo tài chính toàn diện, phê duyệt đơn hàng lớn và đọc tài liệu mật", True),
            ("sales_manager", "Quản Lý Kinh Doanh", "Phê duyệt đơn hàng, xem báo cáo doanh thu và giám sát toàn bộ đơn bán", True),
            ("sales_rep", "Nhân Viên Kinh Doanh", "Lập đơn hàng nháp, tra cứu tồn kho, tìm kiếm khách hàng và hỏi đáp quy chế", True),
            ("warehouse_keeper", "Thủ Kho", "Quản lý tồn kho thực tế, xem các đơn hàng đã chốt để đóng gói xuất hàng", True),
        ]

        role_dict = {}
        for code, name, desc, is_sys in roles_data:
            r = Role(
                id=uuid.uuid4(),
                code=code,
                name=name,
                description=desc,
                is_system=is_sys,
            )
            session.add(r)
            role_dict[code] = r

        await session.flush()

        # 3. Gán Quyền cho 5 Vai trò theo Ma trận Phân quyền
        role_perm_mappings = {
            "admin": list(perm_dict.keys()),  # Toàn quyền
            "director": [
                "reports:revenue_view", "reports:export",
                "orders:read", "orders:read_all", "orders:approve",
                "customers:read", "products:read", "inventory:read",
                "documents:read", "documents:read_confidential",
            ],
            "sales_manager": [
                "reports:revenue_view", "reports:export",
                "orders:read", "orders:read_all", "orders:create", "orders:approve", "orders:reject",
                "customers:read", "customers:write",
                "products:read", "inventory:read",
                "documents:read",
            ],
            "sales_rep": [
                "orders:read", "orders:create", "orders:cancel",
                "customers:read", "products:read", "inventory:read",
                "documents:read",
            ],
            "warehouse_keeper": [
                "inventory:read", "inventory:write",
                "orders:read",
                "products:read",
                "customers:read",
                "documents:read",
            ],
        }

        for role_code, perm_codes in role_perm_mappings.items():
            r = role_dict[role_code]
            for p_code in perm_codes:
                if p_code in perm_dict:
                    session.add(RolePermission(role_id=r.id, permission_id=perm_dict[p_code].id))

        await session.flush()

        # 4. Khởi tạo 5 Người Dùng Mẫu ứng với 5 Vai Trò
        users_seed_data = [
            {
                "email": "admin@erpcopilot.vn",
                "password": "admin123",
                "full_name": "Quản Trị Viên Hệ Thống",
                "role_code": "admin",
                "department": "Công nghệ thông tin",
                "job_title": "IT Director",
                "is_superuser": True,
            },
            {
                "email": "director@erpcopilot.vn",
                "password": "director123",
                "full_name": "Trần Thị Ban Giám Đốc",
                "role_code": "director",
                "department": "Ban Điều Hành",
                "job_title": "Managing Director",
                "is_superuser": False,
            },
            {
                "email": "manager@erpcopilot.vn",
                "password": "manager123",
                "full_name": "Lê Văn Quản Lý",
                "role_code": "sales_manager",
                "department": "Phòng Kinh Doanh",
                "job_title": "Head of Sales",
                "is_superuser": False,
            },
            {
                "email": "sales@erpcopilot.vn",
                "password": "sales123",
                "full_name": "Nguyễn Văn Bán Hàng",
                "role_code": "sales_rep",
                "department": "Phòng Kinh Doanh",
                "job_title": "Sales Executive",
                "is_superuser": False,
            },
            {
                "email": "warehouse@erpcopilot.vn",
                "password": "warehouse123",
                "full_name": "Phạm Văn Thủ Kho",
                "role_code": "warehouse_keeper",
                "department": "Phòng Kho Vận",
                "job_title": "Warehouse Supervisor",
                "is_superuser": False,
            },
        ]

        created_users = {}
        for u_data in users_seed_data:
            user = User(
                id=uuid.uuid4(),
                email=u_data["email"],
                password_hash=get_password_hash(u_data["password"]),
                full_name=u_data["full_name"],
                role=u_data["role_code"],
                department=u_data["department"],
                job_title=u_data["job_title"],
                is_active=True,
                is_superuser=u_data["is_superuser"],
            )
            session.add(user)
            created_users[u_data["role_code"]] = user

        await session.flush()

        # Gán UserRole
        for role_code, user in created_users.items():
            r = role_dict[role_code]
            session.add(UserRole(user_id=user.id, role_id=r.id))

        admin_user = created_users["admin"]
        sales_user = created_users["sales_rep"]

        # 2. Warehouses
        wh_hn = Warehouse(code="WH-HN", name="Kho Tổng Hà Nội")
        wh_hcm = Warehouse(code="WH-HCM", name="Kho Tổng Hồ Chí Minh")
        session.add_all([wh_hn, wh_hcm])
        await session.flush()

        # 3. Customers
        customers = [
            Customer(code="CUS-0001", name="Công ty TNHH Công Nghệ Á Châu", email="contact@asiatech.vn", status="active"),
            Customer(code="CUS-0002", name="Tập đoàn Bán lẻ Toàn Cầu", email="purchasing@globalretail.com", status="active"),
            Customer(code="CUS-0003", name="Công ty Cổ phần May Mặc Việt", email="info@vietgarment.vn", status="active"),
            Customer(code="CUS-0004", name="Công ty TNHH Phân Phối Miền Tây", email="sales@mientaydist.vn", status="active"),
            Customer(code="CUS-0005", name="Chuỗi Siêu thị Xanh", email="order@greensuper.vn", status="active"),
        ]
        session.add_all(customers)
        await session.flush()

        # 4. Products
        products = [
            Product(sku="SKU-001", name="Laptop Pro 14-inch M3", unit_price=Decimal("28500000.00"), is_active=True),
            Product(sku="SKU-002", name="Màn hình Dell UltraSharp 27-inch 4K", unit_price=Decimal("12900000.00"), is_active=True),
            Product(sku="SKU-003", name="Bàn phím cơ không dây Silent", unit_price=Decimal("2450000.00"), is_active=True),
            Product(sku="SKU-004", name="Chuột Ergonomic Bluetooth", unit_price=Decimal("1150000.00"), is_active=True),
            Product(sku="SKU-005", name="Tai nghe chống ồn chủ động ANC", unit_price=Decimal("4600000.00"), is_active=True),
        ]
        session.add_all(products)
        await session.flush()

        # 5. Inventory
        inventories = [
            Inventory(product_id=products[0].id, warehouse_id=wh_hn.id, quantity_on_hand=50, quantity_reserved=5),
            Inventory(product_id=products[0].id, warehouse_id=wh_hcm.id, quantity_on_hand=70, quantity_reserved=10),
            Inventory(product_id=products[1].id, warehouse_id=wh_hn.id, quantity_on_hand=80, quantity_reserved=0),
            Inventory(product_id=products[1].id, warehouse_id=wh_hcm.id, quantity_on_hand=40, quantity_reserved=5),
            Inventory(product_id=products[2].id, warehouse_id=wh_hn.id, quantity_on_hand=200, quantity_reserved=20),
            Inventory(product_id=products[3].id, warehouse_id=wh_hn.id, quantity_on_hand=150, quantity_reserved=0),
            Inventory(product_id=products[4].id, warehouse_id=wh_hcm.id, quantity_on_hand=90, quantity_reserved=15),
        ]
        session.add_all(inventories)

        # 6. Sample Confirmed Orders for Reporting
        order1 = SalesOrder(
            order_number="SO-20260915-001",
            customer_id=customers[0].id,
            status="confirmed",
            total_amount=Decimal("57000000.00"),
            created_by=sales_user.id,
            created_at=datetime(2026, 9, 15, 10, 30, tzinfo=timezone.utc),
            items=[
                SalesOrderItem(
                    product_id=products[0].id,
                    quantity=2,
                    unit_price=Decimal("28500000.00"),
                    line_total=Decimal("57000000.00"),
                )
            ],
        )

        order2 = SalesOrder(
            order_number="SO-20261005-002",
            customer_id=customers[1].id,
            status="confirmed",
            total_amount=Decimal("25800000.00"),
            created_by=sales_user.id,
            created_at=datetime(2026, 10, 5, 14, 0, tzinfo=timezone.utc),
            items=[
                SalesOrderItem(
                    product_id=products[1].id,
                    quantity=2,
                    unit_price=Decimal("12900000.00"),
                    line_total=Decimal("25800000.00"),
                )
            ],
        )
        session.add_all([order1, order2])

        await session.commit()
        print("[+] Demo data seeded successfully!")


if __name__ == "__main__":
    asyncio.run(seed_data())
