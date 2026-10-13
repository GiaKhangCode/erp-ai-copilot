import email
import email.message
import io
import uuid
from decimal import Decimal
import pytest

from app.document_ai.schemas import (
    ExtractedOrderItem,
    ExtractedPurchaseOrder,
    OrderAttachmentMetadata,
    OrderDiscrepancyWarning,
    OrderIngestionResult,
    ParsedEmailMessage,
    ResolvedOrderItem,
)
from app.document_ai.email_parser import _strip_html_tags, parse_email_bytes, parse_raw_order_text


def test_extracted_purchase_order_schema_validation():
    """Kiểm thử tính hợp lệ của Pydantic schema cho đơn đặt hàng trích xuất."""
    item1 = ExtractedOrderItem(
        raw_text="2 cái Laptop Dell M3",
        sku_candidate="SKU-001",
        product_name="Laptop Pro 14-inch M3",
        quantity=2,
        unit="cái",
        unit_price_in_doc=Decimal("28500000"),
        line_total_in_doc=Decimal("57000000"),
    )
    assert item1.quantity == 2
    assert item1.sku_candidate == "SKU-001"

    po = ExtractedPurchaseOrder(
        customer_name_candidate="Công ty TNHH Minh Long",
        customer_code_candidate="CUS-0001",
        sender_email="procurement@minhlong.vn",
        sender_phone="0901234567",
        tax_code="0101234567",
        shipping_address="Tầng 5, Tòa nhà Landmark 81, TP.HCM",
        items=[item1],
    )
    assert po.customer_code_candidate == "CUS-0001"
    assert len(po.items) == 1
    assert po.confidence_score == 1.0


def test_extracted_order_item_quantity_invariant():
    """Kiểm thử bất biến số lượng đặt mua phải là số nguyên dương >= 1."""
    with pytest.raises(Exception):
        ExtractedOrderItem(
            product_name="Chuột không dây",
            quantity=0,  # Vi phạm ràng buộc ge=1
        )


def test_strip_html_tags():
    """Kiểm thử hàm bóc tách HTML tags sang văn bản thuần sạch."""
    html_sample = """
    <html>
        <body>
            <h3>Đơn Đặt Hàng</h3>
            <p>Kính gửi: <b>Bộ phận Bán Hàng</b></p>
            <p>Chúng tôi muốn đặt mua:<br/>- 10 cái SKU-001</p>
        </body>
    </html>
    """
    cleaned = _strip_html_tags(html_sample)
    assert "Đơn Đặt Hàng" in cleaned
    assert "Bộ phận Bán Hàng" in cleaned
    assert "10 cái SKU-001" in cleaned
    assert "<html>" not in cleaned
    assert "<p>" not in cleaned


def test_parse_plain_text_email():
    """Kiểm thử phân tích email định dạng text/plain đơn giản."""
    msg = email.message.EmailMessage()
    msg["Subject"] = "Đơn đặt hàng từ Cty Minh Long PO-2026-001"
    msg["From"] = "Minh Long Procurement <muahang@minhlong.vn>"
    msg["To"] = "sales@erpcopilot.vn"
    msg["Message-ID"] = "<unique-msg-123@minhlong.vn>"
    msg.set_content(
        "Chào ERP Copilot,\n\n"
        "Chúng tôi muốn đặt 5 cái Laptop SKU-001 và 10 cái Chuột không dây SKU-002.\n"
        "Giao trước ngày 2026-10-25.\n\n"
        "Trân trọng,\nMinh Long"
    )

    eml_bytes = msg.as_bytes()
    parsed = parse_email_bytes(eml_bytes, "order.eml")

    assert parsed.subject == "Đơn đặt hàng từ Cty Minh Long PO-2026-001"
    assert parsed.from_address == "muahang@minhlong.vn"
    assert parsed.sender_name == "Minh Long Procurement"
    assert parsed.message_id == "<unique-msg-123@minhlong.vn>"
    assert "SKU-001" in parsed.body_plain
    assert "SKU-002" in parsed.combined_body
    assert len(parsed.attachments) == 0


def test_parse_multipart_email_with_txt_attachment():
    """Kiểm thử phân tích email multipart chứa tệp văn bản đính kèm."""
    msg = email.message.EmailMessage()
    msg["Subject"] = "Đặt hàng theo danh sách đính kèm"
    msg["From"] = "muahang@ancuong.vn"
    msg["To"] = "sales@erpcopilot.vn"
    msg.set_content("Vui lòng xem chi tiết danh mục hàng hóa trong file đính kèm.")

    attachment_content = (
        "MÃ HÀNG | TÊN SẢN PHẨM | SỐ LƯỢNG\n"
        "SKU-001 | Laptop Pro 14 M3 | 20 cái\n"
        "SKU-002 | Chuột công thái học | 50 cái\n"
    )
    msg.add_attachment(
        attachment_content.encode("utf-8"),
        maintype="text",
        subtype="plain",
        filename="danh_sach_dat_hang.txt",
    )

    eml_bytes = msg.as_bytes()
    parsed = parse_email_bytes(eml_bytes, "po_with_attachment.eml")

    assert parsed.from_address == "muahang@ancuong.vn"
    assert len(parsed.attachments) == 1
    assert parsed.attachments[0].filename == "danh_sach_dat_hang.txt"
    assert parsed.attachments[0].extracted_text is not None
    assert "Laptop Pro 14 M3" in parsed.attachments[0].extracted_text
    # Nội dung đính kèm phải được gom vào combined_body để sẵn sàng cho LLM trích xuất
    assert "Laptop Pro 14 M3" in parsed.combined_body
    assert "[TÀI LIỆU ĐÍNH KÈM: danh_sach_dat_hang.txt]" in parsed.combined_body


def test_parse_raw_order_text():
    """Kiểm thử chuẩn hóa văn bản đơn hàng nhập trực tiếp."""
    raw = "   Lên đơn cho khách CUS-0001 mua 3 cái SKU-001 giao ngày mai.   "
    parsed = parse_raw_order_text(raw)
    assert parsed.subject == "Đơn đặt hàng trực tiếp"
    assert parsed.body_plain == "Lên đơn cho khách CUS-0001 mua 3 cái SKU-001 giao ngày mai."
    assert parsed.combined_body == parsed.body_plain
