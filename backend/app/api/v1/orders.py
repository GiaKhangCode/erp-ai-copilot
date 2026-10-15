import io
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
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

