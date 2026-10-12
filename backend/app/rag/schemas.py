import uuid
from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, ConfigDict


class DocumentChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chunk_index: int
    content: str
    metadata_: dict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    mime_type: Optional[str] = None
    storage_key: str
    checksum: str
    owner_id: Optional[uuid.UUID] = None
    access_scope: str
    status: str
    version: int
    created_at: datetime
    chunk_count: int
    download_url: Optional[str] = None


class DocumentDetailResponse(DocumentResponse):
    chunks: List[DocumentChunkResponse] = []


class DocumentListResponse(BaseModel):
    items: List[DocumentResponse]
    total: int
    skip: int
    limit: int


class Citation(BaseModel):
    """Citation linking an answer claim to an exact source document and chunk."""
    document_id: uuid.UUID
    filename: str
    chunk_id: uuid.UUID
    page_number: Optional[int] = None
    chunk_index: int
    quote: str = ""


class GroundedAnswer(BaseModel):
    """Structured response contract for Grounded RAG Q&A with citations and abstention flag."""
    answer: str
    citations: List[Citation] = []
    has_sufficient_context: bool = True
    confidence_score: float = 1.0
    suggested_followups: List[str] = []


class RAGSearchRequest(BaseModel):
    """Request payload for hybrid search endpoint."""
    query: str
    top_k: int = 5


class RAGAskRequest(BaseModel):
    """Request payload for RAG Q&A endpoint."""
    query: str
    top_k: int = 5


class RAGSearchResponse(BaseModel):
    """Response payload for hybrid search endpoint."""
    query: str
    total_retrieved: int
    chunks: List[Any] = []
