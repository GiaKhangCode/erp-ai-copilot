import json
import logging
import re
from typing import Any, Dict, List, Optional
from google import genai
from google.genai import types

from app.core.config import settings
from app.ai.agents.state import (
    ERPAgentState,
    IntentClassificationResult,
    ExtractedEntities,
    OrderItemDraft,
    AgentIntent,
)
from app.ai.prompts.router_prompts import ROUTER_SYSTEM_PROMPT, build_router_user_prompt

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


class IntentRouter:
    """
    Bộ định tuyến phân loại ý định người dùng và trích xuất thực thể.
    Sử dụng Gemini 3.5 Flash-Lite với Grammar-constrained Decoding (response_schema).
    Tích hợp fallback heuristic đảm bảo Agent không bao giờ bị dừng đột ngột.
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
                logger.warning("GEMINI_API_KEY not set! IntentRouter will fallback to heuristic.")
            self.client = genai.Client(api_key=self.api_key)

    async def classify(
        self,
        query: str,
        history_summary: Optional[str] = None,
    ) -> IntentClassificationResult:
        """
        Phân loại ý định từ câu hỏi người dùng bằng Native Constrained Decoding.
        """
        clean_query = query.strip()
        if not clean_query:
            return IntentClassificationResult(
                intent="unknown",
                entities=ExtractedEntities(),
                confidence=0.0,
                reasoning="Câu hỏi rỗng",
            )

        # Chặn các prompt injection thô bạo muốn thực thi SQL
        if re.search(r"\b(drop table|truncate|delete from|exec\s*\(|execute_arbitrary_sql)\b", clean_query, re.IGNORECASE):
            logger.warning("Potential SQL injection detected in user query: %s", clean_query)
            return IntentClassificationResult(
                intent="unknown",
                entities=ExtractedEntities(),
                confidence=1.0,
                reasoning="Yêu cầu chứa lệnh can thiệp cơ sở dữ liệu không hợp lệ",
            )

        prompt = build_router_user_prompt(clean_query, history_summary)
        config = types.GenerateContentConfig(
            system_instruction=ROUTER_SYSTEM_PROMPT,
            temperature=self.temperature,
            response_mime_type="application/json",
            response_schema=IntentClassificationResult,
        )

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )

            # Ưu tiên 1: Lấy trực tiếp Pydantic object đã parse sẵn từ Gemini SDK
            if getattr(response, "parsed", None) and isinstance(response.parsed, IntentClassificationResult):
                return response.parsed

            # Ưu tiên 2: Parse từ response.text nếu chạy qua mock client hoặc fallback
            raw_text = response.text if response else ""
            if not raw_text:
                raise ValueError("Empty response from LLM")

            cleaned_text = _clean_json_markdown(raw_text)
            return IntentClassificationResult.model_validate_json(cleaned_text)

        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "ResourceExhausted" in str(e):
                logger.warning("Gemini 429 Rate Limit hit (15 RPM quota). Gracefully activating intelligent heuristic fallback.")
            else:
                logger.warning("LLM classification failed (%s). Falling back to heuristic classifier.", e)
            return self._classify_with_heuristic(clean_query)

    def _classify_with_heuristic(self, query: str) -> IntentClassificationResult:
        """
        Heuristic / Rule-based classifier dự phòng đảm bảo Agent không bao giờ chết.
        """
        lower = query.lower()

        # Trích xuất mã SKU
        sku_val: Optional[str] = None
        sku_match = re.search(r"\b(sku[-\w]+)\b", query, re.IGNORECASE)
        if sku_match:
            sku_val = sku_match.group(1).upper()

        # Trích xuất mã Khách hàng
        cus_val: Optional[str] = None
        cus_match = re.search(r"\b(cus[-\w]+)\b", query, re.IGNORECASE)
        if cus_match:
            cus_val = cus_match.group(1).upper()

        # Trích xuất mã Kho
        wh_val: Optional[str] = None
        wh_match = re.search(r"\b(wh[-\w]+)\b", query, re.IGNORECASE)
        if wh_match:
            wh_val = wh_match.group(1).upper()

        # Trích xuất số lượng
        qty_val: Optional[int] = None
        qty_match = re.search(r"(\d+)\s*(cái|chiếc|sản phẩm|hộp|thùng|đơn vị|bộ)?", query, re.IGNORECASE)
        if qty_match and qty_match.group(1):
            try:
                qty_val = int(qty_match.group(1))
            except ValueError:
                pass

        # 1. Chitchat check
        if re.search(r"\b(xin chào|chào bạn|chào em|hello|hi|bạn là ai|bạn có thể làm gì|cảm ơn|thank)\b", lower):
            return IntentClassificationResult(
                intent="chitchat",
                entities=ExtractedEntities(
                    sku=sku_val,
                    warehouse_code=wh_val,
                    customer_code=cus_val,
                    quantity=qty_val,
                ),
                confidence=0.85,
                reasoning="Quy tắc heuristic nhận diện lời chào hỏi / xã giao",
            )

        # 2. Document QA check (chính sách, quy định, bảo hành, đổi trả, cẩm nang)
        if re.search(r"(chính sách|quy định|quy chế|cẩm nang|bảo hành|đổi trả|công tác phí|an toàn lao động|nội quy|sổ tay|tài liệu)", lower):
            return IntentClassificationResult(
                intent="document_qa",
                entities=ExtractedEntities(
                    sku=sku_val,
                    warehouse_code=wh_val,
                    customer_code=cus_val,
                    quantity=qty_val,
                ),
                confidence=0.85,
                reasoning="Quy tắc heuristic nhận diện câu hỏi chính sách/tài liệu",
            )

        # 3. Create Order Draft check (lên đơn, tạo đơn, đặt hàng, mua hàng)
        if re.search(r"(tạo đơn|lên đơn|đặt hàng|mua hàng|tạo draft|order draft)", lower):
            items_list = None
            if sku_val and qty_val:
                items_list = [OrderItemDraft(sku=sku_val, quantity=qty_val)]
            return IntentClassificationResult(
                intent="create_order_draft",
                entities=ExtractedEntities(
                    sku=sku_val,
                    warehouse_code=wh_val,
                    customer_code=cus_val,
                    quantity=qty_val,
                    items=items_list,
                ),
                confidence=0.85,
                reasoning="Quy tắc heuristic nhận diện yêu cầu tạo đơn hàng nháp",
            )

        # 4. ERP Query check (tồn kho, còn bao nhiêu, giá, khách hàng, đơn hàng, doanh thu)
        if re.search(r"(tồn kho|còn bao nhiêu|giá|đơn hàng|doanh thu|báo cáo|khách hàng|sku|kho)", lower):
            return IntentClassificationResult(
                intent="erp_query",
                entities=ExtractedEntities(
                    sku=sku_val,
                    warehouse_code=wh_val,
                    customer_code=cus_val,
                    quantity=qty_val,
                ),
                confidence=0.85,
                reasoning="Quy tắc heuristic nhận diện câu hỏi tra cứu dữ liệu ERP",
            )

        # Default fallback
        return IntentClassificationResult(
            intent="unknown",
            entities=ExtractedEntities(
                sku=sku_val,
                warehouse_code=wh_val,
                customer_code=cus_val,
                quantity=qty_val,
            ),
            confidence=0.5,
            reasoning="Heuristic không tìm thấy từ khóa đặc trưng phù hợp",
        )


# =========================================================================
# LangGraph Node and Conditional Edge Functions
# =========================================================================

_router_instance: Optional[IntentRouter] = None


def get_intent_router() -> IntentRouter:
    """Singleton getter cho IntentRouter"""
    global _router_instance
    if _router_instance is None:
        _router_instance = IntentRouter()
    return _router_instance


async def classify_intent_node(state: ERPAgentState) -> Dict[str, Any]:
    """
    LangGraph Node: Phân tích intent và trích xuất entities từ câu hỏi người dùng.
    """
    query = state.get("user_query", "")
    if not query:
        # Nếu chưa có user_query trực tiếp, lấy từ tin nhắn cuối cùng trong messages
        messages = state.get("messages", [])
        if messages:
            last_msg = messages[-1]
            if hasattr(last_msg, "content"):
                query = str(last_msg.content)
            elif isinstance(last_msg, dict):
                query = str(last_msg.get("content", ""))

    router = get_intent_router()
    result = await router.classify(query)

    return {
        "user_query": query,
        "intent": result.intent,
        "entities": result.entities,
        "reasoning": result.reasoning,
    }


def route_by_intent(state: ERPAgentState) -> str:
    """
    LangGraph Conditional Edge Function: Định tuyến trạng thái sang node tiếp theo.
    """
    intent = state.get("intent", "unknown")
    if intent == "erp_query":
        return "erp_agent"
    elif intent == "document_qa":
        return "rag_agent"
    elif intent == "create_order_draft":
        return "draft_order_agent"
    elif intent == "chitchat":
        return "chitchat_agent"
    return "clarify_agent"
