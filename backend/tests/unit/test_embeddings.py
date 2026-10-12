import pytest

from app.rag.embeddings import GeminiEmbeddingService, get_embedding_service
from app.rag.chunker import ChunkPayload


def test_embedding_factory_resolves():
    service = get_embedding_service()
    assert isinstance(service, GeminiEmbeddingService)
    assert service.dimension == 1536
    assert service.model == "gemini-embedding-2"


def test_embed_empty_query_raises():
    service = get_embedding_service()
    with pytest.raises(ValueError, match="empty"):
        service.embed_query("   ")


@pytest.mark.skipif(
    not get_embedding_service().api_key,
    reason="GEMINI_API_KEY not configured",
)
def test_embed_query_live():
    service = get_embedding_service()
    query = "Chính sách bảo hành thiết bị văn phòng ERP"
    vector = service.embed_query(query)

    assert isinstance(vector, list)
    assert len(vector) == 1536
    assert any(v != 0.0 for v in vector)
    assert all(isinstance(v, float) for v in vector)


@pytest.mark.skipif(
    not get_embedding_service().api_key,
    reason="GEMINI_API_KEY not configured",
)
def test_embed_documents_batch_live():
    service = get_embedding_service()
    texts = [
        "Điều 1: Đơn hàng giao trong ngày cho khu vực nội thành Hà Nội.",
        "Điều 2: Đơn hàng ngoại tỉnh chuyển phát nhanh trong 48 giờ.",
        "Điều 3: Miễn phí vận chuyển cho đơn hàng trên 5.000.000 VNĐ.",
    ]
    # Test batching with batch_size=2 to test pagination loop
    vectors = service.embed_documents(texts, batch_size=2)

    assert len(vectors) == 3
    for vec in vectors:
        assert len(vec) == 1536
        assert any(v != 0.0 for v in vec)


@pytest.mark.skipif(
    not get_embedding_service().api_key,
    reason="GEMINI_API_KEY not configured",
)
def test_embed_chunks_live():
    service = get_embedding_service()
    chunks = [
        ChunkPayload(
            chunk_index=0,
            content="Quy định đổi trả hàng hoá trong vòng 7 ngày.",
            page_number=1,
            section_type="text",
        ),
        ChunkPayload(
            chunk_index=1,
            content="| Mã SKU | Đơn giá |\n|---|---|\n| SKU-001 | 1.000.000 |",
            page_number=1,
            section_type="table",
        ),
    ]
    vectors = service.embed_chunks(chunks)
    assert len(vectors) == 2
    assert len(vectors[0]) == 1536
    assert len(vectors[1]) == 1536
