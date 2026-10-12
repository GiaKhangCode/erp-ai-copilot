import json
import uuid
import pytest

from app.rag.prompts import (
    RAG_SYSTEM_PROMPT,
    format_rag_context,
    build_qa_user_prompt,
    parse_grounded_answer,
)
from app.rag.retrieval import RetrievedChunk
from app.rag.schemas import GroundedAnswer, Citation


def test_system_prompt_security_invariants():
    """Verify system prompt contains all required security, grounding, and citation directives."""
    assert "STRICT GROUNDING" in RAG_SYSTEM_PROMPT
    assert "EXPLICIT ABSTENTION" in RAG_SYSTEM_PROMPT
    assert "ACCURATE CITATIONS" in RAG_SYSTEM_PROMPT
    assert "PROMPT INJECTION" in RAG_SYSTEM_PROMPT
    assert "STRUCTURED JSON OUTPUT" in RAG_SYSTEM_PROMPT
    assert "<context>" in RAG_SYSTEM_PROMPT


def test_format_rag_context_empty():
    """Verify empty chunk list outputs safe message."""
    result = format_rag_context([])
    assert "<context>" in result
    assert "</context>" in result
    assert "Không tìm thấy tài liệu nào phù hợp" in result


def test_format_rag_context_with_chunks():
    """Verify context formatting includes chunk indices, filenames, and contents."""
    chunk1 = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename="chinh_sach_doi_tra.pdf",
        chunk_index=0,
        content="Khách hàng được đổi trả hàng trong vòng 07 ngày kể từ khi nhận hàng.",
        page_number=1,
        access_scope="internal",
        score=0.032,
    )
    chunk2 = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename="chinh_sach_bao_hanh.docx",
        chunk_index=1,
        content="Thời gian bảo hành thiết bị phần cứng là 24 tháng.",
        page_number=None,
        access_scope="public",
        score=0.016,
    )

    context_str = format_rag_context([chunk1, chunk2])
    assert "chinh_sach_doi_tra.pdf" in context_str
    assert "Trang: 1" in context_str
    assert "07 ngày" in context_str
    assert "chinh_sach_bao_hanh.docx" in context_str
    assert "Trang: N/A" in context_str
    assert "24 tháng" in context_str
    assert "<context>" in context_str
    assert "</context>" in context_str


def test_build_qa_user_prompt():
    """Verify user prompt combines query and formatted context."""
    chunk = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename="test.txt",
        chunk_index=0,
        content="Nội dung test.",
        page_number=None,
        access_scope="public",
        score=0.01,
    )
    query = "Quy định đổi trả hàng thế nào?"
    prompt = build_qa_user_prompt(query, [chunk])

    assert query in prompt
    assert "test.txt" in prompt
    assert "<context>" in prompt


def test_parse_grounded_answer_valid_json():
    """Verify parsing valid JSON into GroundedAnswer with full citations."""
    doc_id = str(uuid.uuid4())
    chunk_id = str(uuid.uuid4())
    payload = {
        "answer": "Khách hàng được đổi hàng trong 7 ngày [Nguồn: policy.pdf, Trang: 1, Đoạn: 0].",
        "citations": [
            {
                "document_id": doc_id,
                "filename": "policy.pdf",
                "chunk_id": chunk_id,
                "page_number": 1,
                "chunk_index": 0,
                "quote": "Đổi trả hàng trong vòng 7 ngày.",
            }
        ],
        "has_sufficient_context": True,
        "confidence_score": 0.95,
        "suggested_followups": ["Phí vận chuyển đổi trả ai chịu?"],
    }

    parsed = parse_grounded_answer(json.dumps(payload))
    assert isinstance(parsed, GroundedAnswer)
    assert parsed.has_sufficient_context is True
    assert len(parsed.citations) == 1
    assert parsed.citations[0].filename == "policy.pdf"
    assert parsed.citations[0].quote == "Đổi trả hàng trong vòng 7 ngày."
    assert parsed.confidence_score == 0.95


def test_parse_grounded_answer_markdown_fence():
    """Verify parsing JSON wrapped in markdown code fence."""
    payload = {
        "answer": "Chính sách bảo hành là 24 tháng.",
        "citations": [],
        "has_sufficient_context": True,
        "confidence_score": 0.9,
        "suggested_followups": [],
    }
    raw = f"```json\n{json.dumps(payload)}\n```"

    parsed = parse_grounded_answer(raw)
    assert parsed.answer == "Chính sách bảo hành là 24 tháng."
    assert parsed.has_sufficient_context is True


def test_parse_grounded_answer_abstention_text():
    """Verify parsing plain-text abstention response."""
    raw = "Dựa trên các tài liệu được cung cấp, tôi không tìm thấy thông tin để trả lời."
    parsed = parse_grounded_answer(raw)

    assert parsed.has_sufficient_context is False
    assert parsed.confidence_score == 0.0
    assert parsed.citations == []
    assert "không tìm thấy" in parsed.answer


def test_parse_grounded_answer_fallback():
    """Verify fallback when response is unformatted text."""
    raw = "Đây là câu trả lời text thuần không theo định dạng json."
    parsed = parse_grounded_answer(raw)

    assert parsed.answer == raw
    assert parsed.has_sufficient_context is True
    assert parsed.citations == []
