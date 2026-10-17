import asyncio
import json
import logging
from typing import Any, Dict, List, Literal, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.core.config import settings
from app.ai.agents.state import ERPAgentState, ExtractedEntities, OrderItemDraft
from app.ai.agents.router import classify_intent_node, route_by_intent
from app.ai.tools.context import UserContext, get_current_user_context, set_current_user_context
from app.ai.tools import (
    ALL_AGENT_TOOLS,
    get_inventory,
    get_product,
    list_products,
    get_customer,
    list_customers,
    get_sales_orders,
    get_revenue_report,
    propose_sales_order_draft,
    deliver_sales_order,
    adjust_inventory,
    generate_sales_quotation,
    check_customer_credit,
    search_company_knowledge,
)
from app.ai.prompts.agent_prompts import (
    SUPER_AGENT_SYSTEM_PROMPT,
    ERP_AGENT_SYSTEM_PROMPT,
    CHITCHAT_SYSTEM_PROMPT,
    CLARIFY_SYSTEM_PROMPT,
    SYNTHESIZER_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

# Danh sách ERP Domain tools
ERP_READ_TOOLS = [
    get_inventory,
    get_product,
    list_products,
    get_customer,
    list_customers,
    get_sales_orders,
    get_revenue_report,
    deliver_sales_order,
    adjust_inventory,
    generate_sales_quotation,
    check_customer_credit,
]


def _get_llm(model: Optional[str] = None, temperature: float = 0.0) -> ChatGoogleGenerativeAI:
    """Khởi tạo ChatGoogleGenerativeAI với mô hình, max_retries và timeout tối ưu"""
    target_model = model or settings.GEMINI_MODEL
    return ChatGoogleGenerativeAI(
        model=target_model,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=temperature,
        max_retries=settings.GEMINI_MAX_RETRIES,
        timeout=settings.GEMINI_TIMEOUT_SECONDS,
    )

def _extract_text(content: Any) -> str:
    """Trích xuất text thuần từ content (chuỗi hoặc danh sách block/dict)"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, str):
                texts.append(part)
            elif isinstance(part, dict) and "text" in part:
                texts.append(str(part["text"]))
            elif hasattr(part, "text"):
                texts.append(str(getattr(part, "text")))
        return "\n".join(texts)
    return str(content)


# =========================================================================
# ReAct Super-Agent Node Handlers (Multi-step Tool Calling Loop)
# =========================================================================

async def super_agent_node(state: ERPAgentState) -> Dict[str, Any]:
    """
    Super-Agent Core Node: Nạp toàn bộ kho ALL_AGENT_TOOLS, hỗ trợ lập kế hoạch và suy nghĩ nhiều bước (ReAct loop).
    """
    set_current_user_context(UserContext(
        user_id=state.get("user_id"),
        user_role=state.get("user_role"),
        user_name=state.get("user_name"),
        user_email=state.get("user_email"),
        user_permissions=state.get("user_permissions"),
    ))

    system_msg = SystemMessage(content=SUPER_AGENT_SYSTEM_PROMPT)
    messages: List[BaseMessage] = [system_msg]

    history = state.get("messages", [])
    if history:
        messages.extend(history)
    else:
        query = state.get("user_query", "")
        messages.append(HumanMessage(content=query))

    last_err = None
    for attempt in range(1, 3):
        try:
            llm = _get_llm(temperature=0.0).bind_tools(ALL_AGENT_TOOLS)
            response = await llm.ainvoke(messages)
            return {
                "messages": [response],
            }
        except Exception as e:
            last_err = e
            if "429" in str(e) or "ResourceExhausted" in str(e):
                logger.warning("Gemini 429 rate limit hit in super_agent_node (attempt %d). Backing off 5s...", attempt)
                await asyncio.sleep(5)
                continue
            break

    logger.error("Error in super_agent_node: %s", last_err)
    err_msg = AIMessage(content=f"Đã xảy ra lỗi khi kết nối công cụ Super-Agent: {str(last_err)}")
    return {
        "messages": [err_msg],
        "error": str(last_err),
    }


def should_continue(state: ERPAgentState) -> Literal["tools", "synthesizer"]:
    """
    Conditional Edge: Kiểm tra xem Super-Agent có yêu cầu gọi Tool tiếp không.
    Áp dụng guardrail recursion_limit <= 6.
    """
    current_iter = state.get("iteration", 0)
    if current_iter >= 6:
        logger.warning("Super-Agent reached max iteration limit (6). Transitioning to synthesizer.")
        return "synthesizer"

    messages = state.get("messages", [])
    if messages:
        last_msg = messages[-1]
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            return "tools"

    return "synthesizer"


async def super_tools_node(state: ERPAgentState) -> Dict[str, Any]:
    """
    Node thực thi các tool calls từ Super-Agent:
    - Chạy tool với context bảo mật
    - Trích xuất citations từ RAG nếu có
    - Trích xuất proposed_action từ propose_sales_order_draft nếu có
    - Đếm số lần lặp (iteration) để bảo vệ chống loop
    """
    set_current_user_context(UserContext(
        user_id=state.get("user_id"),
        user_role=state.get("user_role"),
    ))

    tools_by_name = {tool.name: tool for tool in ALL_AGENT_TOOLS}
    messages = state.get("messages", [])
    tool_messages: List[BaseMessage] = []
    tool_results = list(state.get("tool_results", []))
    citations = list(state.get("citations", []))
    proposed_action = state.get("proposed_action")
    thought_steps = list(state.get("thought_steps", []) or [])

    tool_label_map = {
        "search_company_knowledge": ("Tra cứu tài liệu nội bộ (RAG)", "Truy vấn chính sách và cẩm nang công ty"),
        "get_inventory": ("Kiểm tra tồn kho", "Kiểm tra số lượng khả dụng"),
        "get_product": ("Tra cứu thông tin sản phẩm", "Kiểm tra thông số và giá niêm yết"),
        "list_products": ("Tìm kiếm danh mục sản phẩm", "Lấy danh sách mặt hàng"),
        "get_customer": ("Tra cứu thông tin khách hàng", "Xác minh thông tin đối tác"),
        "list_customers": ("Tìm kiếm khách hàng", "Lấy danh sách đối tác"),
        "get_sales_orders": ("Tra cứu đơn hàng", "Kiểm tra lịch sử giao dịch"),
        "get_revenue_report": ("Báo cáo doanh thu", "Trích xuất số liệu tài chính"),
        "propose_sales_order_draft": ("Đề xuất tạo đơn nháp (HITL)", "Khởi tạo bản nháp đơn hàng chờ phê duyệt"),
        "deliver_sales_order": ("Xuất kho đơn hàng", "Trừ tồn kho vật lý và hoàn tất giao hàng"),
        "adjust_inventory": ("Điều chỉnh tồn kho", "Lập phiếu kiểm kê và cập nhật số lượng tồn"),
    }

    if messages:
        last_msg = messages[-1]
        tool_calls = getattr(last_msg, "tool_calls", []) or []
        for idx, call in enumerate(tool_calls):
            name = call.get("name")
            args = call.get("args", {})
            call_id = call.get("id") or f"call_{idx}_{name}"
            tool = tools_by_name.get(name)

            title, desc = tool_label_map.get(name, (f"Thực thi {name}", f"Chạy công cụ {name}"))
            arg_summary = ", ".join(f"{k}={v}" for k, v in args.items() if v is not None)[:60]
            detail = f"{desc} ({arg_summary})" if arg_summary else desc

            if tool:
                try:
                    res = await tool.ainvoke(args)
                    res_str = str(res)
                    tool_messages.append(ToolMessage(content=res_str, tool_call_id=call_id, name=name))

                    try:
                        parsed = json.loads(res_str)
                        if isinstance(parsed, dict):
                            tool_results.append(parsed)
                            # Nếu là tool RAG search_company_knowledge
                            if "citations" in parsed and isinstance(parsed["citations"], list):
                                for cit in parsed["citations"]:
                                    if cit not in citations:
                                        citations.append(cit)
                            # Nếu là tool propose_sales_order_draft
                            if parsed.get("action") == "create_sales_order_draft" and parsed.get("success"):
                                proposed_action = parsed
                        else:
                            tool_results.append({"name": name, "result": parsed})
                    except Exception:
                        tool_results.append({"name": name, "result": res_str})

                    thought_steps.append({
                        "step": f"tool_{name}",
                        "title": title,
                        "detail": detail,
                        "status": "completed",
                    })
                except Exception as e:
                    logger.error("Error executing tool %s: %s", name, e)
                    err_str = f"Lỗi thực thi công cụ {name}: {str(e)}"
                    tool_messages.append(ToolMessage(content=err_str, tool_call_id=call_id, name=name))
                    tool_results.append({"name": name, "error": str(e), "success": False})
                    thought_steps.append({
                        "step": f"tool_{name}",
                        "title": title,
                        "detail": f"{detail} - Thất bại: {str(e)}",
                        "status": "error",
                    })

    current_iter = state.get("iteration", 0) + 1

    return {
        "messages": tool_messages,
        "tool_results": tool_results,
        "citations": citations,
        "proposed_action": proposed_action,
        "thought_steps": thought_steps,
        "iteration": current_iter,
    }


# =========================================================================
# Legacy Node Handlers (Giữ để tương thích ngược)
# =========================================================================

async def erp_agent_node(state: ERPAgentState) -> Dict[str, Any]:
    """
    Node xử lý truy vấn dữ liệu ERP: gọi mô hình liên kết với Allowlisted ERP Read Tools.
    """
    # 1. Inject trusted identity context
    set_current_user_context(UserContext(
        user_id=state.get("user_id"),
        user_role=state.get("user_role"),
    ))

    # 2. Xây dựng prompt
    system_msg = SystemMessage(content=ERP_AGENT_SYSTEM_PROMPT)
    messages: List[BaseMessage] = [system_msg]

    history = state.get("messages", [])
    if history:
        messages.extend(history)
    else:
        query = state.get("user_query", "")
        messages.append(HumanMessage(content=query))

    # 3. Gắn tools và thực thi
    last_err = None
    for attempt in range(1, 3):
        try:
            llm = _get_llm(temperature=0.0).bind_tools(ERP_READ_TOOLS)
            response = await llm.ainvoke(messages)
            return {
                "messages": [response],
            }
        except Exception as e:
            last_err = e
            if "429" in str(e) or "ResourceExhausted" in str(e):
                logger.warning("Gemini 429 rate limit hit in erp_agent_node (attempt %d). Backing off 5s...", attempt)
                await asyncio.sleep(5)
                continue
            break

    logger.error("Error in erp_agent_node: %s", last_err)
    # Fallback error message
    err_msg = AIMessage(content=f"Đã xảy ra lỗi khi kết nối công cụ ERP: {str(last_err)}")
    return {
        "messages": [err_msg],
        "error": str(last_err),
    }


def should_call_erp_tools(state: ERPAgentState) -> Literal["erp_tools", "synthesizer"]:
    """Conditional Edge: Kiểm tra xem erp_agent có yêu cầu gọi Tool không"""
    messages = state.get("messages", [])
    if messages:
        last_msg = messages[-1]
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            return "erp_tools"
    return "synthesizer"


async def erp_tools_node(state: ERPAgentState) -> Dict[str, Any]:
    """
    Node thực thi các công cụ ERP với bảo mật context tự động nạp từ state.
    Thực thi trực tiếp danh sách tool_calls từ mô hình AI một cách an toàn và tương thích.
    """
    set_current_user_context(UserContext(
        user_id=state.get("user_id"),
        user_role=state.get("user_role"),
    ))

    tools_by_name = {tool.name: tool for tool in ERP_READ_TOOLS}
    messages = state.get("messages", [])
    tool_messages: List[BaseMessage] = []
    tool_results = list(state.get("tool_results", []))

    if messages:
        last_msg = messages[-1]
        tool_calls = getattr(last_msg, "tool_calls", []) or []
        for idx, call in enumerate(tool_calls):
            name = call.get("name")
            args = call.get("args", {})
            call_id = call.get("id") or f"call_{idx}_{name}"
            tool = tools_by_name.get(name)
            if tool:
                try:
                    res = await tool.ainvoke(args)
                    res_str = str(res)
                    tool_messages.append(ToolMessage(content=res_str, tool_call_id=call_id, name=name))
                    try:
                        parsed = json.loads(res_str)
                        tool_results.append(parsed if isinstance(parsed, dict) else {"result": parsed})
                    except Exception:
                        tool_results.append({"name": name, "result": res_str})
                except Exception as e:
                    logger.error("Error executing tool %s: %s", name, e)
                    err_str = f"Lỗi thực thi công cụ {name}: {str(e)}"
                    tool_messages.append(ToolMessage(content=err_str, tool_call_id=call_id, name=name))
                    tool_results.append({"name": name, "error": str(e), "success": False})

    return {
        "messages": tool_messages,
        "tool_results": tool_results,
    }



async def rag_agent_node(state: ERPAgentState) -> Dict[str, Any]:
    """
    Node xử lý hỏi đáp tài liệu: Gọi RAG tool với quyền truy cập ACL của người dùng.
    """
    set_current_user_context(UserContext(
        user_id=state.get("user_id"),
        user_role=state.get("user_role"),
    ))

    query = state.get("user_query", "")
    try:
        raw_result = await search_company_knowledge.ainvoke({"query": query})
        data = json.loads(raw_result)

        citations = data.get("citations", [])
        tool_results = state.get("tool_results", [])
        updated_tool_results = list(tool_results) + [data]

        return {
            "retrieved_context": [data],
            "citations": citations,
            "tool_results": updated_tool_results,
        }
    except Exception as e:
        logger.error("Error in rag_agent_node: %s", e)
        return {
            "error": str(e),
            "tool_results": [{"error": str(e)}],
        }


async def draft_order_agent_node(state: ERPAgentState) -> Dict[str, Any]:
    """
    Node xử lý đề xuất đơn hàng nháp (Human-in-The-Loop Draft Proposal).
    Tự động đối chiếu (Entity Resolution) thông minh từ ngôn ngữ tự nhiên:
    - Nhận diện cả Mã khách hàng (CUS-XXXX) lẫn Tên khách hàng (VD: 'Tập đoàn Bán lẻ Toàn Cầu', 'Á Châu')
    - Nhận diện cả Mã SKU (SKU-XXX) lẫn Tên sản phẩm (VD: 'chuột ergonomic', 'laptop pro')
    """
    import re
    from app.db.session import async_session_factory
    from app.document_ai.resolver import EntityResolver
    from app.document_ai.schemas import ExtractedPurchaseOrder, ExtractedOrderItem
    from app.erp.services.customer import CustomerService
    from app.erp.models import Product
    from sqlalchemy import select

    user_role = state.get("user_role")
    user_perms = state.get("user_permissions")
    
    is_denied = False
    if user_role == "warehouse_keeper":
        is_denied = True
    elif user_perms is not None:
        is_denied = "*" not in user_perms and "orders:create" not in user_perms
    elif user_role is not None:
        is_denied = user_role not in ["admin", "sales_manager", "sales_rep"]

    if is_denied:
        err_msg = "⛔ **Truy cập bị từ chối:** Bạn đang đăng nhập với vai trò **Thủ kho** (hoặc chưa được phân quyền `orders:create`). Vai trò này chỉ quản lý tồn kho và xác nhận xuất hàng, không có thẩm quyền khởi tạo đơn hàng nháp. Vui lòng liên hệ Trưởng phòng kinh doanh hoặc Quản trị viên."
        return {
            "answer": err_msg,
            "tool_results": [{
                "success": False,
                "error": "PERMISSION_DENIED",
                "message": err_msg,
            }],
            "proposed_action": None,
        }

    set_current_user_context(UserContext(
        user_id=state.get("user_id"),
        user_role=state.get("user_role"),
        user_name=state.get("user_name"),
        user_email=state.get("user_email"),
        user_permissions=state.get("user_permissions"),
    ))

    entities = state.get("entities") or state.get("extracted_entities")
    raw_customer = None
    raw_items = []
    user_q = state.get("user_query", "")

    if isinstance(entities, ExtractedEntities):
        raw_customer = entities.customer_code or entities.customer_name
        if entities.items:
            for item in entities.items:
                name_or_sku = item.sku or getattr(item, "product_name", None)
                if name_or_sku:
                    raw_items.append({"sku": name_or_sku, "quantity": item.quantity or 1})
        elif (entities.sku or getattr(entities, "product_name", None)) and entities.quantity:
            raw_items.append({
                "sku": entities.sku or getattr(entities, "product_name", None),
                "quantity": entities.quantity,
            })
    elif isinstance(entities, dict):
        raw_customer = entities.get("customer_code") or entities.get("customer_name")
        dict_items = entities.get("items") or []
        if isinstance(dict_items, list) and dict_items:
            for it in dict_items:
                name_or_sku = it.get("sku") or it.get("product_name")
                if name_or_sku:
                    raw_items.append({"sku": name_or_sku, "quantity": it.get("quantity") or 1})
        elif (entities.get("sku") or entities.get("product_name")) and entities.get("quantity"):
            raw_items.append({
                "sku": entities.get("sku") or entities.get("product_name"),
                "quantity": entities.get("quantity") or 1,
            })

    # Regex trích xuất dự phòng nếu LLM chưa bắt được
    if not raw_customer and user_q:
        cus_match = re.search(r"(CUS-\d{4})", user_q, re.IGNORECASE)
        if cus_match:
            raw_customer = cus_match.group(1).upper()
        else:
            m_cus = re.search(r"(?:cho|khách hàng|khách|cty|công ty|tập đoàn)\s+([^,:\n.]+)", user_q, re.IGNORECASE)
            if m_cus:
                raw_customer = m_cus.group(1).strip()

    if not raw_items and user_q:
        item_matches = re.findall(r"(\d+)\s*(?:cái|chiếc|sp|hộp|bộ)?\s*(SKU-\d{3})", user_q, re.IGNORECASE)
        if item_matches:
            raw_items = [{"sku": sku.upper(), "quantity": int(qty)} for qty, sku in item_matches]
        else:
            item_matches2 = re.findall(r"(SKU-\d{3})\s*(?:x|:|,)?\s*(\d+)", user_q, re.IGNORECASE)
            if item_matches2:
                raw_items = [{"sku": sku.upper(), "quantity": int(qty)} for sku, qty in item_matches2]

    # Thực hiện Entity Resolution với cơ sở dữ liệu thực
    resolved_customer_code = None
    resolved_customer_name = None
    resolved_items = []
    tool_results = list(state.get("tool_results", []))

    async with async_session_factory() as session:
        # 1. Khớp nối khách hàng
        if raw_customer:
            clean_cust = str(raw_customer).strip()
            if re.match(r"^CUS-\d{4}$", clean_cust, re.IGNORECASE):
                try:
                    c_obj = await CustomerService.get_by_code(session, clean_cust.upper())
                    resolved_customer_code = c_obj.code
                    resolved_customer_name = c_obj.name
                except Exception:
                    pass

            if not resolved_customer_code:
                c_obj = await EntityResolver.resolve_customer(
                    session,
                    ExtractedPurchaseOrder(customer_name_candidate=clean_cust)
                )
                if c_obj:
                    resolved_customer_code = c_obj.code
                    resolved_customer_name = c_obj.name

        # 2. Khớp nối sản phẩm
        for it in raw_items:
            raw_val = it.get("sku") or ""
            qty = it.get("quantity") or 1
            clean_val = str(raw_val).strip()
            if re.match(r"^SKU-\d{3}$", clean_val, re.IGNORECASE):
                resolved_items.append({"sku": clean_val.upper(), "quantity": qty})
            else:
                res_prod = await EntityResolver.resolve_single_item(
                    session,
                    ExtractedOrderItem(product_name=clean_val, quantity=qty)
                )
                if res_prod:
                    resolved_items.append({"sku": res_prod.sku, "quantity": qty})

        # Nếu danh sách sản phẩm vẫn trống, quét trực tiếp từ text
        if not resolved_items and user_q:
            all_prods = (await session.execute(select(Product).where(Product.is_active == True))).scalars().all()
            for prod in all_prods:
                prod_words = [w for w in prod.name.lower().split() if len(w) > 3]
                if any(w in user_q.lower() for w in prod_words):
                    m_qty = re.search(rf"(\d+)\s*(?:cái|chiếc|sp)?\s*{re.escape(prod_words[0])}", user_q, re.IGNORECASE)
                    found_qty = int(m_qty.group(1)) if m_qty else 1
                    resolved_items.append({"sku": prod.sku, "quantity": found_qty})
                    break

    # Kiểm tra tính đầy đủ sau khi đã giải quyết thực thể
    if not resolved_customer_code or not resolved_items:
        reason_parts = []
        if not resolved_customer_code:
            if raw_customer:
                reason_parts.append(f"Không tìm thấy khách hàng **'{raw_customer}'** trong hệ thống ERP")
            else:
                reason_parts.append("Chưa cung cấp thông tin hoặc tên/mã khách hàng")
        if not resolved_items:
            if raw_items:
                unmatched = ", ".join([str(it.get("sku")) for it in raw_items])
                reason_parts.append(f"Không tìm thấy sản phẩm tương ứng với **'{unmatched}'**")
            else:
                reason_parts.append("Chưa chỉ định sản phẩm và số lượng đặt hàng")

        missing_msg = (
            f"⚠️ **Không thể khởi tạo đơn hàng nháp do:**\n- "
            + "\n- ".join(reason_parts)
            + "\n\n💡 *Gợi ý:* Bạn có thể dùng tên thường (VD: *'lên đơn 2 chuột ergonomic cho tập đoàn bán lẻ toàn cầu'*) hoặc mã định danh (VD: *'CUS-0001', 'SKU-001'*)."
        )
        tool_results.append({
            "success": False,
            "message": missing_msg,
        })
        return {
            "tool_results": tool_results,
            "proposed_action": None,
        }

    try:
        raw_result = await propose_sales_order_draft.ainvoke({
            "customer_code": resolved_customer_code,
            "items": resolved_items,
        })
        draft_data = json.loads(raw_result)
        tool_results.append(draft_data)

        proposed_action = None
        if draft_data.get("success"):
            proposed_action = {
                "action_type": "create_sales_order_draft",
                "status": "draft_proposed",
                "requires_approval": True,
                "draft_payload": draft_data.get("order_draft") or draft_data,
            }

        return {
            "tool_results": tool_results,
            "proposed_action": proposed_action,
        }
    except Exception as e:
        logger.error("Error in draft_order_agent_node: %s", e)
        return {
            "error": str(e),
            "tool_results": tool_results + [{"error": str(e)}],
        }


async def chitchat_agent_node(state: ERPAgentState) -> Dict[str, Any]:
    """Node xử lý chào hỏi xã giao và câu hỏi chung với fallback tự động"""
    query = state.get("user_query", "")
    content = None
    prompt = [
        SystemMessage(content=CHITCHAT_SYSTEM_PROMPT),
        HumanMessage(content=query),
    ]

    # Thử primary model trước
    try:
        llm = _get_llm(model=settings.GEMINI_MODEL, temperature=0.3)
        res = await llm.ainvoke(prompt)
        content = _extract_text(res.content)
    except Exception as e_primary:
        logger.warning("Primary LLM (%s) failed in chitchat: %s. Trying fallback (%s)...", settings.GEMINI_MODEL, e_primary, settings.GEMINI_FALLBACK_MODEL)
        try:
            llm_fallback = _get_llm(model=settings.GEMINI_FALLBACK_MODEL, temperature=0.3)
            res = await llm_fallback.ainvoke(prompt)
            content = _extract_text(res.content)
        except Exception as e_fallback:
            logger.warning("Fallback LLM (%s) also failed in chitchat: %s", settings.GEMINI_FALLBACK_MODEL, e_fallback)
            content = "Xin chào! Tôi là ERP AI Copilot. Tôi có thể hỗ trợ bạn tra cứu tồn kho, doanh thu, khách hàng, hỏi đáp tài liệu chính sách và lên đơn hàng nháp."

    return {
        "answer": content,
        "messages": [AIMessage(content=content)],
    }


async def clarify_agent_node(state: ERPAgentState) -> Dict[str, Any]:
    """Node làm rõ câu hỏi khi ý định chưa xác định được với fallback tự động"""
    query = state.get("user_query", "")
    content = None
    prompt = [
        SystemMessage(content=CLARIFY_SYSTEM_PROMPT),
        HumanMessage(content=query),
    ]

    try:
        llm = _get_llm(model=settings.GEMINI_MODEL, temperature=0.2)
        res = await llm.ainvoke(prompt)
        content = _extract_text(res.content)
    except Exception as e_primary:
        logger.warning("Primary LLM failed in clarify: %s. Trying fallback (%s)...", e_primary, settings.GEMINI_FALLBACK_MODEL)
        try:
            llm_fallback = _get_llm(model=settings.GEMINI_FALLBACK_MODEL, temperature=0.2)
            res = await llm_fallback.ainvoke(prompt)
            content = _extract_text(res.content)
        except Exception as e_fallback:
            logger.warning("Fallback LLM failed in clarify: %s", e_fallback)
            content = (
                "Yêu cầu của bạn chưa đủ rõ ràng hoặc nằm ngoài phạm vi hệ thống. "
                "Bạn có thể yêu cầu tôi: (1) Tra cứu tồn kho SKU hoặc doanh thu; "
                "(2) Hỏi đáp quy định, chính sách công ty; "
                "(3) Tạo đơn hàng nháp cho khách hàng."
            )

    return {
        "answer": content,
        "messages": [AIMessage(content=content)],
    }


async def synthesizer_node(state: ERPAgentState) -> Dict[str, Any]:
    """
    Node tổng hợp câu trả lời cuối cùng từ ngữ cảnh và kết quả công cụ ReAct Super-Agent.
    """
    messages = state.get("messages", [])
    tool_results = state.get("tool_results", [])
    proposed_action = state.get("proposed_action")
    citations = state.get("citations", [])
    user_query = state.get("user_query", "")

    # 1. Nếu Super-Agent ở vòng cuối đã tự sinh câu trả lời đầy đủ (không có tool_calls)
    if messages:
        last_msg = messages[-1]
        if isinstance(last_msg, AIMessage) and last_msg.content and not getattr(last_msg, "tool_calls", None):
            final_ans = _extract_text(last_msg.content)
            if len(final_ans.strip()) > 15:
                return {
                    "answer": final_ans,
                    "citations": citations,
                    "proposed_action": proposed_action,
                }

    # 2. Nếu có proposed_action (đơn hàng nháp)
    if proposed_action:
        payload = proposed_action.get("draft_payload") or proposed_action
        customer_name = payload.get("customer_name", "")
        customer_code = payload.get("customer_code", "")
        total_formatted = payload.get("formatted_total_amount") or payload.get("formatted_total", "")
        items = payload.get("items", [])

        items_table = "\n".join([
            f"- **{it.get('product_name')}** (`{it.get('sku')}`): "
            f"{it.get('quantity')} cái x {it.get('formatted_unit_price') or it.get('formatted_price', '')} = **{it.get('formatted_line_total') or it.get('formatted_subtotal', '')}**"
            for it in items
        ])

        final_ans = (
            f"### 📋 Đề xuất đơn hàng nháp (Chờ phê duyệt)\n\n"
            f"Đã lập bản nháp đề xuất cho khách hàng **{customer_name}** (`{customer_code}`):\n\n"
            f"**Danh sách sản phẩm:**\n{items_table}\n\n"
            f"💵 **Tổng tiền tạm tính:** {total_formatted}\n\n"
            f"> ⚠️ **Lưu ý:** Đơn hàng này đang ở trạng thái **Bản nháp chờ phê duyệt** (Human-in-the-Loop) "
            f"và chưa có hiệu lực cho đến khi người có thẩm quyền bấm xác nhận."
        )
        return {
            "answer": final_ans,
            "messages": [AIMessage(content=final_ans)],
            "citations": citations,
            "proposed_action": proposed_action,
        }

    # 3. Tổng hợp qua LLM Synthesizer
    final_ans = None
    context_summary = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            context_summary.append(f"Tool Result ({msg.name}): {msg.content}")

    if tool_results:
        context_summary.append(f"Structured Tool Results: {json.dumps(tool_results, ensure_ascii=False)}")

    context_text = "\n\n".join(context_summary)

    synthesizer_prompt = [
        SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"Câu hỏi người dùng: {user_query}\n\n"
            f"Dữ liệu công cụ thu thập được:\n{context_text}\n\n"
            f"Hãy tổng hợp thành phản hồi hoàn chỉnh, súc tích và chính xác bằng Tiếng Việt:"
        )),
    ]

    try:
        llm = _get_llm(model=settings.GEMINI_MODEL, temperature=0.0)
        res = await llm.ainvoke(synthesizer_prompt)
        final_ans = _extract_text(res.content)
    except Exception as e_primary:
        logger.warning("Primary LLM (%s) failed in synthesizer: %s", settings.GEMINI_MODEL, e_primary)
        try:
            llm_fallback = _get_llm(model=settings.GEMINI_FALLBACK_MODEL, temperature=0.0)
            res = await llm_fallback.ainvoke(synthesizer_prompt)
            final_ans = _extract_text(res.content)
        except Exception as e_fallback:
            logger.warning("Fallback LLM failed in synthesizer: %s", e_fallback)
            final_ans = "Đã xử lý yêu cầu thành công."

    return {
        "answer": final_ans,
        "messages": [AIMessage(content=final_ans)],
        "citations": citations,
        "proposed_action": proposed_action,
    }


# =========================================================================
# StateGraph Assembly (ReAct Super-Agent)
# =========================================================================

def build_erp_agent_graph(checkpointer: Optional[Any] = None) -> Any:
    """
    Xây dựng LangGraph State Machine ReAct Super-Agent cho ERP AI Copilot.
    START -> classify_intent -> (chitchat_agent -> END) OR (super_agent <-> tools -> synthesizer -> END)
    """
    workflow = StateGraph(ERPAgentState)

    # 1. Thêm các Nodes chính
    workflow.add_node("classify_intent", classify_intent_node)
    workflow.add_node("super_agent", super_agent_node)
    workflow.add_node("tools", super_tools_node)
    workflow.add_node("chitchat_agent", chitchat_agent_node)
    workflow.add_node("synthesizer", synthesizer_node)

    # Thêm các nodes legacy để đảm bảo không lỗi nếu có component gọi
    workflow.add_node("erp_agent", erp_agent_node)
    workflow.add_node("erp_tools", erp_tools_node)
    workflow.add_node("rag_agent", rag_agent_node)
    workflow.add_node("draft_order_agent", draft_order_agent_node)
    workflow.add_node("clarify_agent", clarify_agent_node)

    # 2. Định tuyến START -> classify_intent
    workflow.add_edge(START, "classify_intent")

    # 3. Conditional Edge từ classify_intent sang chitchat hoặc super_agent
    workflow.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "chitchat_agent": "chitchat_agent",
            "super_agent": "super_agent",
            "erp_agent": "super_agent",
            "rag_agent": "super_agent",
            "draft_order_agent": "super_agent",
            "clarify_agent": "super_agent",
        },
    )

    # 4. Conditional Edge từ super_agent: kiểm tra lặp tiếp hay kết thúc
    workflow.add_conditional_edges(
        "super_agent",
        should_continue,
        {
            "tools": "tools",
            "synthesizer": "synthesizer",
        },
    )

    # 5. Tools lặp ngược lại super_agent để LLM đọc quan sát và quyết định bước tiếp theo
    workflow.add_edge("tools", "super_agent")

    # 6. Edges kết thúc
    workflow.add_edge("chitchat_agent", END)
    workflow.add_edge("synthesizer", END)

    # Legacy node fallback edges
    workflow.add_edge("erp_tools", "synthesizer")
    workflow.add_edge("rag_agent", "synthesizer")
    workflow.add_edge("draft_order_agent", "synthesizer")
    workflow.add_edge("clarify_agent", END)

    return workflow.compile(checkpointer=checkpointer)


_agent_graph_instance = None


def get_agent_graph(checkpointer: Optional[Any] = None) -> Any:
    """Singleton getter cho ERP Agent Graph"""
    global _agent_graph_instance
    if _agent_graph_instance is None:
        cp = checkpointer if checkpointer is not None else MemorySaver()
        _agent_graph_instance = build_erp_agent_graph(checkpointer=cp)
    return _agent_graph_instance
