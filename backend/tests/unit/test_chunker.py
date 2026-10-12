import uuid
import pytest

from app.rag.parser import ParsedDocument, DocumentSection
from app.rag.chunker import (
    chunk_document,
    _split_text_recursive,
    _split_markdown_table,
    DEFAULT_CHUNK_SIZE,
)


def test_split_text_recursive_small():
    short_text = "Chinh sach ban hang ap dung cho tat ca cac dai ly toan quoc."
    chunks = _split_text_recursive(short_text, max_size=200, overlap=30)
    assert len(chunks) == 1
    assert chunks[0] == short_text


def test_split_text_recursive_large_with_overlap():
    # Construct paragraph of ~400 characters
    sentences = [
        f"Dieu {i}: Khach hang mua tren {i * 10} trieu dong se duoc giam gia {i} phan tram theo chinh sach."
        for i in range(1, 10)
    ]
    full_text = "\n\n".join(sentences)

    chunks = _split_text_recursive(full_text, max_size=250, overlap=50)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 250

    # Verify overlap exists between consecutive chunks
    # (some words from end of chunk 0 should be present in chunk 1)
    overlap_found = False
    words_chunk_0 = set(chunks[0].split()[-5:])
    words_chunk_1 = set(chunks[1].split()[:8])
    if words_chunk_0.intersection(words_chunk_1):
        overlap_found = True
    assert overlap_found is True


def test_split_markdown_table_preserves_header():
    header = "| Ma SKU | Ten san pham | Don gia |\n|---|---|---|"
    rows = [f"| SKU-00{i} | San pham demo loai so {i} | {i * 100000} VND |" for i in range(1, 15)]
    table_text = header + "\n" + "\n".join(rows)

    # Force small max_size to trigger table splitting
    chunks = _split_markdown_table(table_text, max_size=220)
    assert len(chunks) > 1

    # Every chunk must begin with the Markdown table header
    for chunk in chunks:
        assert chunk.startswith(header)
        assert len(chunk) <= 260  # Allow slight room for atomic rows


def test_chunk_document_metadata_and_acl():
    doc_id = uuid.uuid4()
    checksum = "abc123sha256hash"
    access_scope = "role:sales_manager"

    parsed_doc = ParsedDocument(
        filename="chinh_sach_kinh_doanh_2026.pdf",
        mime_type="application/pdf",
        total_pages=2,
        sections=[
            DocumentSection(
                text="Trang 1: Tong quan ve chinh sach kinh doanh ERP 2026.",
                page_number=1,
                section_type="text",
            ),
            DocumentSection(
                text="| Ma SKU | Chiet khau |\n|---|---|\n| SKU-001 | 10% |\n| SKU-002 | 15% |",
                page_number=2,
                section_type="table",
            ),
        ],
    )

    chunks = chunk_document(
        parsed_doc=parsed_doc,
        document_id=doc_id,
        access_scope=access_scope,
        checksum=checksum,
        chunk_size=1000,
        chunk_overlap=100,
    )

    assert len(chunks) == 2

    # Chunk 0 (Text from Page 1)
    c0 = chunks[0]
    assert c0.chunk_index == 0
    assert c0.page_number == 1
    assert c0.section_type == "text"
    assert c0.metadata["document_id"] == str(doc_id)
    assert c0.metadata["filename"] == "chinh_sach_kinh_doanh_2026.pdf"
    assert c0.metadata["access_scope"] == access_scope
    assert c0.metadata["checksum"] == checksum
    assert c0.metadata["page_number"] == 1
    assert c0.metadata["token_count_approx"] > 0

    # Chunk 1 (Table from Page 2)
    c1 = chunks[1]
    assert c1.chunk_index == 1
    assert c1.page_number == 2
    assert c1.section_type == "table"
    assert "| SKU-001 | 10% |" in c1.content
    assert c1.metadata["access_scope"] == access_scope
    assert c1.metadata["page_number"] == 2


def test_chunk_document_empty():
    parsed_doc = ParsedDocument(
        filename="empty.txt",
        mime_type="text/plain",
        total_pages=1,
        sections=[],
    )
    chunks = chunk_document(parsed_doc)
    assert chunks == []
