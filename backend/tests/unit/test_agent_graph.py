import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver

from app.core.config import settings
from app.ai.agents.state import ERPAgentState, ExtractedEntities, OrderItemDraft
from app.ai.agents.graph import (
    build_erp_agent_graph,
    get_agent_graph,
    erp_agent_node,
    rag_agent_node,
    draft_order_agent_node,
    chitchat_agent_node,
    clarify_agent_node,
    synthesizer_node,
    should_call_erp_tools,
)


def test_build_erp_agent_graph_compilation():
    """Kiểm tra StateGraph biên dịch thành công và chứa đầy đủ các nodes"""
    graph = build_erp_agent_graph(checkpointer=MemorySaver())
    assert graph is not None

    # Kiểm tra nodes trong graph
    nodes = list(graph.nodes.keys())
    assert "classify_intent" in nodes
    assert "erp_agent" in nodes
    assert "erp_tools" in nodes
    assert "rag_agent" in nodes
    assert "draft_order_agent" in nodes
    assert "chitchat_agent" in nodes
    assert "clarify_agent" in nodes
    assert "synthesizer" in nodes


@pytest.mark.asyncio
async def test_chitchat_agent_node_fallback():
    """Kiểm tra chitchat node xử lý phản hồi lịch sự"""
    state: ERPAgentState = {
        "user_query": "Xin chào bạn là ai?",
        "intent": "chitchat",
        "messages": [],
    }
    result = await chitchat_agent_node(state)
    assert "answer" in result
    assert len(result["messages"]) == 1
    assert "ERP AI Copilot" in result["answer"] or "trợ lý" in result["answer"].lower()


@pytest.mark.asyncio
async def test_clarify_agent_node_fallback():
    """Kiểm tra clarify node hướng dẫn người dùng làm rõ ý định"""
    state: ERPAgentState = {
        "user_query": "blablabla 123",
        "intent": "unknown",
        "messages": [],
    }
    result = await clarify_agent_node(state)
    assert "answer" in result
    assert "erp ai copilot" in result["answer"].lower() or "rõ" in result["answer"].lower() or "phạm vi" in result["answer"].lower()


@pytest.mark.asyncio
async def test_draft_order_agent_missing_entities():
    """Kiểm tra draft order node khi thiếu thông tin khách hoặc sản phẩm"""
    state: ERPAgentState = {
        "user_query": "Lên đơn giúp tôi",
        "intent": "create_order_draft",
        "entities": ExtractedEntities(),
        "tool_results": [],
    }
    result = await draft_order_agent_node(state)
    assert result["proposed_action"] is None
    assert len(result["tool_results"]) == 1
    assert "mã khách hàng" in result["tool_results"][0]["message"]


@pytest.mark.asyncio
async def test_draft_order_agent_success():
    """Kiểm tra draft order node khi trích xuất đầy đủ thực thể và đề xuất draft"""
    mock_draft_response = {
        "success": True,
        "message": "Đã tạo đề xuất đơn hàng nháp thành công.",
        "order_draft": {
            "customer_code": "CUS-0001",
            "customer_name": "Công ty TNHH Minh Long",
            "total_amount": 25000000.0,
            "formatted_total": "25,000,000 VND",
            "items": [
                {
                    "sku": "SKU-001",
                    "product_name": "Laptop Dell Pro",
                    "quantity": 1,
                    "unit_price": 25000000.0,
                    "formatted_price": "25,000,000 VND",
                    "subtotal": 25000000.0,
                    "formatted_subtotal": "25,000,000 VND",
                }
            ],
        },
    }

    mock_tool = MagicMock()
    mock_tool.ainvoke = AsyncMock(return_value=json.dumps(mock_draft_response, ensure_ascii=False))

    with patch("app.ai.agents.graph.propose_sales_order_draft", mock_tool):
        state: ERPAgentState = {
            "user_query": "Lên đơn cho khách CUS-0001 mua 1 cái SKU-001",
            "intent": "create_order_draft",
            "entities": ExtractedEntities(
                customer_code="CUS-0001",
                sku="SKU-001",
                quantity=1,
            ),
            "tool_results": [],
        }

        result = await draft_order_agent_node(state)

        assert result["proposed_action"] is not None
        assert result["proposed_action"]["action_type"] == "create_sales_order_draft"
        assert result["proposed_action"]["status"] == "draft_proposed"
        assert result["proposed_action"]["requires_approval"] is True

        # Kiểm tra synthesizer format đề xuất đơn hàng
        synth_state: ERPAgentState = {
            **state,
            **result,
        }
        synth_result = await synthesizer_node(synth_state)
        assert "Chờ phê duyệt" in synth_result["answer"]
        assert "25,000,000 VND" in synth_result["answer"]
        assert "Minh Long" in synth_result["answer"]


@pytest.mark.asyncio
async def test_rag_agent_flow():
    """Kiểm tra RAG agent node và synthesizer chuyển giao citations"""
    mock_rag_response = {
        "has_sufficient_context": True,
        "answer": "Theo chính sách, khách hàng được đổi trả hàng trong vòng 07 ngày.",
        "citations": [
            {
                "filename": "chinh_sach_doi_tra.md",
                "page_number": 1,
                "quote": "Khách hàng được quyền đổi trả hàng trong vòng 07 ngày",
            }
        ],
    }

    mock_tool = MagicMock()
    mock_tool.ainvoke = AsyncMock(return_value=json.dumps(mock_rag_response, ensure_ascii=False))

    with patch("app.ai.agents.graph.search_company_knowledge", mock_tool):
        state: ERPAgentState = {
            "user_query": "Quy định đổi trả hàng thế nào?",
            "intent": "document_qa",
            "user_role": "sales_rep",
        }

        rag_result = await rag_agent_node(state)
        assert len(rag_result["citations"]) == 1
        assert rag_result["citations"][0]["filename"] == "chinh_sach_doi_tra.md"

        synth_state: ERPAgentState = {
            **state,
            **rag_result,
        }
        synth_result = await synthesizer_node(synth_state)
        assert "07 ngày" in synth_result["answer"]


def test_should_call_erp_tools_logic():
    """Kiểm tra điều kiện rẽ nhánh conditional edge của erp_agent"""
    # 1. Message có tool_calls -> gọi erp_tools
    ai_msg_with_tools = AIMessage(
        content="",
        tool_calls=[{"name": "get_inventory", "args": {"sku": "SKU-001"}, "id": "call_1"}],
    )
    assert should_call_erp_tools({"messages": [ai_msg_with_tools]}) == "erp_tools"

    # 2. Message không có tool_calls -> đi thẳng synthesizer
    ai_msg_text = AIMessage(content="Tồn kho còn 10 cái")
    assert should_call_erp_tools({"messages": [ai_msg_text]}) == "synthesizer"

    # 3. Trạng thái rỗng -> synthesizer
    assert should_call_erp_tools({"messages": []}) == "synthesizer"


@pytest.mark.asyncio
async def test_full_graph_chitchat_end_to_end():
    """Kiểm tra StateGraph thực thi hoàn chỉnh từ START đến END qua MemorySaver"""
    memory = MemorySaver()
    graph = build_erp_agent_graph(checkpointer=memory)

    config = {"configurable": {"thread_id": "test-session-001"}}

    # Truy vấn chitchat đơn giản
    initial_state = {
        "messages": [HumanMessage(content="Xin chào")],
        "user_query": "Xin chào",
    }

    final_state = await graph.ainvoke(initial_state, config=config)

    assert "answer" in final_state
    assert len(final_state["messages"]) >= 2
    assert final_state["intent"] == "chitchat"
