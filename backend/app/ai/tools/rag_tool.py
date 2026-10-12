import json
import logging
from langchain_core.tools import tool

from app.ai.tools.context import get_current_user_context
from app.db.session import async_session_factory
from app.rag.qa_service import get_qa_service

logger = logging.getLogger(__name__)


@tool
async def search_company_knowledge(query: str) -> str:
    """
    Tra cứu kho tri thức, tài liệu nội bộ, chính sách công ty, quy định đổi trả, bảo hành,
    quy trình giao hàng và sổ tay an toàn kho của doanh nghiệp (RAG Knowledge Assistant).
    Hệ thống tự động lọc quyền truy cập (ACL) của người dùng hiện tại và trích dẫn nguồn tài liệu chính xác.

    Args:
        query: Câu hỏi hoặc từ khóa cần tra cứu trong tài liệu nội bộ (Ví dụ: 'quy định đổi trả hàng', 'hạn mức công tác phí').
    """
    clean_query = query.strip()
    if not clean_query:
        return json.dumps({
            "has_sufficient_context": False,
            "answer": "Vui lòng cung cấp nội dung cần tra cứu trong tài liệu.",
            "citations": [],
        }, ensure_ascii=False)

    user_ctx = get_current_user_context()
    qa_service = get_qa_service()

    async with async_session_factory() as session:
        grounded_answer = await qa_service.ask(
            session=session,
            query=clean_query,
            user_id=user_ctx.user_id,
            user_role=user_ctx.user_role,
            top_k=4,
        )

        return json.dumps({
            "has_sufficient_context": grounded_answer.has_sufficient_context,
            "answer": grounded_answer.answer,
            "confidence_score": grounded_answer.confidence_score,
            "citations": [
                {
                    "filename": c.filename,
                    "page_number": c.page_number,
                    "chunk_index": c.chunk_index,
                    "quote": c.quote,
                }
                for c in grounded_answer.citations
            ],
            "suggested_followups": grounded_answer.suggested_followups,
        }, ensure_ascii=False)
