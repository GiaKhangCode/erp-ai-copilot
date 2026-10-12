import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import HumanMessage

from app.core.config import settings
from app.ai.agents.state import ERPAgentState, IntentClassificationResult, ExtractedEntities
from app.ai.agents.router import (
    IntentRouter,
    classify_intent_node,
    route_by_intent,
)


@pytest.fixture
def mock_genai_client():
    client = MagicMock()
    aio_mock = MagicMock()
    models_mock = MagicMock()
    aio_mock.models = models_mock
    client.aio = aio_mock
    return client


def test_erp_agent_state_and_result_schema():
    state: ERPAgentState = {
        "user_id": "usr-123",
        "user_role": "admin",
        "conversation_id": "conv-456",
        "request_id": "req-789",
        "messages": [],
        "user_query": "SKU-001 còn bao nhiêu?",
        "intent": "erp_query",
        "entities": {"sku": "SKU-001"},
        "reasoning": "Tra cứu tồn kho",
        "retrieved_context": [],
        "tool_results": [],
        "proposed_action": None,
        "approval_id": None,
        "answer": "Còn 100 sản phẩm",
        "citations": [],
        "error": None,
    }
    assert state["intent"] == "erp_query"
    assert state["entities"]["sku"] == "SKU-001"

    result = IntentClassificationResult(
        intent="document_qa",
        entities={"document_type": "policy"},
        confidence=0.95,
        reasoning="Hỏi về chính sách đổi trả",
    )
    assert result.intent == "document_qa"
    assert result.confidence == 0.95


@pytest.mark.asyncio
async def test_router_classify_empty_query(mock_genai_client):
    router = IntentRouter(genai_client=mock_genai_client)
    res = await router.classify("   ")

    assert res.intent == "unknown"
    assert res.confidence == 0.0
    mock_genai_client.aio.models.generate_content.assert_not_called()


@pytest.mark.asyncio
async def test_router_sql_injection_guardrail(mock_genai_client):
    router = IntentRouter(genai_client=mock_genai_client)
    res = await router.classify("DROP TABLE products; -- Xóa hết dữ liệu")

    assert res.intent == "unknown"
    assert "cơ sở dữ liệu" in res.reasoning.lower()
    mock_genai_client.aio.models.generate_content.assert_not_called()


@pytest.mark.asyncio
async def test_router_classify_erp_query_with_mock_llm(mock_genai_client):
    response_payload = {
        "intent": "erp_query",
        "entities": {"sku": "SKU-001", "warehouse_code": "WH-HN"},
        "confidence": 0.98,
        "reasoning": "Người dùng hỏi tồn kho SKU-001 tại kho WH-HN",
    }
    mock_response = MagicMock()
    mock_response.text = json.dumps(response_payload)
    mock_genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    router = IntentRouter(genai_client=mock_genai_client)
    res = await router.classify("Kiểm tra tồn kho SKU-001 ở kho Hà Nội WH-HN")

    assert res.intent == "erp_query"
    assert res.entities["sku"] == "SKU-001"
    assert res.entities["warehouse_code"] == "WH-HN"
    assert res.confidence == 0.98
    mock_genai_client.aio.models.generate_content.assert_called_once()


@pytest.mark.asyncio
async def test_router_classify_document_qa_with_mock_llm(mock_genai_client):
    response_payload = {
        "intent": "document_qa",
        "entities": {},
        "confidence": 0.95,
        "reasoning": "Người dùng hỏi về quy định đổi trả hàng",
    }
    mock_response = MagicMock()
    mock_response.text = f"```json\n{json.dumps(response_payload)}\n```"
    mock_genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    router = IntentRouter(genai_client=mock_genai_client)
    res = await router.classify("Quy định đổi trả hàng trong vòng bao nhiêu ngày?")

    assert res.intent == "document_qa"
    assert res.confidence == 0.95


@pytest.mark.asyncio
async def test_router_classify_create_order_draft_with_mock_llm(mock_genai_client):
    response_payload = {
        "intent": "create_order_draft",
        "entities": {
            "customer_code": "CUS-0001",
            "items": [{"sku": "SKU-001", "quantity": 10}],
        },
        "confidence": 0.99,
        "reasoning": "Yêu cầu lên đơn hàng cho khách hàng CUS-0001",
    }
    mock_response = MagicMock()
    mock_response.text = json.dumps(response_payload)
    mock_genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    router = IntentRouter(genai_client=mock_genai_client)
    res = await router.classify("Lên đơn nháp cho khách CUS-0001 mua 10 cái SKU-001")

    assert res.intent == "create_order_draft"
    assert res.entities["customer_code"] == "CUS-0001"
    assert len(res.entities["items"]) == 1


@pytest.mark.asyncio
async def test_router_heuristic_fallback_when_llm_fails(mock_genai_client):
    mock_genai_client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("LLM API Timeout"))

    router = IntentRouter(genai_client=mock_genai_client)

    # 1. Heuristic ERP query
    res_erp = await router.classify("Tồn kho SKU-002 còn bao nhiêu chiếc ở WH-HN?")
    assert res_erp.intent == "erp_query"
    assert res_erp.entities["sku"] == "SKU-002"
    assert res_erp.entities["warehouse_code"] == "WH-HN"

    # 2. Heuristic Document QA
    res_doc = await router.classify("Chính sách công tác phí của công ty?")
    assert res_doc.intent == "document_qa"

    # 3. Heuristic Create Order Draft
    res_draft = await router.classify("Tạo đơn hàng 5 cái SKU-001")
    assert res_draft.intent == "create_order_draft"
    assert res_draft.entities["sku"] == "SKU-001"
    assert res_draft.entities["quantity"] == 5

    # 4. Heuristic Chitchat
    res_chat = await router.classify("Xin chào bạn, bạn là ai?")
    assert res_chat.intent == "chitchat"


@pytest.mark.asyncio
async def test_classify_intent_node_and_route_by_intent(monkeypatch):
    # Mock singleton router
    mock_router = MagicMock()
    mock_result = IntentClassificationResult(
        intent="erp_query",
        entities={"sku": "SKU-001"},
        confidence=0.99,
        reasoning="Tra cứu tồn kho SKU-001",
    )
    mock_router.classify = AsyncMock(return_value=mock_result)
    monkeypatch.setattr("app.ai.agents.router.get_intent_router", lambda: mock_router)

    # Case 1: State with direct user_query
    state1: ERPAgentState = {
        "user_query": "SKU-001 còn bao nhiêu?",
        "messages": [],
    }
    update1 = await classify_intent_node(state1)
    assert update1["intent"] == "erp_query"
    assert update1["entities"]["sku"] == "SKU-001"
    mock_router.classify.assert_called_with("SKU-001 còn bao nhiêu?")

    # Case 2: State with messages only
    state2: ERPAgentState = {
        "user_query": "",
        "messages": [HumanMessage(content="Kiểm tra tồn kho")],
    }
    update2 = await classify_intent_node(state2)
    assert update2["intent"] == "erp_query"
    mock_router.classify.assert_called_with("Kiểm tra tồn kho")

    # Test route_by_intent conditional routing
    assert route_by_intent({"intent": "erp_query"}) == "erp_agent"
    assert route_by_intent({"intent": "document_qa"}) == "rag_agent"
    assert route_by_intent({"intent": "create_order_draft"}) == "draft_order_agent"
    assert route_by_intent({"intent": "chitchat"}) == "chitchat_agent"
    assert route_by_intent({"intent": "unknown"}) == "clarify_agent"
    assert route_by_intent({}) == "clarify_agent"


@pytest.mark.asyncio
async def test_live_intent_router_classification():
    """Live API test against Gemini 3.5 Flash-Lite if API key configured"""
    if not settings.GEMINI_API_KEY:
        pytest.skip("GEMINI_API_KEY is not configured for live router test")

    router = IntentRouter()
    res = await router.classify("Sản phẩm SKU-001 còn tồn kho bao nhiêu cái?")

    assert res.intent == "erp_query"
    assert "sku" in res.entities or "SKU-001" in str(res.entities) or "SKU-001" in res.reasoning
    assert res.confidence > 0.5


@pytest.mark.asyncio
async def test_router_classify_with_parsed_object(mock_genai_client):
    expected_result = IntentClassificationResult(
        intent="erp_query",
        entities=ExtractedEntities(sku="SKU-999", warehouse_code="WH-HCM"),
        confidence=0.99,
        reasoning="Native parsed response test",
    )
    mock_response = MagicMock()
    mock_response.parsed = expected_result
    mock_response.text = None
    mock_genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    router = IntentRouter(genai_client=mock_genai_client)
    res = await router.classify("Tồn kho SKU-999 tại WH-HCM?")

    assert res.intent == "erp_query"
    assert res.entities.sku == "SKU-999"
    assert res.entities["sku"] == "SKU-999"
    assert res.entities.get("warehouse_code") == "WH-HCM"
    assert res.confidence == 0.99

