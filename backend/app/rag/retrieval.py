import logging
import uuid
from typing import Dict, List, Optional, Tuple, Any

from pydantic import BaseModel, Field
from sqlalchemy import desc, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.models import Document, DocumentChunk
from app.rag.embeddings import GeminiEmbeddingService, get_embedding_service

logger = logging.getLogger(__name__)


class RetrievedChunk(BaseModel):
    """Represents a chunk retrieved through Hybrid Search with ACL validation."""
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    chunk_index: int
    content: str
    page_number: Optional[int] = None
    access_scope: str
    score: float
    vector_rank: Optional[int] = None
    fts_rank: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


def build_acl_condition(
    user_id: Optional[uuid.UUID] = None,
    user_role: Optional[str] = None,
):
    """
    Constructs an authorization filter condition for database queries.
    Rules:
    - role='admin': Access all documents
    - Authenticated users: 'public', 'internal', 'role:<user_role>', and own documents
    - Anonymous users: 'public' only
    """
    if user_role == "admin":
        return text("1=1")

    allowed_scopes = ["public"]

    if user_id:
        allowed_scopes.append("internal")
        if user_role:
            allowed_scopes.append(f"role:{user_role}")
        return or_(
            Document.access_scope.in_(allowed_scopes),
            Document.owner_id == user_id,
        )

    return Document.access_scope == "public"


async def search_vector_similarity(
    session: AsyncSession,
    query_vector: List[float],
    top_k: int = 10,
    user_id: Optional[uuid.UUID] = None,
    user_role: Optional[str] = None,
) -> List[Tuple[DocumentChunk, Document, float]]:
    """
    Dense vector search using pgvector cosine distance.
    Returns (DocumentChunk, Document, cosine_similarity).
    """
    cosine_dist = DocumentChunk.embedding.cosine_distance(query_vector)
    acl_cond = build_acl_condition(user_id=user_id, user_role=user_role)

    stmt = (
        select(
            DocumentChunk,
            Document,
            (1 - cosine_dist).label("similarity"),
        )
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(Document.status == "indexed")
        .where(acl_cond)
        .where(DocumentChunk.embedding.isnot(None))
        .order_by(cosine_dist)
        .limit(top_k)
    )

    result = await session.execute(stmt)
    return [(row[0], row[1], float(row[2])) for row in result.all()]


async def search_keyword_fts(
    session: AsyncSession,
    query: str,
    top_k: int = 10,
    user_id: Optional[uuid.UUID] = None,
    user_role: Optional[str] = None,
) -> List[Tuple[DocumentChunk, Document, float]]:
    """
    Keyword search using PostgreSQL Full-Text Search and ILIKE exact substring matching.
    Critical for exact SKU names, policy numbers, and acronyms.
    Returns (DocumentChunk, Document, fts_rank).
    """
    clean_query = query.strip()
    if not clean_query:
        return []

    acl_cond = build_acl_condition(user_id=user_id, user_role=user_role)

    ts_vector = func.to_tsvector("simple", DocumentChunk.content)
    ts_query = func.plainto_tsquery("simple", clean_query)
    rank_expr = func.ts_rank(ts_vector, ts_query)

    stmt = (
        select(
            DocumentChunk,
            Document,
            rank_expr.label("rank"),
        )
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(Document.status == "indexed")
        .where(acl_cond)
        .where(
            or_(
                ts_vector.op("@@")(ts_query),
                DocumentChunk.content.ilike(f"%{clean_query}%"),
            )
        )
        .order_by(desc("rank"))
        .limit(top_k)
    )

    result = await session.execute(stmt)
    return [(row[0], row[1], float(row[2]) if row[2] else 0.1) for row in result.all()]


def reciprocal_rank_fusion(
    vector_results: List[Tuple[DocumentChunk, Document, float]],
    fts_results: List[Tuple[DocumentChunk, Document, float]],
    top_k: int = 5,
    rrf_k: int = 60,
    vector_weight: float = 1.0,
    fts_weight: float = 1.0,
) -> List[RetrievedChunk]:
    """
    Combines dense vector search and sparse full-text search rankings using Reciprocal Rank Fusion.
    RRF(d) = sum_m ( weight_m / (k + rank_m(d)) )
    """
    scores: Dict[uuid.UUID, float] = {}
    doc_map: Dict[uuid.UUID, Tuple[DocumentChunk, Document]] = {}
    v_ranks: Dict[uuid.UUID, int] = {}
    f_ranks: Dict[uuid.UUID, int] = {}

    # 1. Process vector results
    for rank_idx, (chunk, doc, _) in enumerate(vector_results):
        rank = rank_idx + 1
        v_ranks[chunk.id] = rank
        doc_map[chunk.id] = (chunk, doc)
        rrf_val = vector_weight * (1.0 / (rrf_k + rank))
        scores[chunk.id] = scores.get(chunk.id, 0.0) + rrf_val

    # 2. Process FTS results
    for rank_idx, (chunk, doc, _) in enumerate(fts_results):
        rank = rank_idx + 1
        f_ranks[chunk.id] = rank
        if chunk.id not in doc_map:
            doc_map[chunk.id] = (chunk, doc)
        rrf_val = fts_weight * (1.0 / (rrf_k + rank))
        scores[chunk.id] = scores.get(chunk.id, 0.0) + rrf_val

    # 3. Sort by combined RRF score descending
    sorted_chunk_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)[:top_k]

    results: List[RetrievedChunk] = []
    for cid in sorted_chunk_ids:
        chunk, doc = doc_map[cid]
        page_num = chunk.metadata_.get("page_number") if isinstance(chunk.metadata_, dict) else None

        results.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=doc.id,
                filename=doc.filename,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                page_number=page_num,
                access_scope=doc.access_scope,
                score=scores[cid],
                vector_rank=v_ranks.get(cid),
                fts_rank=f_ranks.get(cid),
                metadata=chunk.metadata_ or {},
            )
        )

    return results


class HybridRetriever:
    """
    Unified Hybrid Search Retriever:
    1. Embeds query via GeminiEmbeddingService (1536 dims)
    2. Performs concurrent/sequential Vector & FTS searches with strict ACL filtering
    3. Fuses rankings via Reciprocal Rank Fusion (RRF)
    """

    def __init__(self, embedding_service: Optional[GeminiEmbeddingService] = None):
        self.embeddings = embedding_service or get_embedding_service()

    async def retrieve(
        self,
        session: AsyncSession,
        query: str,
        top_k: int = 5,
        user_id: Optional[uuid.UUID] = None,
        user_role: Optional[str] = None,
        rrf_k: int = 60,
        vector_weight: float = 1.0,
        fts_weight: float = 1.0,
    ) -> List[RetrievedChunk]:
        """
        Execute full Hybrid Retrieval with ACL filtering.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        # Step 1: Compute query embedding
        query_vector = self.embeddings.embed_query(clean_query)

        # Step 2: Dense Vector Search (retrieve candidate pool of 2x top_k)
        candidate_k = max(top_k * 2, 10)
        vector_candidates = await search_vector_similarity(
            session=session,
            query_vector=query_vector,
            top_k=candidate_k,
            user_id=user_id,
            user_role=user_role,
        )

        # Step 3: Sparse Keyword/FTS Search
        fts_candidates = await search_keyword_fts(
            session=session,
            query=clean_query,
            top_k=candidate_k,
            user_id=user_id,
            user_role=user_role,
        )

        # Step 4: Reciprocal Rank Fusion (RRF)
        fused_chunks = reciprocal_rank_fusion(
            vector_results=vector_candidates,
            fts_results=fts_candidates,
            top_k=top_k,
            rrf_k=rrf_k,
            vector_weight=vector_weight,
            fts_weight=fts_weight,
        )

        logger.info(
            "HybridRetriever query='%s': %d vector, %d fts -> %d fused results",
            clean_query,
            len(vector_candidates),
            len(fts_candidates),
            len(fused_chunks),
        )
        return fused_chunks
