import io
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_current_user,
    require_role,
    require_permission,
    get_current_user_permissions,
)
from app.db.session import get_db
from app.document_ai.email_parser import parse_email_bytes, parse_raw_order_text
from app.document_ai.extractor import get_order_extractor
from app.document_ai.ingestion_service import ApprovalService, OrderIngestionService
from app.document_ai.schemas import OrderIngestionResult
from app.erp.models import ApprovalRequest, User
from app.erp.services.order import SalesOrderService
from app.erp.services.quotation import QuotationService
from app.erp.services.customer import CustomerService
from app.erp.schemas import OrderResponse, CustomerCreditCheckResponse
from app.rag.parser import parse_document

router = APIRouter(tags=["Document AI & Approval Inbox"])


class TextOrderIngestRequest(BaseModel):
    text: str = Field(..., min_length=5, description="Nội dung email hoặc tin nhắn đặt hàng")
    source_identifier: Optional[str] = "manual_text_input"


class ApprovalActionResponse(BaseModel):
    message: str
    approval_id: str
    order_id: str
    status: str
    order_number: Optional[str] = None
    reason: Optional[str] = None


class RejectRequest(BaseModel):
    reason: Optional[str] = Field(None, description="Lý do từ chối đơn hàng")


class ApprovalItemResponse(BaseModel):
    id: uuid.UUID
    action_type: str
    target_id: uuid.UUID
    payload: Dict[str, Any]
    status: str
    requested_by: uuid.UUID
    approved_by: Optional[uuid.UUID] = None
    created_at: Any


# =========================================================================
# Order Ingestion Endpoints (Email & Documents)
# =========================================================================

@router.post(
    "/orders/ingest-text",
    response_model=OrderIngestionResult,
    status_code=status.HTTP_200_OK,
    summary="Trích xuất đơn hàng từ văn bản/email thô và tạo đơn nháp",
)
async def ingest_order_from_text(
    payload: TextOrderIngestRequest,
    current_user: User = Depends(require_permission("orders:create")),
    db: AsyncSession = Depends(get_db),
):
    """
    Tiếp nhận văn bản email dán trực tiếp:
    1. Chuẩn hóa qua email_parser
    2. Bóc tách thực thể qua Gemini OrderExtractor
    3. Đối chiếu ERP và tạo đơn hàng nháp kèm bản ghi phê duyệt
    """
    parsed_email = parse_raw_order_text(payload.text, payload.source_identifier or "raw_text")
    extractor = get_order_extractor()
    extracted = await extractor.extract_order(parsed_email)

    result = await OrderIngestionService.ingest_extracted_order(
        session=db,
        extracted_order=extracted,
        actor_id=current_user.id,
        source_type="email_text",
        source_identifier=payload.source_identifier or "raw_text",
    )
    return result


@router.post(
    "/orders/ingest-email",
    response_model=OrderIngestionResult,
    status_code=status.HTTP_200_OK,
    summary="Upload file email (.eml) để tự động trích xuất và tạo đơn nháp",
)
async def ingest_order_from_eml(
    file: UploadFile = File(..., description="Tệp email định dạng .eml"),
    current_user: User = Depends(require_permission("orders:create")),
    db: AsyncSession = Depends(get_db),
):
    """
    Tiếp nhận file .eml (RFC 822):
    1. Parse header, nội dung text/HTML, và các file đính kèm (PDF, DOCX, TXT)
    2. Bóc tách thực thể qua Gemini OrderExtractor
    3. Đối chiếu DB và tạo draft order + approval request
    """
    content_bytes = await file.read()
    if not content_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tệp email không được để trống.",
        )

    parsed_email = parse_email_bytes(content_bytes, file.filename or "email.eml")
    extractor = get_order_extractor()
    extracted = await extractor.extract_order(parsed_email)

    result = await OrderIngestionService.ingest_extracted_order(
        session=db,
        extracted_order=extracted,
        actor_id=current_user.id,
        source_type="email_eml",
        source_identifier=file.filename or "email.eml",
    )
    return result


@router.post(
    "/orders/ingest-document",
    response_model=OrderIngestionResult,
    status_code=status.HTTP_200_OK,
    summary="Upload tài liệu đơn hàng (PDF, DOCX) để trích xuất và tạo đơn nháp",
)
async def ingest_order_from_document(
    file: UploadFile = File(..., description="Tệp đơn đặt hàng PDF, DOCX"),
    current_user: User = Depends(require_permission("orders:create")),
    db: AsyncSession = Depends(get_db),
):
    """
    Tiếp nhận file đơn hàng PDF/DOCX độc lập:
    1. Parse nội dung văn bản qua Multi-format Parser
    2. Bóc tách qua Gemini OrderExtractor
    3. Đối chiếu ERP và đưa vào Approval Inbox
    """
    content_bytes = await file.read()
    if not content_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tệp tài liệu không được để trống.",
        )

    try:
        parsed_doc = parse_document(content_bytes, file.filename or "document.pdf", file.content_type)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Lỗi phân tích tệp tài liệu: {str(e)}",
        )

    parsed_email = parse_raw_order_text(parsed_doc.full_text, file.filename or "document")
    extractor = get_order_extractor()
    extracted = await extractor.extract_order(parsed_email)

    source_type = "document_pdf" if (file.filename or "").lower().endswith(".pdf") else "document_docx"

    result = await OrderIngestionService.ingest_extracted_order(
        session=db,
        extracted_order=extracted,
        actor_id=current_user.id,
        source_type=source_type,
        source_identifier=file.filename or "document",
    )
    return result


# =========================================================================
# Approval Inbox Endpoints (Human-In-The-Loop)
# =========================================================================

@router.get(
    "/approvals",
    response_model=List[ApprovalItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Lấy danh sách các yêu cầu trong Approval Inbox",
)
async def list_approvals(
    status_filter: Optional[str] = Query(None, alias="status", description="Lọc theo trạng thái: pending, approved, rejected"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    user_permissions: set[str] = Depends(get_current_user_permissions),
    db: AsyncSession = Depends(get_db),
):
    """
    Lấy danh sách yêu cầu phê duyệt.
    Tự động áp dụng Data Scoping: Người dùng không có quyền 'orders:approve' (sales_rep) chỉ xem được yêu cầu do chính mình gửi.
    """
    has_approve_perm = "*" in user_permissions or "orders:approve" in user_permissions
    requested_by_filter = None if has_approve_perm else current_user.id

    items = await ApprovalService.list_approvals(
        session=db,
        status=status_filter,
        limit=limit,
        offset=offset,
        requested_by=requested_by_filter,
    )
    return [
        ApprovalItemResponse(
            id=item.id,
            action_type=item.action_type,
            target_id=item.target_id,
            payload=item.payload,
            status=item.status,
            requested_by=item.requested_by,
            approved_by=item.approved_by,
            created_at=item.created_at,
        )
        for item in items
    ]


@router.get(
    "/approvals/{approval_id}",
    response_model=ApprovalItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Xem chi tiết một yêu cầu phê duyệt",
)
async def get_approval_detail(
    approval_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    user_permissions: set[str] = Depends(get_current_user_permissions),
    db: AsyncSession = Depends(get_db),
):
    """Xem chi tiết một yêu cầu phê duyệt (có kiểm tra quyền sở hữu đối với sales_rep)."""
    item = await ApprovalService.get_approval_by_id(db, approval_id)
    has_approve_perm = "*" in user_permissions or "orders:approve" in user_permissions
    if not has_approve_perm and item.requested_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xem yêu cầu phê duyệt của nhân viên khác.",
        )
    return ApprovalItemResponse(
        id=item.id,
        action_type=item.action_type,
        target_id=item.target_id,
        payload=item.payload,
        status=item.status,
        requested_by=item.requested_by,
        approved_by=item.approved_by,
        created_at=item.created_at,
    )


@router.post(
    "/approvals/{approval_id}/approve",
    response_model=ApprovalActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Phê duyệt đơn hàng nháp (chuyển sang confirmed, giữ tồn kho)",
)
async def approve_order(
    approval_id: uuid.UUID,
    current_user: User = Depends(require_permission("orders:approve")),
    db: AsyncSession = Depends(get_db),
):
    """Yêu cầu quyền 'orders:approve' (admin, director, sales_manager). Áp dụng Nguyên tắc 4 mắt."""
    return await ApprovalService.approve_request(
        session=db,
        approval_id=approval_id,
        approver_id=current_user.id,
    )


@router.post(
    "/approvals/{approval_id}/reject",
    response_model=ApprovalActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Từ chối yêu cầu phê duyệt đơn hàng nháp",
)
async def reject_order(
    approval_id: uuid.UUID,
    payload: Optional[RejectRequest] = None,
    current_user: User = Depends(require_permission("orders:reject")),
    db: AsyncSession = Depends(get_db),
):
    """Yêu cầu quyền 'orders:reject' (admin, sales_manager)."""
    reason = payload.reason if payload else None
    return await ApprovalService.reject_request(
        session=db,
        approval_id=approval_id,
        approver_id=current_user.id,
        reason=reason,
    )


@router.post(
    "/orders/{order_id}/deliver",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Thủ kho xác nhận đóng gói và xuất hàng (chuyển sang delivered, trừ kho vật lý)",
)
async def deliver_order_endpoint(
    order_id: uuid.UUID,
    current_user: User = Depends(require_permission("inventory:write")),
    db: AsyncSession = Depends(get_db),
):
    """
    Nghiệp vụ xuất kho dành cho Thủ kho (hoặc Admin):
    - Đơn hàng phải ở trạng thái 'confirmed'.
    - Tự động trừ số lượng thực tế trong kho (on_hand) và giải phóng số lượng đang giữ đơn (reserved).
    - Cập nhật đơn hàng sang trạng thái 'delivered'.
    """
    return await SalesOrderService.deliver_order(
        session=db,
        order_id=order_id,
        actor_id=current_user.id,
    )


@router.get(
    "/orders/{order_id}/quotation/pdf",
    summary="Xuất file PDF Báo giá kinh doanh (Sales Quotation / Proforma Invoice)",
)
async def export_order_quotation_pdf(
    order_id: uuid.UUID,
    current_user: User = Depends(require_permission("orders:read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Xuất file PDF Báo giá kinh doanh tiêu chuẩn:
    - Trả về binary stream application/pdf.
    - Hỗ trợ in trực tiếp hoặc xem trước trong trình duyệt / chat interface.
    """
    order = await SalesOrderService.get_order_by_id(db, order_id)
    pdf_bytes = await QuotationService.generate_pdf(db, order_id)

    filename = f"Bao_Gia_{order.order_number}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "X-Filename": filename,
        },
    )


@router.get(
    "/orders/{order_id}/quotation/summary",
    summary="Lấy thông tin tóm tắt báo giá phục vụ AI Chat Card Widget",
)
async def get_order_quotation_summary(
    order_id: uuid.UUID,
    current_user: User = Depends(require_permission("orders:read")),
    db: AsyncSession = Depends(get_db),
):
    order = await SalesOrderService.get_order_by_id(db, order_id)
    items_summary = [
        {
            "sku": item.product.sku if item.product else "N/A",
            "name": item.product.name if item.product else "Sản phẩm",
            "quantity": item.quantity,
            "unit_price": float(item.unit_price),
            "line_total": float(item.line_total),
        }
        for item in order.items
    ]
    filename = f"Bao_Gia_{order.order_number}.pdf"
    return {
        "order_id": str(order.id),
        "order_number": order.order_number,
        "customer_id": str(order.customer_id),
        "customer_name": order.customer.name if order.customer else "N/A",
        "customer_code": order.customer.code if order.customer else "N/A",
        "total_amount": float(order.total_amount),
        "status": order.status,
        "created_at": order.created_at.isoformat(),
        "filename": filename,
        "pdf_url": f"/api/v1/orders/{order.id}/quotation/pdf",
        "items": items_summary,
    }


@router.get(
    "/customers/{customer_id_or_code}/credit-check",
    response_model=CustomerCreditCheckResponse,
    summary="Kiểm tra hạn mức công nợ và tỷ lệ an toàn tín dụng của khách hàng",
)
async def check_customer_credit_limit(
    customer_id_or_code: str,
    additional_amount: Optional[float] = Query(0.0, description="Giá trị đơn hàng dự kiến đặt thêm (VND)"),
    current_user: User = Depends(require_permission("customers:read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Kiểm tra hạn mức tín dụng khách hàng:
    - Tính toán dư nợ hiện tại, hạn mức còn lại và tỷ lệ sử dụng công nợ.
    - Cảnh báo nếu đơn hàng mới vượt quá hạn mức cho phép.
    """
    from decimal import Decimal
    result = await CustomerService.check_credit_limit(
        session=db,
        customer_id_or_code=customer_id_or_code,
        additional_amount=Decimal(str(additional_amount or 0)),
    )
    return CustomerCreditCheckResponse(
        customer_id=result["customer_id"],
        customer_code=result["customer_code"],
        customer_name=result["customer_name"],
        credit_limit=result["credit_limit"],
        current_debt=result["current_debt"],
        available_credit=result["available_credit"],
        credit_utilization_rate=result["credit_utilization_rate"],
        is_exceeded=result["is_exceeded"],
        currency="VND",
    )


