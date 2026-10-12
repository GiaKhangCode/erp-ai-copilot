import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

from app.main import app
from app.rag.retrieval import RetrievedChunk
from app.rag.schemas import GroundedAnswer, Citation
from app.rag.qa_service import get_qa_service


@pytest.fixture
def sample_retrieved_chunk():
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename="chinh_sach_doi_tra.pdf",
        chunk_index=0,
        content="Khách hàng được đổi trả trong 07 ngày.",
        page_number=1,
        access_scope="internal",
        score=0.032,
    )


def test_openapi_schema_contains_rag_endpoints():
    """Verify OpenAPI schema registers both /rag/search and /rag/ask endpoints."""
    openapi = app.openapi()
    paths = openapi["paths"]
    assert "/api/v1/rag/search" in paths
    assert "post" in paths["/api/v1/rag/search"]
    assert "/api/v1/rag/ask" in paths
    assert "post" in paths["/api/v1/rag/ask"]


@pytest.mark.asyncio
async def test_rag_search_endpoint(sample_retrieved_chunk):
    """Test POST /api/v1/rag/search returns 200 with chunks list."""
    mock_qa = AsyncMock()
    mock_qa.search.return_value = [sample_retrieved_chunk]

    app.dependency_overrides[get_qa_service] = lambda: mock_qa

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/v1/rag/search",
                json={"query": "chính sách đổi trả", "top_k": 3},
            )

        assert res.status_code == 200
        data = res.json()
        assert data["query"] == "chính sách đổi trả"
        assert data["total_retrieved"] == 1
        assert len(data["chunks"]) == 1
        assert data["chunks"][0]["filename"] == "chinh_sach_doi_tra.pdf"
        assert data["chunks"][0]["page_number"] == 1
    finally:
        app.dependency_overrides.pop(get_qa_service, None)


@pytest.mark.asyncio
async def test_rag_ask_endpoint(sample_retrieved_chunk):
    """Test POST /api/v1/rag/ask returns 200 with GroundedAnswer."""
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    expected_answer = GroundedAnswer(
        answer="Khách hàng được đổi hàng trong 7 ngày [Nguồn: policy.pdf, Trang: 1, Đoạn: 0].",
        citations=[
            Citation(
                document_id=doc_id,
                filename="policy.pdf",
                chunk_id=chunk_id,
                page_number=1,
                chunk_index=0,
                quote="Đổi hàng trong 7 ngày.",
            )
        ],
        has_sufficient_context=True,
        confidence_score=0.95,
        suggested_followups=["Điều kiện đổi hàng là gì?"],
    )

    mock_qa = AsyncMock()
    mock_qa.ask.return_value = expected_answer

    app.dependency_overrides[get_qa_service] = lambda: mock_qa

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/v1/rag/ask",
                json={"query": "Quy định đổi hàng?", "top_k": 5},
            )

        assert res.status_code == 200
        data = res.json()
        assert data["has_sufficient_context"] is True
        assert len(data["citations"]) == 1
        assert data["citations"][0]["filename"] == "policy.pdf"
        assert data["citations"][0]["quote"] == "Đổi hàng trong 7 ngày."
        assert len(data["suggested_followups"]) == 1
    finally:
        app.dependency_overrides.pop(get_qa_service, None)
