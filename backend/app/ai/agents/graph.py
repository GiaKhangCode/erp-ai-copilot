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
from app.ai.tools.erp_tools import (
    get_inventory,
    get_product,
    get_customer,
    get_sales_orders,
    get_revenue_report,
    propose_sales_order_draft,
)
from app.ai.tools.rag_tool import search_company_knowledge
from app.ai.prompts.agent_prompts import (
    ERP_AGENT_SYSTEM_PROMPT,
    CHITCHAT_SYSTEM_PROMPT,
    CLARIFY_SYSTEM_PROMPT,
    SYNTHESIZER_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

# Danh sách read-only ERP Domain tools
ERP_READ_TOOLS = [
    get_inventory,
    get_product,
    get_customer,
    get_sales_orders,
    get_revenue_report,
]


def _get_llm(temperature: float = 0.0) -> ChatGoogleGenerativeAI:
    """Khởi tạo ChatGoogleGenerativeAI với mô hình cấu hình trong settings và retry tự động"""
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=temperature,
        max_retries=3,
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
# LangGraph Node Handlers
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
    Node thực thi ToolNode cho các công cụ ERP với bảo mật context tự động nạp từ state.
    """
    set_current_user_context(UserContext(
        user_id=state.get("user_id"),
        user_role=state.get("user_role"),
    ))
    tool_node = ToolNode(ERP_READ_TOOLS)
    return await tool_node.ainvoke(state)



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
    """
    set_current_user_context(UserContext(
        user_id=state.get("user_id"),
        user_role=state.get("user_role"),
    ))

    entities = state.get("entities")
    customer_code = None
    items = None

    if isinstance(entities, ExtractedEntities):
        customer_code = entities.customer_code
        if entities.items:
            items = [{"sku": item.sku, "quantity": item.quantity} for item in entities.items]
        elif entities.sku and entities.quantity:
            items = [{"sku": entities.sku, "quantity": entities.quantity}]
    elif isinstance(entities, dict):
        customer_code = entities.get("customer_code")
        items = entities.get("items")
        if not items and entities.get("sku") and entities.get("quantity"):
            items = [{"sku": entities.get("sku"), "quantity": entities.get("quantity")}]

    tool_results = list(state.get("tool_results", []))

    if not customer_code or not items:
        missing_payload = {
            "success": False,
            "message": "Để tạo đơn hàng nháp, vui lòng cung cấp mã khách hàng (VD: CUS-0001) và danh sách mặt hàng kèm số lượng (VD: 10 cái SKU-001).",
        }
        tool_results.append(missing_payload)
        return {
            "tool_results": tool_results,
            "proposed_action": None,
        }

    try:
        raw_result = await propose_sales_order_draft.ainvoke({
            "customer_code": customer_code,
            "items": items,
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
    """Node xử lý chào hỏi xã giao và câu hỏi chung"""
    query = state.get("user_query", "")
    try:
        llm = _get_llm(temperature=0.3)
        prompt = [
            SystemMessage(content=CHITCHAT_SYSTEM_PROMPT),
            HumanMessage(content=query),
        ]
        res = await llm.ainvoke(prompt)
        content = _extract_text(res.content)
    except Exception as e:
        logger.warning("Chitchat LLM failed, using fallback: %s", e)
        content = "Xin chào! Tôi là ERP AI Copilot. Tôi có thể hỗ trợ bạn tra cứu tồn kho, khách hàng, đơn hàng, hỏi đáp tài liệu chính sách và lên đơn hàng nháp."

    return {
        "answer": content,
        "messages": [AIMessage(content=content)],
    }


async def clarify_agent_node(state: ERPAgentState) -> Dict[str, Any]:
    """Node làm rõ câu hỏi khi ý định chưa xác định được"""
    query = state.get("user_query", "")
    try:
        llm = _get_llm(temperature=0.2)
        prompt = [
            SystemMessage(content=CLARIFY_SYSTEM_PROMPT),
            HumanMessage(content=query),
        ]
        res = await llm.ainvoke(prompt)
        content = _extract_text(res.content)
    except Exception as e:
        logger.warning("Clarify LLM failed, using fallback: %s", e)
        content = (
            "Yêu cầu của bạn chưa đủ rõ ràng hoặc nằm ngoài phạm vi hệ thống. "
            "Bạn có thể yêu cầu tôi: (1) Tra cứu tồn kho SKU hoặc khách hàng; "
            "(2) Hỏi đáp quy định, chính sách công ty; "
            "(3) Tạo đơn hàng nháp cho khách hàng."
        )

    return {
        "answer": content,
        "messages": [AIMessage(content=content)],
    }


async def synthesizer_node(state: ERPAgentState) -> Dict[str, Any]:
    """
    Node tổng hợp câu trả lời cuối cùng từ ngữ cảnh và kết quả công cụ.
    """
    intent = state.get("intent", "unknown")
    tool_results = state.get("tool_results", [])
    proposed_action = state.get("proposed_action")
    retrieved_context = state.get("retrieved_context", [])
    citations = state.get("citations", [])
    user_query = state.get("user_query", "")

    # Nếu là RAG và đã có sẵn câu trả lời grounded từ RAG service
    if intent == "document_qa" and retrieved_context:
        first_ctx = retrieved_context[0]
        if isinstance(first_ctx, dict) and "answer" in first_ctx:
            final_ans = first_ctx["answer"]
            return {
                "answer": final_ans,
                "messages": [AIMessage(content=final_ans)],
            }

    # Nếu là đề xuất đơn hàng nháp
    if intent == "create_order_draft":
        if proposed_action and proposed_action.get("draft_payload"):
            payload = proposed_action["draft_payload"]
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
            }
        elif tool_results and not tool_results[-1].get("success", True):
            fail_msg = tool_results[-1].get("message", "Không thể tạo đơn hàng nháp.")
            return {
                "answer": fail_msg,
                "messages": [AIMessage(content=fail_msg)],
            }

    # Tổng hợp qua LLM Synthesizer
    final_ans = None
    for attempt in range(1, 3):
        try:
            llm = _get_llm(temperature=0.0)

            context_summary = []
            # Lấy kết quả từ ToolMessages trong history
            for msg in state.get("messages", []):
                if isinstance(msg, ToolMessage):
                    context_summary.append(f"Tool Result ({msg.name}): {msg.content}")

            if tool_results:
                context_summary.append(f"Structured Tool Results: {json.dumps(tool_results, ensure_ascii=False)}")

            context_text = "\n\n".join(context_summary)

            synthesizer_prompt = [
                SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT),
                HumanMessage(content=(
                    f"Câu hỏi người dùng: {user_query}\n\n"
                    f"Ý định: {intent}\n\n"
                    f"Dữ liệu công cụ thu thập được:\n{context_text}\n\n"
                    f"Hãy tổng hợp thành phản hồi hoàn chỉnh, súc tích và chính xác bằng Tiếng Việt:"
                )),
            ]

            res = await llm.ainvoke(synthesizer_prompt)
            final_ans = _extract_text(res.content)
            break
        except Exception as e:
            if ("429" in str(e) or "ResourceExhausted" in str(e)) and attempt == 1:
                logger.warning("Gemini 429 rate limit hit in synthesizer_node. Backing off 5s...")
                await asyncio.sleep(5)
                continue
            logger.warning("LLM Synthesizer failed, using fallback summary: %s", e)
            # Fallback formatting từ ToolMessage cuối cùng
            last_tool_content = None
            for msg in reversed(state.get("messages", [])):
                if isinstance(msg, ToolMessage):
                    last_tool_content = msg.content
                    break

            if last_tool_content:
                final_ans = f"Kết quả từ hệ thống ERP:\n\n{last_tool_content}"
            else:
                final_ans = "Đã xử lý yêu cầu thành công."
            break

    return {
        "answer": final_ans,
        "messages": [AIMessage(content=final_ans)],
    }


# =========================================================================
# StateGraph Assembly
# =========================================================================

def build_erp_agent_graph(checkpointer: Optional[Any] = None) -> Any:
    """
    Xây dựng LangGraph State Machine cho ERP AI Copilot theo Blueprint Section 6.2.
    """
    workflow = StateGraph(ERPAgentState)

    # 1. Thêm các Nodes
    workflow.add_node("classify_intent", classify_intent_node)
    workflow.add_node("erp_agent", erp_agent_node)
    workflow.add_node("erp_tools", erp_tools_node)
    workflow.add_node("rag_agent", rag_agent_node)
    workflow.add_node("draft_order_agent", draft_order_agent_node)
    workflow.add_node("chitchat_agent", chitchat_agent_node)
    workflow.add_node("clarify_agent", clarify_agent_node)
    workflow.add_node("synthesizer", synthesizer_node)

    # 2. Định tuyến START -> classify_intent
    workflow.add_edge(START, "classify_intent")

    # 3. Conditional Edge từ classify_intent sang các branch agents
    workflow.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "erp_agent": "erp_agent",
            "rag_agent": "rag_agent",
            "draft_order_agent": "draft_order_agent",
            "chitchat_agent": "chitchat_agent",
            "clarify_agent": "clarify_agent",
        },
    )

    # 4. Conditional Edge từ erp_agent sang erp_tools hoặc synthesizer
    workflow.add_conditional_edges(
        "erp_agent",
        should_call_erp_tools,
        {
            "erp_tools": "erp_tools",
            "synthesizer": "synthesizer",
        },
    )

    # 5. Edges chuyển tiếp về synthesizer
    workflow.add_edge("erp_tools", "synthesizer")
    workflow.add_edge("rag_agent", "synthesizer")
    workflow.add_edge("draft_order_agent", "synthesizer")

    # 6. Edges kết thúc
    workflow.add_edge("chitchat_agent", END)
    workflow.add_edge("clarify_agent", END)
    workflow.add_edge("synthesizer", END)

    # Compile graph với checkpointer nếu có (MemorySaver cho hội thoại đa vòng)
    return workflow.compile(checkpointer=checkpointer)


_agent_graph_instance = None


def get_agent_graph(checkpointer: Optional[Any] = None) -> Any:
    """Singleton getter cho ERP Agent Graph"""
    global _agent_graph_instance
    if _agent_graph_instance is None:
        cp = checkpointer if checkpointer is not None else MemorySaver()
        _agent_graph_instance = build_erp_agent_graph(checkpointer=cp)
    return _agent_graph_instance
