"""
Migration script for Phase 7:
- Add customer_po_number to erp.sales_orders (anti-duplicate check)
- Add catalog_price to erp.sales_order_items (track original catalog price vs negotiated PO price)
- Add allocated_quantity, backorder_quantity to erp.sales_order_items (support partial stock & backorder)
- Backfill allocated_quantity = quantity and catalog_price = unit_price for existing items
"""
import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text  # noqa: E402
from app.db.session import async_session_factory  # noqa: E402


async def migrate():
    print("[*] Starting Phase 7 Migration (Order Ingestion Revamp & Backorder)...")
    async with async_session_factory() as session:
        # 1. Bảng erp.sales_orders: thêm customer_po_number
        print("1. Adding customer_po_number to erp.sales_orders...")
        await session.execute(text("""
            ALTER TABLE erp.sales_orders
            ADD COLUMN IF NOT EXISTS customer_po_number VARCHAR(100);
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_sales_orders_customer_po
            ON erp.sales_orders(customer_po_number);
        """))

        # 2. Bảng erp.sales_order_items: thêm catalog_price, allocated_quantity, backorder_quantity
        print("2. Adding catalog_price, allocated_quantity, backorder_quantity to erp.sales_order_items...")
        await session.execute(text("""
            ALTER TABLE erp.sales_order_items
            ADD COLUMN IF NOT EXISTS catalog_price NUMERIC(14, 2);
        """))
        await session.execute(text("""
            ALTER TABLE erp.sales_order_items
            ADD COLUMN IF NOT EXISTS allocated_quantity INTEGER NOT NULL DEFAULT 0;
        """))
        await session.execute(text("""
            ALTER TABLE erp.sales_order_items
            ADD COLUMN IF NOT EXISTS backorder_quantity INTEGER NOT NULL DEFAULT 0;
        """))

        # 3. Backfill dữ liệu cũ
        print("3. Backfilling allocated_quantity and catalog_price for existing orders...")
        await session.execute(text("""
            UPDATE erp.sales_order_items
            SET allocated_quantity = quantity,
                catalog_price = unit_price
            WHERE allocated_quantity = 0 AND quantity > 0;
        """))

        await session.commit()
        print("[+] Phase 7 Migration completed successfully!")


if __name__ == "__main__":
    asyncio.run(migrate())
