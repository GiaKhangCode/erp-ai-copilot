import logging
from typing import Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_optional_current_user
from app.erp.models import User
from app.rag.qa_service import QAService, get_qa_service
from app.rag.schemas import (
    GroundedAnswer,
    RAGAskRequest,
    RAGSearchRequest,
    RAGSearchResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG / Knowledge Assistant"])


@router.post(
    "/search",
    response_model=RAGSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Thực hiện tìm kiếm kết hợp Hybrid Search (Vector + FTS + RRF) có phân quyền ACL",
)
async def search_documents(
    payload: RAGSearchRequest,
    session: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
    qa_service: QAService = Depends(get_qa_service),
) -> RAGSearchResponse:
    """
    Tìm kiếm tài liệu kết hợp giữa pgvector cosine similarity và PostgreSQL Full-Text Search.
    Áp dụng phân quyền ACL nghiêm ngặt trước khi xếp hạng (public, internal, role, owner_id).
    """
    user_id = current_user.id if current_user else None
    user_role = current_user.role if current_user else None

    chunks = await qa_service.search(
        session=session,
        query=payload.query,
        user_id=user_id,
        user_role=user_role,
        top_k=payload.top_k,
    )

    return RAGSearchResponse(
        query=payload.query,
        total_retrieved=len(chunks),
        chunks=chunks,
    )


@router.post(
    "/ask",
    response_model=GroundedAnswer,
    status_code=status.HTTP_200_OK,
    summary="Hỏi đáp tài liệu thông minh (Grounded Q&A Assistant) kèm trích dẫn nguồn và chống ảo giác",
)
async def ask_documents(
    payload: RAGAskRequest,
    session: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
    qa_service: QAService = Depends(get_qa_service),
) -> GroundedAnswer:
    """
    Trợ lý hỏi đáp tài liệu sử dụng mô hình Gemini 3.5 Flash-Lite:
    - Lọc quyền truy cập tài liệu qua Hybrid Retrieval.
    - Từ chối trả lời (Short-circuit Abstention) nếu không có tài liệu chứng cứ.
    - Cung cấp câu trả lời có cấu trúc và trích dẫn chuẩn [Nguồn: ..., Trang: ..., Đoạn: ...].
    - Loại bỏ các trích dẫn giả mạo (hallucinated citations).
    """
    user_id = current_user.id if current_user else None
    user_role = current_user.role if current_user else None

    answer = await qa_service.ask(
        session=session,
        query=payload.query,
        user_id=user_id,
        user_role=user_role,
        top_k=payload.top_k,
    )

    return answer
