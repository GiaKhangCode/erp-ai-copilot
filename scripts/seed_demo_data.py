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
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_documents_owner_id "
                "ON ai.documents (owner_id);"
            )
        )

        await conn.execute(
            text(
                "TRUNCATE erp.sales_order_items, erp.sales_orders, erp.inventory, "
                "erp.products, erp.customers, erp.warehouses, erp.users, erp.idempotency_keys "
                "RESTART IDENTITY CASCADE;"
            )
        )

    async with async_session_factory() as session:
        # 1. Users
        admin_user = User(
            email="admin@erpcopilot.vn",
            password_hash=get_password_hash("admin123"),
            full_name="Quản Trị Viên Hệ Thống",
            role="admin",
        )
        sales_user = User(
            email="sales@erpcopilot.vn",
            password_hash=get_password_hash("sales123"),
            full_name="Nguyễn Văn Bán Hàng",
            role="sales_rep",
        )
        session.add_all([admin_user, sales_user])
        await session.flush()

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
