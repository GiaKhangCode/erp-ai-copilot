"""
Migration script for Phase 2:
- Add credit_limit, current_debt, phone, address to erp.customers
- Initialize demo financial limits for customers
"""
import asyncio
import os
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.db.session import async_session_factory

async def main():
    async with async_session_factory() as session:
        print("1. Adding credit columns to erp.customers...")
        await session.execute(text("""
            ALTER TABLE erp.customers 
            ADD COLUMN IF NOT EXISTS credit_limit NUMERIC(14, 2) NOT NULL DEFAULT 50000000,
            ADD COLUMN IF NOT EXISTS current_debt NUMERIC(14, 2) NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS phone VARCHAR(30),
            ADD COLUMN IF NOT EXISTS address TEXT;
        """))
        
        # Populate demo values
        print("2. Populating sample credit limits and debt...")
        await session.execute(text("""
            UPDATE erp.customers 
            SET credit_limit = 100000000, current_debt = 25000000, phone = '0901234567', address = 'Tòa nhà FPT, Phố Duy Tân, Cầu Giấy, Hà Nội'
            WHERE code = 'CUS-001' OR code = 'CUS-0001';
        """))
        await session.execute(text("""
            UPDATE erp.customers 
            SET credit_limit = 50000000, current_debt = 42000000, phone = '0987654321', address = 'Số 10 Mai Chí Thọ, TP. Thủ Đức, TP. Hồ Chí Minh'
            WHERE code = 'CUS-002' OR code = 'CUS-0002';
        """))
        await session.commit()
        print("Migration for Phase 2 completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
