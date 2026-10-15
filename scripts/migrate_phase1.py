"""
Migration script for Phase 1:
- Update check_sales_order_status to include 'delivered'
- Create erp.stock_adjustments table if not exists
"""
import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.db.session import async_session_factory

async def main():
    async with async_session_factory() as session:
        # 1. Update check constraint on sales_orders
        print("1. Updating check_sales_order_status...")
        await session.execute(text("ALTER TABLE erp.sales_orders DROP CONSTRAINT IF EXISTS check_sales_order_status;"))
        await session.execute(text("""
            ALTER TABLE erp.sales_orders 
            ADD CONSTRAINT check_sales_order_status 
            CHECK (status IN ('draft', 'pending_approval', 'confirmed', 'cancelled', 'delivered'));
        """))

        # 2. Create stock_adjustments table
        print("2. Creating erp.stock_adjustments table...")
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
        await session.commit()
        print("Migration for Phase 1 completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
