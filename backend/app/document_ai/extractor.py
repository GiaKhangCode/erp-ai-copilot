import asyncio
import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from google import genai
from google.genai import types

from app.core.config import settings
from app.document_ai.email_parser import ParsedEmailMessage
from app.document_ai.prompts import ORDER_EXTRACTION_SYSTEM_PROMPT, build_order_extraction_user_prompt
from app.document_ai.schemas import ExtractedOrderItem, ExtractedPurchaseOrder

logger = logging.getLogger(__name__)


def _clean_json_markdown(text: str) -> str:
    """Loại bỏ markdown code fence nếu mô hình trả về ```json ... ```"""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


class OrderExtractor:
    """
    Bộ trích xuất thông tin đơn đặt hàng từ email / tài liệu văn bản.
    - Sử dụng Gemini 3.5 Flash-Lite với Native Constrained Decoding (response_schema=ExtractedPurchaseOrder).
    - Tích hợp Fast Security Guardrails chống SQL/Prompt Injection trong email.
    - Tự động fallback Heuristic Rule-based Extractor khi gặp sự cố mạng hoặc chạm hạn mức 15 RPM.
    """

    def __init__(
        self,
        genai_client: Optional[genai.Client] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
    ):
        self.api_key = settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self.temperature = temperature

        if genai_client:
            self.client = genai_client
        else:
            if not self.api_key:
                logger.warning("GEMINI_API_KEY not set! OrderExtractor will fallback to heuristic.")
            self.client = genai.Client(api_key=self.api_key)

    async def extract_order(
        self,
        parsed_email: ParsedEmailMessage,
        max_retries: int = 2,
    ) -> ExtractedPurchaseOrder:
        """
        Trích xuất dữ liệu có cấu trúc từ ParsedEmailMessage.
        """
        content = parsed_email.combined_body or parsed_email.body_plain or ""
        clean_content = content.strip()

        if not clean_content:
            return ExtractedPurchaseOrder(
                sender_email=parsed_email.from_address or None,
                confidence_score=0.0,
                notes="Nội dung email hoặc tài liệu rỗng",
            )

        # 1. Fast Security Filter: Phát hiện các dấu hiệu tấn công phá hoại SQL trong tài liệu
        if re.search(r"\b(drop table|truncate|delete from|exec\s*\(|execute_arbitrary_sql)\b", clean_content, re.IGNORECASE):
            logger.warning("Security Guardrail: SQL injection attempt detected in order document: %s", clean_content[:100])
            # Trích xuất an toàn bằng heuristic, cô lập nội dung SQL độc hại
            extracted = self._extract_with_heuristic(parsed_email)
            extracted.notes = "Cảnh báo: Nội dung tài liệu có chứa cú pháp câu lệnh cơ sở dữ liệu bất thường và đã bị vô hiệu hóa."
            return extracted

        prompt = build_order_extraction_user_prompt(
            subject=parsed_email.subject,
            sender=parsed_email.from_address,
            combined_body=clean_content,
        )

        config = types.GenerateContentConfig(
            system_instruction=ORDER_EXTRACTION_SYSTEM_PROMPT,
            temperature=self.temperature,
            response_mime_type="application/json",
            response_schema=ExtractedPurchaseOrder,
        )

        last_err = None
        for attempt in range(1, max_retries + 1):
            try:
                response = await self.client.aio.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )

                # Ưu tiên 1: Lấy Pydantic parsed object từ SDK
                if getattr(response, "parsed", None) and isinstance(response.parsed, ExtractedPurchaseOrder):
                    result = response.parsed
                else:
                    raw_text = response.text if response else ""
                    if not raw_text:
                        raise ValueError("Empty response text from LLM")
                    cleaned_json = _clean_json_markdown(raw_text)
                    result = ExtractedPurchaseOrder.model_validate_json(cleaned_json)

                # Bổ sung sender_email từ header email nếu mô hình không trích xuất được
                if not result.sender_email and parsed_email.from_address:
                    result.sender_email = parsed_email.from_address

                return result

            except Exception as e:
                last_err = e
                if "429" in str(e) or "ResourceExhausted" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    logger.warning("Gemini 429 Rate Limit hit in OrderExtractor. Backing off 4s (attempt %d/%d)...", attempt, max_retries)
                    if attempt < max_retries:
                        await asyncio.sleep(4)
                        continue
                logger.warning("LLM Order Extraction failed (%s). Activating Heuristic fallback.", e)
                break

        return self._extract_with_heuristic(parsed_email)

    def _extract_with_heuristic(self, parsed_email: ParsedEmailMessage) -> ExtractedPurchaseOrder:
        """
        Bộ trích xuất dự phòng bằng quy tắc Heuristic / Regular Expressions
        đảm bảo hệ thống vẫn hoạt động thông suốt khi mạng mất kết nối hoặc chạm trần RPM.
        """
        text = parsed_email.combined_body or parsed_email.body_plain or ""
        subject = parsed_email.subject or ""
        full_text = f"{subject}\n{text}"

        # 1. Trích xuất mã khách hàng (CUS-XXXX)
        cus_code = None
        cus_match = re.search(r"\b(CUS-\d{4,})\b", full_text, re.IGNORECASE)
        if cus_match:
            cus_code = cus_match.group(1).upper()

        # 2. Trích xuất tên công ty khách hàng
        cus_name = None
        name_match = re.search(
            r"(Công ty\s+TNHH\s+[\w\s]+|Công ty\s+Cổ phần\s+[\w\s]+|Cty\s+[\w\s]+|Doanh nghiệp\s+[\w\s]+)",
            full_text,
            re.IGNORECASE,
        )
        if name_match:
            cus_name = name_match.group(1).strip()
        elif parsed_email.sender_name:
            cus_name = parsed_email.sender_name

        # 3. Trích xuất mã số thuế trước (MST thường có prefix MST hoặc mã số thuế)
        tax = None
        tax_match = re.search(r"(?:MST|mã số thuế)[:\s]*([0-9\-]{10,14})", full_text, re.IGNORECASE)
        if tax_match:
            tax = tax_match.group(1).strip()

        # 4. Trích xuất số điện thoại (ưu tiên có tiền tố SĐT/Tel/Điện thoại hoặc đầu số di động 09, 08, 07, 03, 05)
        phone = None
        phone_match_prefixed = re.search(r"(?:SĐT|điện thoại|tel|phone|hotline)[:\s]*(\+?84\d{9,10}|0\d{9,10})\b", full_text, re.IGNORECASE)
        if phone_match_prefixed:
            phone = phone_match_prefixed.group(1).strip()
        else:
            phone_match = re.search(r"\b(0[35789]\d{8}|\+84[35789]\d{8})\b", full_text)
            if phone_match and phone_match.group(1) != tax:
                phone = phone_match.group(1)

        # 5. Trích xuất ngày giao hàng (YYYY-MM-DD hoặc DD/MM/YYYY)
        deliv_date = None
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", full_text)
        if date_match:
            try:
                deliv_date = date.fromisoformat(date_match.group(1))
            except ValueError:
                pass
        else:
            dmy_match = re.search(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", full_text)
            if dmy_match:
                try:
                    d, m, y = int(dmy_match.group(1)), int(dmy_match.group(2)), int(dmy_match.group(3))
                    deliv_date = date(y, m, d)
                except ValueError:
                    pass

        # 6. Trích xuất các mặt hàng (SKU-XXX kèm số lượng)
        items: List[ExtractedOrderItem] = []
        # 6. Trích xuất các mặt hàng (tìm kiếm theo từng dòng chứa SKU và số lượng)
        items: List[ExtractedOrderItem] = []
        lines = full_text.split("\n")
        seen_skus = set()

        for line in lines:
            line_clean = line.strip().strip("-*•")
            sku_found = re.search(r"\b(SKU-\d+)\b", line_clean, re.IGNORECASE)
            if not sku_found:
                continue

            sku_val = sku_found.group(1).upper()
            if sku_val in seen_skus:
                continue

            # Tìm số lượng
            qty_match = re.search(r"(\d+)\s*(cái|chiếc|bộ|hộp|thùng|con|máy)?", line_clean, re.IGNORECASE)
            qty = 1
            unit = "cái"
            if qty_match:
                try:
                    qty = int(qty_match.group(1))
                    unit = qty_match.group(2) or "cái"
                except ValueError:
                    qty = 1

            # Tên sản phẩm lấy từ phần trước SKU hoặc sau SKU
            name_part = re.sub(r"\b(SKU-\d+)\b", "", line_clean, flags=re.IGNORECASE)
            name_part = re.sub(r"(?:mua|đặt|cần|chiếc|cái|con|máy|\d+|mã:?|\(|\))", " ", name_part, flags=re.IGNORECASE).strip()
            name_val = re.sub(r"\s+", " ", name_part).strip() or f"Sản phẩm {sku_val}"

            items.append(
                ExtractedOrderItem(
                    raw_text=line_clean.strip(),
                    sku_candidate=sku_val,
                    product_name=name_val,
                    quantity=qty,
                    unit=unit,
                )
            )
            seen_skus.add(sku_val)

        return ExtractedPurchaseOrder(
            customer_name_candidate=cus_name,
            customer_code_candidate=cus_code,
            sender_email=parsed_email.from_address or None,
            sender_phone=phone,
            tax_code=tax,
            requested_delivery_date=deliv_date,
            items=items,
            confidence_score=0.75,
            notes="Trích xuất tự động qua Heuristic Rule-based Extractor",
        )


_order_extractor_instance: Optional[OrderExtractor] = None


def get_order_extractor() -> OrderExtractor:
    """Singleton getter cho OrderExtractor"""
    global _order_extractor_instance
    if _order_extractor_instance is None:
        _order_extractor_instance = OrderExtractor()
    return _order_extractor_instance
