import email
import email.policy
import email.utils
import html
import io
import logging
import re
from datetime import datetime
from email.message import EmailMessage
from typing import List, Optional, Tuple

from app.document_ai.schemas import OrderAttachmentMetadata, ParsedEmailMessage
from app.rag.parser import normalize_text, parse_docx, parse_pdf, parse_text

logger = logging.getLogger(__name__)


def _strip_html_tags(html_content: str) -> str:
    """Loại bỏ thẻ HTML và chuẩn hóa thực thể ký tự HTML sang văn bản thuần."""
    if not html_content:
        return ""
    # Chuyển đổi <br> và </p>, </tr> thành xuống dòng
    text = re.sub(r"(?i)<br\s*/?>", "\n", html_content)
    text = re.sub(r"(?i)</(p|tr|div|h[1-6])>", "\n\n", text)
    text = re.sub(r"(?i)<(td|th)[^>]*>", "\t", text)
    # Loại bỏ script/style tags và nội dung của chúng
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", text)
    # Loại bỏ toàn bộ các thẻ HTML còn lại
    text = re.sub(r"<[^>]+>", "", text)
    # Giải mã HTML entities (&nbsp;, &amp;, &lt;,...)
    text = html.unescape(text)
    return normalize_text(text)


def parse_email_bytes(file_bytes: bytes, filename: str = "email.eml") -> ParsedEmailMessage:
    """
    Phân tích tệp email (.eml / MIME RFC 822 chuẩn quốc tế) thành ParsedEmailMessage.
    Tự động giải mã charset, bóc tách nội dung Text / HTML và trích xuất file đính kèm (PDF, DOCX, TXT).
    """
    msg: EmailMessage = email.message_from_bytes(file_bytes, policy=email.policy.default)

    subject = msg.get("Subject", "(Không có tiêu đề)")
    message_id = msg.get("Message-ID")
    from_raw = msg.get("From", "")
    to_raw = msg.get("To", "")

    # Phân tách tên hiển thị và địa chỉ email người gửi
    sender_name, from_address = email.utils.parseaddr(from_raw)
    if not from_address and from_raw:
        from_address = from_raw

    # Danh sách địa chỉ nhận
    to_addresses = [addr[1] for addr in email.utils.getaddresses([to_raw]) if addr[1]]

    # Parse thời gian gửi
    date_header = msg.get("Date")
    parsed_date: Optional[datetime] = None
    if date_header:
        try:
            parsed_date = email.utils.parsedate_to_datetime(date_header)
        except Exception as e:
            logger.warning("Could not parse email date header '%s': %s", date_header, e)

    body_plain_parts: List[str] = []
    body_html_parts: List[str] = []
    attachments: List[OrderAttachmentMetadata] = []

    for part in msg.walk():
        content_disposition = part.get_content_disposition()
        content_type = part.get_content_type()
        part_filename = part.get_filename()

        # Kiểm tra nếu là file đính kèm
        if content_disposition == "attachment" or (part_filename and content_disposition != "inline"):
            attachment_name = part_filename or f"attachment_{len(attachments)+1}"
            payload_bytes = part.get_payload(decode=True) or b""
            size = len(payload_bytes)

            extracted_text: Optional[str] = None
            lower_name = attachment_name.lower()

            try:
                if lower_name.endswith(".pdf") or "pdf" in content_type:
                    parsed_doc = parse_pdf(payload_bytes, attachment_name)
                    extracted_text = parsed_doc.full_text
                elif lower_name.endswith(".docx") or "officedocument.wordprocessingml" in content_type:
                    parsed_doc = parse_docx(payload_bytes, attachment_name)
                    extracted_text = parsed_doc.full_text
                elif lower_name.endswith(".txt") or "text/plain" in content_type:
                    parsed_doc = parse_text(payload_bytes, attachment_name)
                    extracted_text = parsed_doc.full_text
            except Exception as e:
                logger.warning("Error parsing attachment '%s': %s", attachment_name, e)

            attachments.append(
                OrderAttachmentMetadata(
                    filename=attachment_name,
                    content_type=content_type,
                    size_bytes=size,
                    extracted_text=extracted_text,
                )
            )
        elif content_type == "text/plain":
            try:
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                if payload:
                    body_plain_parts.append(payload.decode(charset, errors="replace"))
            except Exception as e:
                logger.warning("Error decoding text/plain part: %s", e)
        elif content_type == "text/html":
            try:
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                if payload:
                    body_html_parts.append(payload.decode(charset, errors="replace"))
            except Exception as e:
                logger.warning("Error decoding text/html part: %s", e)

    raw_plain = "\n\n".join(body_plain_parts).strip()
    raw_html = "\n\n".join(body_html_parts).strip() if body_html_parts else None

    # Nếu không có text/plain, trích xuất văn bản thuần từ html
    if raw_plain:
        primary_text = normalize_text(raw_plain)
    elif raw_html:
        primary_text = _strip_html_tags(raw_html)
    else:
        primary_text = ""

    # Kết hợp nội dung email và toàn bộ văn bản từ file đính kèm (nếu có)
    combined_sections = [primary_text]
    for att in attachments:
        if att.extracted_text and att.extracted_text.strip():
            combined_sections.append(
                f"\n--- [TÀI LIỆU ĐÍNH KÈM: {att.filename}] ---\n{att.extracted_text.strip()}"
            )

    combined_body = "\n\n".join(s for s in combined_sections if s.strip())

    return ParsedEmailMessage(
        message_id=message_id,
        subject=subject,
        from_address=from_address,
        sender_name=sender_name or None,
        to_addresses=to_addresses,
        date=parsed_date,
        body_plain=primary_text,
        body_html=raw_html,
        combined_body=combined_body,
        attachments=attachments,
    )


def parse_raw_order_text(text: str, source_identifier: str = "raw_input") -> ParsedEmailMessage:
    """
    Chuẩn hóa văn bản đơn hàng thô (tin nhắn chat, ghi chú, email dán trực tiếp)
    thành cấu trúc ParsedEmailMessage nhất quán.
    """
    cleaned = normalize_text(text)
    return ParsedEmailMessage(
        subject="Đơn đặt hàng trực tiếp",
        from_address="",
        combined_body=cleaned,
        body_plain=cleaned,
    )
