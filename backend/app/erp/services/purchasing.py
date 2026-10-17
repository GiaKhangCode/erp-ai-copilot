import uuid
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundException, ValidationException, AppException
from app.erp.models import (
    Supplier,
    PurchaseOrder,
    PurchaseOrderItem,
    Warehouse,
    Product,
    Inventory,
    AuditLog,
    User,
)
from app.erp.schemas import (
    SupplierCreate,
    PurchaseOrderCreate,
    PurchaseOrderResponse,
    PurchaseOrderItemResponse,
)


class PurchasingService:
    @staticmethod
    async def list_suppliers(
        session: AsyncSession,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Supplier]:
        """Lấy danh sách nhà cung cấp."""
        stmt = select(Supplier)
        if status:
            stmt = stmt.where(Supplier.status == status)
        stmt = stmt.order_by(Supplier.name.asc()).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_supplier(
        session: AsyncSession,
        payload: SupplierCreate,
        actor_id: uuid.UUID,
    ) -> Supplier:
        """Tạo mới nhà cung cấp."""
        existing_stmt = select(Supplier).where(Supplier.code == payload.code.strip().upper())
        res = await session.execute(existing_stmt)
        if res.scalar_one_or_none():
            raise ValidationException(f"Nhà cung cấp với mã '{payload.code}' đã tồn tại.")

        supplier = Supplier(
            code=payload.code.strip().upper(),
            name=payload.name.strip(),
            tax_code=payload.tax_code.strip() if payload.tax_code else None,
            contact_email=payload.contact_email.strip() if payload.contact_email else None,
            phone=payload.phone.strip() if payload.phone else None,
            address=payload.address.strip() if payload.address else None,
            status=payload.status or "active",
        )
        session.add(supplier)

        audit = AuditLog(
            id=uuid.uuid4(),
            actor_id=actor_id,
            action="SUPPLIER_CREATE",
            resource_type="supplier",
            resource_id=str(supplier.id),
            result="SUCCESS",
            details={"code": supplier.code, "name": supplier.name},
        )
        session.add(audit)
        await session.commit()
        await session.refresh(supplier)
        return supplier

    @staticmethod
    async def list_purchase_orders(
        session: AsyncSession,
        status: Optional[str] = None,
        supplier_code: Optional[str] = None,
        warehouse_code: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[PurchaseOrderResponse]:
        """Lấy danh sách đơn mua hàng PO kèm thông tin chi tiết."""
        stmt = (
            select(PurchaseOrder)
            .join(PurchaseOrder.supplier)
            .join(PurchaseOrder.warehouse)
            .options(
                selectinload(PurchaseOrder.supplier),
                selectinload(PurchaseOrder.warehouse),
                selectinload(PurchaseOrder.creator),
                selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.product),
            )
        )
        if status:
            stmt = stmt.where(PurchaseOrder.status == status)
        if supplier_code:
            stmt = stmt.where(Supplier.code == supplier_code)
        if warehouse_code:
            stmt = stmt.where(Warehouse.code == warehouse_code)

        stmt = stmt.order_by(PurchaseOrder.created_at.desc()).limit(limit).offset(offset)
        result = await session.execute(stmt)
        pos = result.scalars().all()

        responses: List[PurchaseOrderResponse] = []
        for po in pos:
            items_res = [
                PurchaseOrderItemResponse(
                    id=item.id,
                    product_id=item.product_id,
                    sku=item.product.sku if item.product else "N/A",
                    product_name=item.product.name if item.product else "Sản phẩm",
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    line_total=item.line_total,
                )
                for item in po.items
            ]
            responses.append(
                PurchaseOrderResponse(
                    id=po.id,
                    po_number=po.po_number,
                    supplier_id=po.supplier_id,
                    supplier_code=po.supplier.code if po.supplier else "N/A",
                    supplier_name=po.supplier.name if po.supplier else "N/A",
                    warehouse_id=po.warehouse_id,
                    warehouse_code=po.warehouse.code if po.warehouse else "N/A",
                    warehouse_name=po.warehouse.name if po.warehouse else "N/A",
                    status=po.status,
                    total_amount=po.total_amount,
                    notes=po.notes,
                    created_by=po.created_by,
                    creator_name=po.creator.name if po.creator else None,
                    created_at=po.created_at,
                    items=items_res,
                )
            )
        return responses

    @staticmethod
    async def get_purchase_order(session: AsyncSession, po_id: uuid.UUID) -> PurchaseOrderResponse:
        """Lấy chi tiết đơn mua hàng PO theo ID."""
        stmt = (
            select(PurchaseOrder)
            .options(
                selectinload(PurchaseOrder.supplier),
                selectinload(PurchaseOrder.warehouse),
                selectinload(PurchaseOrder.creator),
                selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.product),
            )
            .where(PurchaseOrder.id == po_id)
        )
        result = await session.execute(stmt)
        po = result.scalar_one_or_none()
        if not po:
            raise NotFoundException(f"Không tìm thấy đơn mua hàng với ID '{po_id}'", code="PO_NOT_FOUND")

        items_res = [
            PurchaseOrderItemResponse(
                id=item.id,
                product_id=item.product_id,
                sku=item.product.sku if item.product else "N/A",
                product_name=item.product.name if item.product else "Sản phẩm",
                quantity=item.quantity,
                unit_price=item.unit_price,
                line_total=item.line_total,
            )
            for item in po.items
        ]
        return PurchaseOrderResponse(
            id=po.id,
            po_number=po.po_number,
            supplier_id=po.supplier_id,
            supplier_code=po.supplier.code if po.supplier else "N/A",
            supplier_name=po.supplier.name if po.supplier else "N/A",
            warehouse_id=po.warehouse_id,
            warehouse_code=po.warehouse.code if po.warehouse else "N/A",
            warehouse_name=po.warehouse.name if po.warehouse else "N/A",
            status=po.status,
            total_amount=po.total_amount,
            notes=po.notes,
            created_by=po.created_by,
            creator_name=po.creator.name if po.creator else None,
            created_at=po.created_at,
            items=items_res,
        )

    @staticmethod
    async def create_purchase_order(
        session: AsyncSession,
        payload: PurchaseOrderCreate,
        actor_id: uuid.UUID,
    ) -> PurchaseOrderResponse:
        """
        Tạo đơn mua hàng PO mới:
        - Kiểm tra nhà cung cấp
        - Kiểm tra kho hàng tiếp nhận
        - Kiểm tra danh mục sản phẩm và tính toán tổng tiền
        - Ghi nhận AuditLog PO_CREATED
        """
        # 1. Supplier
        sup_stmt = select(Supplier).where(Supplier.code == payload.supplier_code)
        res_sup = await session.execute(sup_stmt)
        supplier = res_sup.scalar_one_or_none()
        if not supplier:
            raise NotFoundException(f"Nhà cung cấp với mã '{payload.supplier_code}' không tồn tại.", code="SUPPLIER_NOT_FOUND")
        if supplier.status != "active":
            raise ValidationException(f"Nhà cung cấp '{payload.supplier_code}' đang ngừng giao dịch.")

        # 2. Warehouse
        wh_stmt = select(Warehouse).where(Warehouse.code == payload.warehouse_code)
        res_wh = await session.execute(wh_stmt)
        warehouse = res_wh.scalar_one_or_none()
        if not warehouse:
            raise NotFoundException(f"Kho hàng với mã '{payload.warehouse_code}' không tồn tại.", code="WAREHOUSE_NOT_FOUND")

        # 3. Items
        if not payload.items:
            raise ValidationException("Đơn mua hàng phải có ít nhất một mặt hàng.")

        po_items: List[PurchaseOrderItem] = []
        total_amount = Decimal("0.00")

        for it in payload.items:
            if it.quantity <= 0:
                raise ValidationException(f"Số lượng đặt mua cho SKU '{it.sku}' phải lớn hơn 0.")
            if it.unit_price < 0:
                raise ValidationException(f"Đơn giá cho SKU '{it.sku}' không được âm.")

            prod_stmt = select(Product).where(Product.sku == it.sku)
            res_prod = await session.execute(prod_stmt)
            product = res_prod.scalar_one_or_none()
            if not product:
                raise NotFoundException(f"Sản phẩm với SKU '{it.sku}' không tồn tại.", code="PRODUCT_NOT_FOUND")

            line_total = Decimal(it.quantity) * Decimal(str(it.unit_price))
            total_amount += line_total

            po_item = PurchaseOrderItem(
                id=uuid.uuid4(),
                product_id=product.id,
                quantity=it.quantity,
                unit_price=it.unit_price,
                line_total=line_total,
            )
            po_items.append(po_item)

        # 4. PO Number
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        random_suffix = secrets.token_hex(2).upper()
        po_number = f"PO-{today_str}-{random_suffix}"

        po = PurchaseOrder(
            id=uuid.uuid4(),
            po_number=po_number,
            supplier_id=supplier.id,
            warehouse_id=warehouse.id,
            status="draft",
            total_amount=total_amount,
            notes=payload.notes,
            created_by=actor_id,
            items=po_items,
        )
        session.add(po)

        audit = AuditLog(
            id=uuid.uuid4(),
            actor_id=actor_id,
            action="PO_CREATED",
            resource_type="purchase_order",
            resource_id=str(po.id),
            result="SUCCESS",
            details={
                "po_number": po.po_number,
                "supplier": supplier.name,
                "warehouse": warehouse.name,
                "total_amount": float(total_amount),
            },
        )
        session.add(audit)
        await session.commit()

        return await PurchasingService.get_purchase_order(session, po.id)

    @staticmethod
    async def receive_purchase_order(
        session: AsyncSession,
        po_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> PurchaseOrderResponse:
        """
        Nghiệp vụ Nhập kho Mua hàng (PO Receiving):
        - Chỉ cho phép khi đơn ở trạng thái 'draft' hoặc 'ordered'.
        - Tự động cộng số lượng thực tế tồn kho 'quantity_on_hand' tại warehouse_id tương ứng.
        - Chuyển trạng thái đơn sang 'received'.
        - Ghi nhận AuditLog PO_RECEIVED.
        """
        stmt = (
            select(PurchaseOrder)
            .options(
                selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.product),
                selectinload(PurchaseOrder.warehouse),
            )
            .where(PurchaseOrder.id == po_id)
            .with_for_update()
        )
        res = await session.execute(stmt)
        po = res.scalar_one_or_none()
        if not po:
            raise NotFoundException(f"Không tìm thấy đơn mua hàng với ID '{po_id}'", code="PO_NOT_FOUND")

        if po.status == "received":
            raise AppException(status_code=400, code="PO_ALREADY_RECEIVED", message="Đơn mua hàng này đã được nhập kho trước đó.")
        if po.status == "cancelled":
            raise AppException(status_code=400, code="PO_CANCELLED", message="Đơn mua hàng này đã bị hủy, không thể nhập kho.")

        # Tăng tồn kho cho từng sản phẩm
        received_items_summary = []
        for item in po.items:
            inv_stmt = (
                select(Inventory)
                .where(
                    Inventory.product_id == item.product_id,
                    Inventory.warehouse_id == po.warehouse_id,
                )
                .with_for_update()
            )
            res_inv = await session.execute(inv_stmt)
            inv = res_inv.scalar_one_or_none()

            if not inv:
                inv = Inventory(
                    product_id=item.product_id,
                    warehouse_id=po.warehouse_id,
                    quantity_on_hand=item.quantity,
                    quantity_reserved=0,
                )
                session.add(inv)
            else:
                inv.quantity_on_hand += item.quantity

            received_items_summary.append({
                "sku": item.product.sku if item.product else str(item.product_id),
                "quantity": item.quantity,
            })

        po.status = "received"

        audit = AuditLog(
            id=uuid.uuid4(),
            actor_id=actor_id,
            action="PO_RECEIVED",
            resource_type="purchase_order",
            resource_id=str(po.id),
            result="RECEIVED",
            details={
                "po_number": po.po_number,
                "warehouse": po.warehouse.name if po.warehouse else str(po.warehouse_id),
                "items": received_items_summary,
            },
        )
        session.add(audit)
        await session.commit()

        return await PurchasingService.get_purchase_order(session, po.id)

    @staticmethod
    async def cancel_purchase_order(
        session: AsyncSession,
        po_id: uuid.UUID,
        actor_id: uuid.UUID,
        reason: Optional[str] = None,
    ) -> PurchaseOrderResponse:
        """Hủy đơn mua hàng chưa nhập kho."""
        stmt = select(PurchaseOrder).where(PurchaseOrder.id == po_id).with_for_update()
        res = await session.execute(stmt)
        po = res.scalar_one_or_none()
        if not po:
            raise NotFoundException(f"Không tìm thấy đơn mua hàng với ID '{po_id}'", code="PO_NOT_FOUND")

        if po.status == "received":
            raise AppException(status_code=400, code="PO_ALREADY_RECEIVED", message="Đơn mua hàng đã nhập kho, không thể hủy.")
        if po.status == "cancelled":
            raise AppException(status_code=400, code="PO_ALREADY_CANCELLED", message="Đơn mua hàng đã được hủy trước đó.")

        po.status = "cancelled"

        audit = AuditLog(
            id=uuid.uuid4(),
            actor_id=actor_id,
            action="PO_CANCELLED",
            resource_type="purchase_order",
            resource_id=str(po.id),
            result="CANCELLED",
            details={"po_number": po.po_number, "reason": reason or "Người dùng yêu cầu hủy"},
        )
        session.add(audit)
        await session.commit()

        return await PurchasingService.get_purchase_order(session, po.id)
