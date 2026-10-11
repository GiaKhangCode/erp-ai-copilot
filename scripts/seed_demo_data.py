"""
Seed Demo Data Script for ERP AI Copilot
Creates deterministic sample data:
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

# Ensure backend/ directory is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import Base
from app.db.session import engine, async_session_factory
from app.erp.models import Customer, Product, Warehouse, Inventory, SalesOrder, SalesOrderItem
import app.rag.models  # noqa: F401


async def seed_data():
    print("🌱 Starting ERP demo data seeding...")
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS erp;"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS ai;"))
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        # 1. Warehouses
        wh_hn = Warehouse(code="WH-HN", name="Kho Tổng Hà Nội")
        wh_hcm = Warehouse(code="WH-HCM", name="Kho Tổng Hồ Chí Minh")
        session.add_all([wh_hn, wh_hcm])
        await session.flush()

        # 2. Customers
        customers = [
            Customer(code="CUS-0001", name="Công ty TNHH Công Nghệ Á Châu", email="contact@asiatech.vn", status="active"),
            Customer(code="CUS-0002", name="Tập đoàn Bán lẻ Toàn Cầu", email="purchasing@globalretail.com", status="active"),
            Customer(code="CUS-0003", name="Công ty Cổ phần May Mặc Việt", email="info@vietgarment.vn", status="active"),
            Customer(code="CUS-0004", name="Công ty TNHH Phân Phối Miền Tây", email="sales@mientaydist.vn", status="active"),
            Customer(code="CUS-0005", name="Chuỗi Siêu thị Xanh", email="order@greensuper.vn", status="active"),
        ]
        session.add_all(customers)
        await session.flush()

        # 3. Products
        products = [
            Product(sku="SKU-001", name="Laptop Pro 14-inch M3", unit_price=Decimal("28500000.00"), is_active=True),
            Product(sku="SKU-002", name="Màn hình Dell UltraSharp 27-inch 4K", unit_price=Decimal("12900000.00"), is_active=True),
            Product(sku="SKU-003", name="Bàn phím cơ không dây Silent", unit_price=Decimal("2450000.00"), is_active=True),
            Product(sku="SKU-004", name="Chuột Ergonomic Bluetooth", unit_price=Decimal("1150000.00"), is_active=True),
            Product(sku="SKU-005", name="Tai nghe chống ồn chủ động ANC", unit_price=Decimal("4600000.00"), is_active=True),
        ]
        session.add_all(products)
        await session.flush()

        # 4. Inventory
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

        await session.commit()
        print("✅ Demo data seeded successfully!")


if __name__ == "__main__":
    asyncio.run(seed_data())
