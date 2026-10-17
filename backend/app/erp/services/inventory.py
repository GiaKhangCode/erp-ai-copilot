import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundException, ValidationException
from app.erp.models import Product, Warehouse, Inventory, StockAdjustment, AuditLog
from app.erp.schemas import InventoryResponse, StockAdjustmentResponse


class InventoryService:
    @staticmethod
    async def get_inventory(
        session: AsyncSession,
        sku: Optional[str] = None,
        warehouse_code: Optional[str] = None,
    ) -> List[InventoryResponse]:
        """
        Tra cứu tồn kho thời gian thực.
        Tính toán số lượng khả dụng: available = on_hand - reserved.
        """
        stmt = (
            select(Inventory)
            .join(Inventory.product)
            .join(Inventory.warehouse)
            .options(selectinload(Inventory.product), selectinload(Inventory.warehouse))
        )
        if sku:
            stmt = stmt.where(Product.sku == sku)
        if warehouse_code:
            stmt = stmt.where(Warehouse.code == warehouse_code)

        stmt = stmt.order_by(Product.sku, Warehouse.code)
        result = await session.execute(stmt)
        items = result.scalars().all()

        return [
            InventoryResponse(
                product_sku=item.product.sku,
                product_name=item.product.name,
                warehouse_code=item.warehouse.code,
                warehouse_name=item.warehouse.name,
                quantity_on_hand=item.quantity_on_hand,
                quantity_reserved=item.quantity_reserved,
                quantity_available=item.available_quantity,
            )
            for item in items
        ]

    @staticmethod
    async def adjust_inventory(
        session: AsyncSession,
        sku: str,
        warehouse_code: str,
        delta_quantity: int,
        reason: str,
        user_id: uuid.UUID,
    ) -> StockAdjustment:
        """
        Phiếu kiểm kê & điều chỉnh tồn kho (Stock Adjustment):
        - delta_quantity: số lượng tăng (+) hoặc giảm (-).
        - Kiểm tra tính hợp lệ: Tồn kho sau điều chỉnh không được nhỏ hơn số lượng đang giữ đơn (reserved).
        - Ghi nhật ký kiểm kê StockAdjustment và AuditLog.
        """
        if delta_quantity == 0:
            raise ValidationException("Số lượng điều chỉnh (delta) phải khác 0.")

        clean_sku = sku.strip().upper()
        clean_wh = warehouse_code.strip().upper()

        # Tìm sản phẩm
        prod_stmt = select(Product).where(Product.sku == clean_sku)
        prod_res = await session.execute(prod_stmt)
        product = prod_res.scalar_one_or_none()
        if not product:
            raise NotFoundException(f"Không tìm thấy sản phẩm có mã SKU '{clean_sku}'")

        # Tìm kho
        wh_stmt = select(Warehouse).where(Warehouse.code == clean_wh)
        wh_res = await session.execute(wh_stmt)
        warehouse = wh_res.scalar_one_or_none()
        if not warehouse:
            raise NotFoundException(f"Không tìm thấy kho hàng có mã '{clean_wh}'")

        # Tìm bản ghi tồn kho
        inv_stmt = select(Inventory).where(
            Inventory.product_id == product.id,
            Inventory.warehouse_id == warehouse.id,
        )
        inv_res = await session.execute(inv_stmt)
        inventory = inv_res.scalar_one_or_none()

        if not inventory:
            if delta_quantity < 0:
                raise ValidationException(f"Sản phẩm '{clean_sku}' chưa có tồn kho tại kho '{clean_wh}', không thể giảm.")
            inventory = Inventory(
                product_id=product.id,
                warehouse_id=warehouse.id,
                quantity_on_hand=0,
                quantity_reserved=0,
            )
            session.add(inventory)

        qty_before = inventory.quantity_on_hand
        qty_after = qty_before + delta_quantity

        if qty_after < 0:
            raise ValidationException(
                f"Tồn kho thực tế không thể âm ({qty_after}). Tồn kho hiện tại: {qty_before}."
            )

        if qty_after < inventory.quantity_reserved:
            raise ValidationException(
                f"Không thể giảm tồn kho xuống dưới số lượng đang giữ đơn hàng. "
                f"Tồn kho sau điều chỉnh: {qty_after}, số lượng đang giữ đơn: {inventory.quantity_reserved}."
            )

        inventory.quantity_on_hand = qty_after

        # Ghi nhận phiếu điều chỉnh
        adjustment = StockAdjustment(
            id=uuid.uuid4(),
            product_id=product.id,
            warehouse_id=warehouse.id,
            sku=clean_sku,
            warehouse_code=clean_wh,
            delta_quantity=delta_quantity,
            quantity_before=qty_before,
            quantity_after=qty_after,
            reason=reason.strip(),
            adjusted_by=user_id,
        )
        session.add(adjustment)

        # Ghi nhật ký kiểm toán
        audit_log = AuditLog(
            id=uuid.uuid4(),
            actor_id=user_id,
            action="STOCK_ADJUSTMENT",
            resource_type="inventory",
            resource_id=f"{clean_wh}:{clean_sku}",
            result=f"BEFORE={qty_before}, AFTER={qty_after}, DELTA={delta_quantity}",
        )
        session.add(audit_log)

        await session.commit()
        await session.refresh(adjustment)
        return adjustment

    @staticmethod
    async def list_adjustments(
        session: AsyncSession,
        sku: Optional[str] = None,
        warehouse_code: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[StockAdjustment]:
        """Lấy lịch sử các phiếu kiểm kê điều chỉnh tồn kho."""
        stmt = select(StockAdjustment)
        if sku:
            stmt = stmt.where(StockAdjustment.sku == sku.strip().upper())
        if warehouse_code:
            stmt = stmt.where(StockAdjustment.warehouse_code == warehouse_code.strip().upper())

        stmt = stmt.order_by(StockAdjustment.created_at.desc()).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def transfer_inventory(
        session: AsyncSession,
        source_warehouse_code: str,
        target_warehouse_code: str,
        sku: str,
        quantity: int,
        reason: str,
        user_id: uuid.UUID,
        actor_email: str = "system",
        actor_role: str = "unknown",
        ip_address: Optional[str] = None,
    ) -> dict:
        """
        Thực hiện điều chuyển tồn kho giữa 2 kho nội bộ:
        - Kiểm tra tính hợp lệ kho xuất & kho nhập khác nhau.
        - Kiểm tra tồn kho khả dụng tại kho xuất: available = on_hand - reserved >= quantity.
        - Trừ tồn tại kho xuất, cộng tồn tại kho nhập.
        - Ghi nhật ký StockTransfer và AuditLog.
        """
        src_code = source_warehouse_code.strip().upper()
        tgt_code = target_warehouse_code.strip().upper()
        clean_sku = sku.strip().upper()

        if src_code == tgt_code:
            raise ValidationException("Kho xuất và kho nhập không được trùng nhau.")
        if quantity <= 0:
            raise ValidationException("Số lượng điều chuyển phải lớn hơn 0.")

        # 1. Tìm sản phẩm
        prod_stmt = select(Product).where(Product.sku == clean_sku)
        prod_res = await session.execute(prod_stmt)
        product = prod_res.scalar_one_or_none()
        if not product:
            raise NotFoundException(f"Không tìm thấy sản phẩm có SKU '{clean_sku}'")

        # 2. Tìm 2 kho hàng
        wh_stmt = select(Warehouse).where(Warehouse.code.in_([src_code, tgt_code]))
        wh_res = await session.execute(wh_stmt)
        warehouses = {w.code: w for w in wh_res.scalars().all()}

        if src_code not in warehouses:
            raise NotFoundException(f"Không tìm thấy kho xuất hàng '{src_code}'")
        if tgt_code not in warehouses:
            raise NotFoundException(f"Không tìm thấy kho nhập hàng '{tgt_code}'")

        src_wh = warehouses[src_code]
        tgt_wh = warehouses[tgt_code]

        # 3. Kiểm tra tồn kho nguồn
        src_inv_stmt = select(Inventory).where(
            Inventory.product_id == product.id,
            Inventory.warehouse_id == src_wh.id
        ).with_for_update()
        src_inv_res = await session.execute(src_inv_stmt)
        src_inv = src_inv_res.scalar_one_or_none()

        if not src_inv or src_inv.available_quantity < quantity:
            avail = src_inv.available_quantity if src_inv else 0
            raise ValidationException(
                f"Tồn kho khả dụng tại kho {src_code} không đủ để chuyển (khả dụng: {avail}, yêu cầu: {quantity})."
            )

        # 4. Kiểm tra tồn kho đích (nếu chưa có bản ghi thì tạo mới)
        tgt_inv_stmt = select(Inventory).where(
            Inventory.product_id == product.id,
            Inventory.warehouse_id == tgt_wh.id
        ).with_for_update()
        tgt_inv_res = await session.execute(tgt_inv_stmt)
        tgt_inv = tgt_inv_res.scalar_one_or_none()

        if not tgt_inv:
            tgt_inv = Inventory(
                product_id=product.id,
                warehouse_id=tgt_wh.id,
                quantity_on_hand=0,
                quantity_reserved=0,
            )
            session.add(tgt_inv)

        # 5. Thực hiện điều chuyển
        src_inv.quantity_on_hand -= quantity
        tgt_inv.quantity_on_hand += quantity

        # 6. Ghi bản ghi StockTransfer
        from datetime import datetime, timezone
        from app.erp.models import StockTransfer
        from app.erp.services.audit import AuditService

        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        rand_suffix = uuid.uuid4().hex[:4].upper()
        transfer_number = f"TRF-{today_str}-{rand_suffix}"

        transfer = StockTransfer(
            id=uuid.uuid4(),
            transfer_number=transfer_number,
            source_warehouse_id=src_wh.id,
            target_warehouse_id=tgt_wh.id,
            product_id=product.id,
            quantity=quantity,
            reason=reason.strip(),
            transferred_by=user_id,
        )
        session.add(transfer)

        # 7. Ghi Audit Log
        await AuditService.log_activity(
            session=session,
            action="STOCK_TRANSFER",
            actor=user_id,
            actor_email=actor_email,
            actor_role=actor_role,
            resource_type="StockTransfer",
            resource_id=str(transfer.id),
            ip_address=ip_address,
            details={
                "transfer_number": transfer_number,
                "sku": clean_sku,
                "product_name": product.name,
                "source_warehouse": src_code,
                "target_warehouse": tgt_code,
                "quantity": quantity,
                "reason": reason.strip(),
                "src_remaining_on_hand": src_inv.quantity_on_hand,
                "tgt_new_on_hand": tgt_inv.quantity_on_hand,
            },
        )

        await session.commit()
        await session.refresh(transfer)

        return {
            "id": transfer.id,
            "transfer_number": transfer.transfer_number,
            "sku": clean_sku,
            "product_name": product.name,
            "source_warehouse_code": src_code,
            "source_warehouse_name": src_wh.name,
            "target_warehouse_code": tgt_code,
            "target_warehouse_name": tgt_wh.name,
            "quantity": quantity,
            "reason": reason.strip(),
            "transferred_by": user_id,
            "created_at": transfer.created_at,
        }

    @staticmethod
    async def list_transfers(
        session: AsyncSession,
        sku: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[dict]:
        """Lấy danh sách các phiếu điều chuyển tồn kho nội bộ."""
        from app.erp.models import StockTransfer, User
        from sqlalchemy.orm import aliased

        SourceWh = aliased(Warehouse)
        TargetWh = aliased(Warehouse)

        stmt = (
            select(
                StockTransfer,
                Product.sku.label("sku"),
                Product.name.label("product_name"),
                SourceWh.code.label("src_code"),
                SourceWh.name.label("src_name"),
                TargetWh.code.label("tgt_code"),
                TargetWh.name.label("tgt_name"),
                User.full_name.label("transferrer_name"),
            )
            .join(Product, StockTransfer.product_id == Product.id)
            .join(SourceWh, StockTransfer.source_warehouse_id == SourceWh.id)
            .join(TargetWh, StockTransfer.target_warehouse_id == TargetWh.id)
            .outerjoin(User, StockTransfer.transferred_by == User.id)
            .order_by(StockTransfer.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        if sku:
            stmt = stmt.where(Product.sku == sku.strip().upper())

        res = await session.execute(stmt)
        rows = res.all()

        results = []
        for transfer, p_sku, p_name, s_code, s_name, t_code, t_name, u_name in rows:
            results.append({
                "id": transfer.id,
                "transfer_number": transfer.transfer_number,
                "sku": p_sku,
                "product_name": p_name,
                "source_warehouse_code": s_code,
                "source_warehouse_name": s_name,
                "target_warehouse_code": t_code,
                "target_warehouse_name": t_name,
                "quantity": transfer.quantity,
                "reason": transfer.reason,
                "transferred_by": transfer.transferred_by,
                "transferrer_name": u_name,
                "created_at": transfer.created_at,
            })
        return results
