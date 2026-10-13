import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExtractedOrderItem(BaseModel):
    """Chi tiết từng mặt hàng được trích xuất từ văn bản đơn hàng hoặc email."""
    raw_text: Optional[str] = Field(None, description="Đoạn văn bản gốc mô tả sản phẩm")
    sku_candidate: Optional[str] = Field(None, description="Mã SKU sản phẩm nếu có (VD: SKU-001)")
    product_name: str = Field(..., description="Tên sản phẩm được đề cập (VD: Laptop Pro 14-inch M3)")
    quantity: int = Field(..., ge=1, description="Số lượng đặt mua, phải là số nguyên dương >= 1")
    unit: Optional[str] = Field("cái", description="Đơn vị tính (chiếc, cái, bộ, thùng,...)")
    unit_price_in_doc: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Đơn giá ghi trong tài liệu (nếu có). Lưu ý: Server ERP sẽ tự đối chiếu giá niêm yết DB.",
    )
    line_total_in_doc: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Thành tiền ghi trong tài liệu (nếu có).",
    )
    notes: Optional[str] = Field(None, description="Ghi chú về mặt hàng (màu sắc, cấu hình, yêu cầu đóng gói)")


class ExtractedPurchaseOrder(BaseModel):
    """
    Cấu trúc dữ liệu có kiểu định nghĩa rõ ràng trích xuất từ email/PDF
    thông qua LLM Structured Output (Gemini Constrained Decoding).
    """
    customer_name_candidate: Optional[str] = Field(
        None,
        description="Tên công ty hoặc người mua hàng (VD: Công ty TNHH Minh Long)",
    )
    customer_code_candidate: Optional[str] = Field(
        None,
        description="Mã khách hàng nếu được nhắc đến (VD: CUS-0001)",
    )
    sender_email: Optional[str] = Field(
        None,
        description="Địa chỉ email người gửi nếu có",
    )
    sender_phone: Optional[str] = Field(
        None,
        description="Số điện thoại liên hệ của khách hàng",
    )
    tax_code: Optional[str] = Field(
        None,
        description="Mã số thuế của doanh nghiệp mua hàng",
    )
    shipping_address: Optional[str] = Field(
        None,
        description="Địa chỉ giao nhận hàng hóa yêu cầu",
    )
    requested_delivery_date: Optional[date] = Field(
        None,
        description="Ngày yêu cầu giao hàng mong muốn (YYYY-MM-DD)",
    )
    payment_terms_requested: Optional[str] = Field(
        None,
        description="Điều khoản thanh toán mong muốn (VD: Chuyển khoản trong 30 ngày, COD,...)",
    )
    items: List[ExtractedOrderItem] = Field(
        default_factory=list,
        description="Danh sách các sản phẩm và số lượng đặt hàng",
    )
    notes: Optional[str] = Field(
        None,
        description="Các yêu cầu hoặc chỉ dẫn bổ sung từ khách hàng",
    )
    confidence_score: float = Field(
        1.0,
        ge=0.0,
        le=1.0,
        description="Độ tin cậy của việc bóc tách thực thể",
    )


class OrderAttachmentMetadata(BaseModel):
    """Metadata của file đính kèm trong email."""
    filename: str
    content_type: str
    size_bytes: int
    extracted_text: Optional[str] = None


class ParsedEmailMessage(BaseModel):
    """Cấu trúc chuẩn hóa của email sau khi bóc tách từ file .eml hoặc email thô."""
    message_id: Optional[str] = None
    subject: str
    from_address: str
    sender_name: Optional[str] = None
    to_addresses: List[str] = Field(default_factory=list)
    date: Optional[datetime] = None
    body_plain: str = ""
    body_html: Optional[str] = None
    combined_body: str = ""
    attachments: List[OrderAttachmentMetadata] = Field(default_factory=list)


class ResolvedOrderItem(BaseModel):
    """Mặt hàng sau khi đối chiếu khớp nối với ERP Product Database."""
    product_id: uuid.UUID
    sku: str
    product_name: str
    quantity: int
    db_unit_price: Decimal
    doc_unit_price: Optional[Decimal] = None
    line_total: Decimal
    price_discrepancy: bool = False
    price_discrepancy_message: Optional[str] = None
    available_stock: int
    stock_sufficient: bool = True


class OrderDiscrepancyWarning(BaseModel):
    """Cảnh báo sai lệch thông tin phát hiện trong quá trình đối chiếu ERP."""
    warning_type: str = Field(
        ...,
        description="Loại cảnh báo: 'stock_shortage', 'price_mismatch', 'unmatched_customer', 'unmatched_sku', 'missing_delivery_date'",
    )
    severity: str = Field("warning", description="'info', 'warning', 'critical'")
    message: str
    field_affected: Optional[str] = None


class OrderIngestionResult(BaseModel):
    """Kết quả hoàn chỉnh của quy trình xử lý Email/Document-to-Order."""
    source_type: str = Field(..., description="'email_eml', 'email_text', 'document_pdf', 'document_docx'")
    source_identifier: str = Field(..., description="Tên file hoặc ID của nguồn đơn hàng")
    status: str = Field(
        ...,
        description="'success_draft_created', 'requires_human_correction', 'rejected_unmatched_items'",
    )
    extracted_data: ExtractedPurchaseOrder
    resolved_customer_id: Optional[uuid.UUID] = None
    resolved_customer_code: Optional[str] = None
    resolved_customer_name: Optional[str] = None
    resolved_items: List[ResolvedOrderItem] = Field(default_factory=list)
    total_amount: Decimal = Decimal("0.00")
    warnings: List[OrderDiscrepancyWarning] = Field(default_factory=list)
    draft_order_id: Optional[uuid.UUID] = None
    approval_request_id: Optional[uuid.UUID] = None
