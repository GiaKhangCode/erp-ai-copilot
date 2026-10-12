import uuid
import pytest
from unittest.mock import MagicMock

from app.rag.retrieval import (
    build_acl_condition,
    reciprocal_rank_fusion,
    RetrievedChunk,
)
from app.rag.models import Document, DocumentChunk


def test_build_acl_condition_admin():
    cond = build_acl_condition(user_id=uuid.uuid4(), user_role="admin")
    assert str(cond) == "1=1"


def test_build_acl_condition_anonymous():
    cond = build_acl_condition(user_id=None, user_role=None)
    # Anonymous users can only access 'public'
    sql_str = str(cond.compile(compile_kwargs={"literal_binds": True}))
    assert "'public'" in sql_str


def test_build_acl_condition_authenticated_sales_rep():
    user_id = uuid.uuid4()
    cond = build_acl_condition(user_id=user_id, user_role="sales_rep")
    sql_str = str(cond.compile(compile_kwargs={"literal_binds": True}))
    assert "'public'" in sql_str
    assert "'internal'" in sql_str
    assert "'role:sales_rep'" in sql_str
    assert str(user_id) in sql_str or user_id.hex in sql_str


def test_reciprocal_rank_fusion_math():
    doc1 = Document(
        id=uuid.uuid4(),
        filename="chinh_sach_1.pdf",
        access_scope="internal",
        status="indexed",
    )
    chunk1 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc1.id,
        chunk_index=0,
        content="Noi dung chunk 1 xuat hien ca o vector va fts",
        metadata_={"page_number": 1},
    )

    doc2 = Document(
        id=uuid.uuid4(),
        filename="chinh_sach_2.pdf",
        access_scope="internal",
        status="indexed",
    )
    chunk2 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc2.id,
        chunk_index=0,
        content="Noi dung chunk 2 chi co o vector",
        metadata_={"page_number": 2},
    )

    doc3 = Document(
        id=uuid.uuid4(),
        filename="chinh_sach_3.pdf",
        access_scope="internal",
        status="indexed",
    )
    chunk3 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc3.id,
        chunk_index=0,
        content="Noi dung chunk 3 chi co o fts",
        metadata_={"page_number": 3},
    )

    # Vector results: chunk1 (rank 1), chunk2 (rank 2)
    vector_results = [
        (chunk1, doc1, 0.95),
        (chunk2, doc2, 0.85),
    ]

    # FTS results: chunk1 (rank 1), chunk3 (rank 2)
    fts_results = [
        (chunk1, doc1, 0.90),
        (chunk3, doc3, 0.70),
    ]

    fused = reciprocal_rank_fusion(
        vector_results=vector_results,
        fts_results=fts_results,
        top_k=2,
        rrf_k=60,
    )

    assert len(fused) == 2
    # chunk1 appeared #1 in both -> must be #1 overall
    assert fused[0].chunk_id == chunk1.id
    assert fused[0].vector_rank == 1
    assert fused[0].fts_rank == 1
    # Score calculation for chunk1: 1/(60+1) + 1/(60+1) = 2/61
    expected_chunk1_score = (1.0 / 61) + (1.0 / 61)
    assert abs(fused[0].score - expected_chunk1_score) < 1e-6

    # chunk2 and chunk3 have score 1/(60+2) = 1/62
    expected_chunk2_score = 1.0 / 62
    assert abs(fused[1].score - expected_chunk2_score) < 1e-6
