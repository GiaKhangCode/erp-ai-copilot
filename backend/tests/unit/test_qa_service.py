import json
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.rag.qa_service import QAService, get_qa_service
from app.rag.retrieval import RetrievedChunk
from app.rag.schemas import GroundedAnswer, Citation


@pytest.fixture
def mock_retriever():
    retriever = MagicMock()
    retriever.retrieve = AsyncMock()
    return retriever


@pytest.fixture
def mock_genai_client():
    client = MagicMock()
    # Mock client.aio.models.generate_content
    aio_mock = MagicMock()
    models_mock = MagicMock()
    aio_mock.models = models_mock
    client.aio = aio_mock
    return client


@pytest.mark.asyncio
async def test_qa_service_empty_query(mock_retriever, mock_genai_client):
    service = QAService(retriever=mock_retriever, genai_client=mock_genai_client)
    res = await service.ask(session=MagicMock(), query="   ")

    assert res.has_sufficient_context is False
    assert "cung cấp câu hỏi" in res.answer
    mock_retriever.retrieve.assert_not_called()
    mock_genai_client.aio.models.generate_content.assert_not_called()


@pytest.mark.asyncio
async def test_qa_service_short_circuit_abstention(mock_retriever, mock_genai_client):
    mock_retriever.retrieve.return_value = []
    service = QAService(retriever=mock_retriever, genai_client=mock_genai_client)

    res = await service.ask(
        session=MagicMock(),
        query="Chính sách lương thưởng là gì?",
        user_id=uuid.uuid4(),
        user_role="sales_rep",
    )

    assert res.has_sufficient_context is False
    assert res.confidence_score == 0.0
    assert len(res.citations) == 0
    assert "không tìm thấy thông tin" in res.answer
    # LLM should never be called when context is empty
    mock_genai_client.aio.models.generate_content.assert_not_called()


@pytest.mark.asyncio
async def test_qa_service_ask_success_with_mock_llm(mock_retriever, mock_genai_client):
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    retrieved_chunk = RetrievedChunk(
        chunk_id=chunk_id,
        document_id=doc_id,
        filename="chinh_sach_doi_tra.pdf",
        chunk_index=0,
        content="Khách hàng được đổi trả hàng trong vòng 07 ngày kể từ ngày nhận hàng.",
        page_number=1,
        access_scope="internal",
        score=0.033,
    )
    mock_retriever.retrieve.return_value = [retrieved_chunk]

    llm_payload = {
        "answer": "Theo chính sách, khách hàng được đổi trả trong 07 ngày [Nguồn: chinh_sach_doi_tra.pdf, Trang: 1, Đoạn: 0].",
        "citations": [
            {
                "document_id": str(doc_id),
                "filename": "chinh_sach_doi_tra.pdf",
                "chunk_id": str(chunk_id),
                "page_number": 1,
                "chunk_index": 0,
                "quote": "Khách hàng được đổi trả hàng trong vòng 07 ngày.",
            }
        ],
        "has_sufficient_context": True,
        "confidence_score": 0.98,
        "suggested_followups": ["Điều kiện đổi trả là gì?"],
    }

    mock_response = MagicMock()
    mock_response.text = json.dumps(llm_payload)
    mock_genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    service = QAService(retriever=mock_retriever, genai_client=mock_genai_client)
    res = await service.ask(session=MagicMock(), query="Quy định đổi trả?")

    assert res.has_sufficient_context is True
    assert len(res.citations) == 1
    assert res.citations[0].filename == "chinh_sach_doi_tra.pdf"
    assert res.citations[0].chunk_id == chunk_id
    assert res.citations[0].page_number == 1
    assert "07 ngày" in res.answer


@pytest.mark.asyncio
async def test_qa_service_citation_validation_filters_hallucinated_citation(mock_retriever, mock_genai_client):
    real_chunk_id = uuid.uuid4()
    fake_chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    retrieved_chunk = RetrievedChunk(
        chunk_id=real_chunk_id,
        document_id=doc_id,
        filename="chinh_sach_bao_hanh.docx",
        chunk_index=0,
        content="Bảo hành phần cứng 24 tháng.",
        page_number=None,
        access_scope="public",
        score=0.02,
    )
    mock_retriever.retrieve.return_value = [retrieved_chunk]

    # LLM hallucinates a second citation that never existed
    llm_payload = {
        "answer": "Bảo hành 24 tháng.",
        "citations": [
            {
                "document_id": str(doc_id),
                "filename": "chinh_sach_bao_hanh.docx",
                "chunk_id": str(real_chunk_id),
                "page_number": None,
                "chunk_index": 0,
                "quote": "Bảo hành phần cứng 24 tháng.",
            },
            {
                "document_id": str(uuid.uuid4()),
                "filename": "tai_lieu_gia_mao.pdf",
                "chunk_id": str(fake_chunk_id),
                "page_number": 99,
                "chunk_index": 99,
                "quote": "Thông tin không có trong context.",
            },
        ],
        "has_sufficient_context": True,
        "confidence_score": 0.9,
        "suggested_followups": [],
    }

    mock_response = MagicMock()
    mock_response.text = json.dumps(llm_payload)
    mock_genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    service = QAService(retriever=mock_retriever, genai_client=mock_genai_client)
    res = await service.ask(session=MagicMock(), query="Bảo hành mấy tháng?")

    # The fake citation must be eliminated
    assert len(res.citations) == 1
    assert res.citations[0].chunk_id == real_chunk_id
    assert res.citations[0].filename == "chinh_sach_bao_hanh.docx"


@pytest.mark.asyncio
async def test_qa_service_retry_and_degraded_fallback(mock_retriever, mock_genai_client):
    retrieved_chunk = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename="test.txt",
        chunk_index=0,
        content="Test content.",
        page_number=None,
        access_scope="public",
        score=0.01,
    )
    mock_retriever.retrieve.return_value = [retrieved_chunk]

    # LLM call throws error continuously
    mock_genai_client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("API quota exceeded"))

    service = QAService(retriever=mock_retriever, genai_client=mock_genai_client)
    res = await service.ask(session=MagicMock(), query="Test query", max_retries=2)

    assert res.has_sufficient_context is False
    assert "bận hoặc gặp sự cố" in res.answer
    assert res.confidence_score == 0.0


def test_qa_service_singleton_factory():
    s1 = get_qa_service()
    s2 = get_qa_service()
    assert s1 is s2
