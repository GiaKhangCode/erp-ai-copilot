import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundException, ValidationException
from app.document_ai.schemas import ExtractedPurchaseOrder, OrderIngestionResult, ResolvedOrderItem
from app.document_ai.resolver import EntityResolver, EntityResolutionResult
from app.erp.models import ApprovalRequest, AuditLog, Customer, Inventory, Product, SalesOrder, SalesOrderItem
from app.erp.schemas import OrderDraftCreate, OrderItemDraft
from app.erp.services.order import SalesOrderService

logger = logging.getLogger(__name__)


class OrderIngestionService:
    """
    Domain Service điều phối toàn bộ quy trình Ingestion từ Email/Tài liệu sang ERP:
    1. Tiếp nhận kết quả trích xuất ExtractedPurchaseOrder
    2. Đối chiếu cơ sở dữ liệu qua EntityResolver
    3. Tạo đơn hàng nháp (status='draft') trong erp.sales_orders
    4. Tạo bản ghi phê duyệt (status='pending') trong erp.approval_requests kèm payload_hash
    5. Ghi Audit Log đồng bộ
    """

    @classmethod
    async def ingest_extracted_order(
        cls,
        session: AsyncSession,
        extracted_order: ExtractedPurchaseOrder,
        actor_id: uuid.UUID,
        source_type: str = "email_eml",
        source_identifier: str = "order.eml",
    ) -> OrderIngestionResult:
        # 1. Đối chiếu thực thể với DB
        resolution: EntityResolutionResult = await EntityResolver.resolve_order(session, extracted_order)

        # Nếu không có khách hàng hoặc không có bất kỳ mặt hàng nào khớp
        if not resolution.customer or not resolution.resolved_items:
            return OrderIngestionResult(
                source_type=source_type,
                source_identifier=source_identifier,
                status="requires_human_correction",
                extracted_data=extracted_order,
                resolved_customer_id=resolution.customer.id if resolution.customer else None,
                resolved_customer_code=resolution.customer.code if resolution.customer else None,
                resolved_customer_name=resolution.customer.name if resolution.customer else None,
                resolved_items=resolution.resolved_items,
                total_amount=resolution.total_amount,
                warnings=resolution.warnings,
                draft_order_id=None,
                approval_request_id=None,
            )

        # 2. Tạo đơn hàng nháp qua SalesOrderService
        draft_payload = OrderDraftCreate(
            customer_code=resolution.customer.code,
            items=[
                OrderItemDraft(sku=item.sku, quantity=item.quantity)
                for item in resolution.resolved_items
            ],
            requested_delivery_date=str(extracted_order.requested_delivery_date) if extracted_order.requested_delivery_date else None,
        )

        draft_order = await SalesOrderService.create_order_draft(
            session=session,
            payload=draft_payload,
            actor_id=actor_id,
        )

        # 3. Tạo bản ghi phê duyệt trong erp.approval_requests
        approval_payload = {
            "order_id": str(draft_order.id),
            "order_number": draft_order.order_number,
            "customer_code": resolution.customer.code,
            "customer_name": resolution.customer.name,
            "total_amount": float(draft_order.total_amount),
            "source_type": source_type,
            "source_identifier": source_identifier,
            "warnings_count": len(resolution.warnings),
            "items": [
                {
                    "sku": item.sku,
                    "product_name": item.product_name,
                    "quantity": item.quantity,
                    "unit_price": float(item.db_unit_price),
                    "line_total": float(item.line_total),
                    "stock_sufficient": item.stock_sufficient,
                    "price_discrepancy": item.price_discrepancy,
                }
                for item in resolution.resolved_items
            ],
        }

        payload_bytes = json.dumps(approval_payload, sort_keys=True).encode("utf-8")
        payload_hash = hashlib.sha256(payload_bytes).hexdigest()

        approval_request = ApprovalRequest(
            id=uuid.uuid4(),
            action_type="create_sales_order_from_document",
            target_id=draft_order.id,
            payload=approval_payload,
            payload_hash=payload_hash,
            status="pending",
            requested_by=actor_id,
        )
        session.add(approval_request)

        # 4. Ghi Audit Log
        audit_log = AuditLog(
            id=uuid.uuid4(),
            actor_id=actor_id,
            action="INGEST_ORDER_DRAFT",
            resource_type="sales_order",
            resource_id=str(draft_order.id),
            result="SUCCESS",
        )
        session.add(audit_log)
        await session.commit()

        status_result = "success_draft_created" if resolution.is_fully_resolved else "requires_human_correction"

        return OrderIngestionResult(
            source_type=source_type,
            source_identifier=source_identifier,
            status=status_result,
            extracted_data=extracted_order,
            resolved_customer_id=resolution.customer.id,
            resolved_customer_code=resolution.customer.code,
            resolved_customer_name=resolution.customer.name,
            resolved_items=resolution.resolved_items,
            total_amount=draft_order.total_amount,
            warnings=resolution.warnings,
            draft_order_id=draft_order.id,
            approval_request_id=approval_request.id,
        )


class ApprovalService:
    """
    Domain Service quản lý quy trình phê duyệt Human-In-The-Loop:
    - Lấy danh sách yêu cầu phê duyệt
    - Phê duyệt (Approve): Re-validate dữ liệu, chuyển đơn hàng sang 'confirmed', giữ hàng trong kho
    - Từ chối (Reject): Chuyển đơn sang 'cancelled' hoặc giữ 'draft' kèm lý do từ chối
    """

    @classmethod
    async def list_approvals(
        cls,
        session: AsyncSession,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        requested_by: Optional[uuid.UUID] = None,
    ) -> List[ApprovalRequest]:
        stmt = select(ApprovalRequest)
        if status:
            stmt = stmt.where(ApprovalRequest.status == status)
        if requested_by:
            stmt = stmt.where(ApprovalRequest.requested_by == requested_by)
        stmt = stmt.order_by(ApprovalRequest.created_at.desc()).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def get_approval_by_id(
        cls,
        session: AsyncSession,
        approval_id: uuid.UUID,
    ) -> ApprovalRequest:
        stmt = select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
        result = await session.execute(stmt)
        req = result.scalar_one_or_none()
        if not req:
            raise NotFoundException(
                f"Không tìm thấy yêu cầu phê duyệt với ID '{approval_id}'",
                code="APPROVAL_NOT_FOUND",
            )
        return req

    @classmethod
    async def approve_request(
        cls,
        session: AsyncSession,
        approval_id: uuid.UUID,
        approver_id: uuid.UUID,
    ) -> Dict[str, Any]:
        req = await cls.get_approval_by_id(session, approval_id)
        if req.status != "pending":
            raise ValidationException(
                f"Yêu cầu phê duyệt này đã ở trạng thái '{req.status}', không thể duyệt lại."
            )

        # Kiểm tra Nguyên tắc 4 mắt (Four-Eyes Principle / Segregation of Duties)
        if req.requested_by == approver_id:
            raise ValidationException(
                "Vi phạm nguyên tắc phân tách trách nhiệm (Four-Eyes Principle): "
                "Người lập yêu cầu không được phép tự phê duyệt đơn hàng của chính mình. "
                "Yêu cầu phải được một cấp quản lý khác xem xét và phê duyệt."
            )

        # Lấy đơn hàng liên quan
        stmt = (
            select(SalesOrder)
            .options(selectinload(SalesOrder.items))
            .where(SalesOrder.id == req.target_id)
        )
        res = await session.execute(stmt)
        order = res.scalar_one_or_none()
        if not order:
            raise NotFoundException(f"Không tìm thấy đơn hàng ID '{req.target_id}'")

        # Cập nhật trạng thái duyệt
        req.status = "approved"
        req.approved_by = approver_id
        order.status = "confirmed"

        # Tăng số lượng hàng giữ chỗ (reserved quantity) trong kho đầu tiên có sẵn
        for item in order.items:
            inv_stmt = select(Inventory).where(Inventory.product_id == item.product_id).limit(1)
            inv_res = await session.execute(inv_stmt)
            inv = inv_res.scalar_one_or_none()
            if inv:
                if inv.quantity_reserved + item.quantity > inv.quantity_on_hand:
                    raise ValidationException(
                        f"Không đủ tồn kho khả dụng để phê duyệt đơn hàng. "
                        f"Tồn kho thực tế: {inv.quantity_on_hand}, đã giữ chỗ: {inv.quantity_reserved}, cần giữ thêm: {item.quantity}."
                    )
                inv.quantity_reserved += item.quantity

        # Ghi Audit Log
        audit_log = AuditLog(
            id=uuid.uuid4(),
            actor_id=approver_id,
            action="APPROVE_ORDER",
            resource_type="sales_order",
            resource_id=str(order.id),
            result="APPROVED",
        )
        session.add(audit_log)
        await session.commit()

        return {
            "message": "Đã phê duyệt đơn hàng thành công.",
            "approval_id": str(req.id),
            "order_id": str(order.id),
            "order_number": order.order_number,
            "status": order.status,
        }

    @classmethod
    async def reject_request(
        cls,
        session: AsyncSession,
        approval_id: uuid.UUID,
        approver_id: uuid.UUID,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        req = await cls.get_approval_by_id(session, approval_id)
        if req.status != "pending":
            raise ValidationException(
                f"Yêu cầu phê duyệt này đã ở trạng thái '{req.status}', không thể từ chối."
            )

        stmt = select(SalesOrder).where(SalesOrder.id == req.target_id)
        res = await session.execute(stmt)
        order = res.scalar_one_or_none()
        if order:
            order.status = "cancelled"

        req.status = "rejected"
        req.approved_by = approver_id
        if reason:
            req.payload = {**req.payload, "rejection_reason": reason}

        # Ghi Audit Log
        audit_log = AuditLog(
            id=uuid.uuid4(),
            actor_id=approver_id,
            action="REJECT_ORDER",
            resource_type="sales_order",
            resource_id=str(req.target_id),
            result="REJECTED",
        )
        session.add(audit_log)
        await session.commit()

        return {
            "message": "Đã từ chối đơn hàng.",
            "approval_id": str(req.id),
            "order_id": str(req.target_id),
            "status": "rejected",
            "reason": reason,
        }
