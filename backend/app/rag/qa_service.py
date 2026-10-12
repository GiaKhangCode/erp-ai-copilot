import asyncio
import logging
import uuid
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from google import genai
from google.genai import types
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.rag.prompts import (
    RAG_SYSTEM_PROMPT,
    build_qa_user_prompt,
    parse_grounded_answer,
)
from app.rag.retrieval import HybridRetriever, RetrievedChunk
from app.rag.schemas import Citation, GroundedAnswer

logger = logging.getLogger(__name__)


class QAService:
    """
    RAG Question & Answering Domain Service:
    1. Hybrid Search (Vector + FTS + RRF) with DB-level ACL authorization.
    2. Short-circuit Abstention when no chunks found or user has no permissions.
    3. Grounded generation via Gemini (gemini-3.5-flash-lite) with strict anti-hallucination.
    4. Post-generation citation validation to eliminate fabricated citations.
    """

    def __init__(
        self,
        retriever: Optional[HybridRetriever] = None,
        genai_client: Optional[genai.Client] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
        settings = get_settings()
        self.retriever = retriever or HybridRetriever()
        self.api_key = settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self.temperature = temperature if temperature is not None else settings.GEMINI_TEMPERATURE

        if genai_client:
            self.client = genai_client
        else:
            if not self.api_key:
                logger.warning("GEMINI_API_KEY not set! Gemini Q&A generation will fail.")
            self.client = genai.Client(api_key=self.api_key)

        logger.info(
            "Initialized QAService with model='%s', temperature=%.2f",
            self.model,
            self.temperature,
        )

    async def search(
        self,
        session: AsyncSession,
        query: str,
        user_id: Optional[uuid.UUID] = None,
        user_role: Optional[str] = None,
        top_k: int = 5,
    ) -> List[RetrievedChunk]:
        """
        Execute Hybrid Search (Vector + FTS + RRF) with ACL pre-filtering.
        """
        return await self.retriever.retrieve(
            session=session,
            query=query,
            top_k=top_k,
            user_id=user_id,
            user_role=user_role,
        )

    async def ask(
        self,
        session: AsyncSession,
        query: str,
        user_id: Optional[uuid.UUID] = None,
        user_role: Optional[str] = None,
        top_k: int = 5,
        max_retries: int = 3,
    ) -> GroundedAnswer:
        """
        Execute full Grounded RAG Q&A workflow:
        - ACL-filtered Hybrid Retrieval
        - Short-circuit abstention if empty context
        - Structured LLM response generation with strict citations
        - Citation verification and enrichment
        """
        clean_query = query.strip()
        if not clean_query:
            return GroundedAnswer(
                answer="Vui lòng cung cấp câu hỏi cần tra cứu.",
                citations=[],
                has_sufficient_context=False,
                confidence_score=0.0,
                suggested_followups=[],
            )

        # Step 1: Hybrid Retrieval with ACL pre-filtering
        chunks = await self.search(
            session=session,
            query=clean_query,
            user_id=user_id,
            user_role=user_role,
            top_k=top_k,
        )

        # Step 2: Short-circuit Abstention (No documents found or no access rights)
        if not chunks:
            logger.info(
                "Short-circuit abstention for query='%s', user_id=%s, role=%s",
                clean_query,
                user_id,
                user_role,
            )
            return GroundedAnswer(
                answer="Dựa trên các tài liệu được cung cấp trong phạm vi quyền truy cập của bạn, tôi không tìm thấy thông tin để trả lời câu hỏi này.",
                citations=[],
                has_sufficient_context=False,
                confidence_score=0.0,
                suggested_followups=[],
            )

        # Step 3: Construct Grounded Prompt
        user_prompt = build_qa_user_prompt(query=clean_query, chunks=chunks)
        config = types.GenerateContentConfig(
            system_instruction=RAG_SYSTEM_PROMPT,
            temperature=self.temperature,
            response_mime_type="application/json",
        )

        # Step 4: Call Gemini LLM with retry logic
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                response = await self.client.aio.models.generate_content(
                    model=self.model,
                    contents=user_prompt,
                    config=config,
                )
                if not response.text:
                    raise RuntimeError("Empty response received from Gemini API")

                # Step 5: Parse Grounded Answer
                grounded = parse_grounded_answer(response.text)

                # Step 6: Post-generation Citation Validation
                validated_answer = self._validate_citations(grounded, chunks)
                return validated_answer

            except Exception as e:
                last_error = e
                logger.warning(
                    "Gemini Q&A call failed (attempt %d/%d): %s",
                    attempt,
                    max_retries,
                    e,
                )
                if attempt == max_retries:
                    break
                await asyncio.sleep(2 ** attempt)

        # If LLM failed after retries, return graceful degraded response
        logger.error("Failed to generate Grounded Answer after retries: %s", last_error)
        return GroundedAnswer(
            answer="Hệ thống AI hiện đang bận hoặc gặp sự cố kết nối. Vui lòng thử lại sau.",
            citations=[],
            has_sufficient_context=False,
            confidence_score=0.0,
            suggested_followups=[],
        )

    def _validate_citations(
        self,
        grounded: GroundedAnswer,
        chunks: List[RetrievedChunk],
    ) -> GroundedAnswer:
        """
        Validates citations against actual retrieved chunks.
        Eliminates fabricated chunk IDs and enriches missing metadata.
        """
        chunk_by_id: Dict[uuid.UUID, RetrievedChunk] = {c.chunk_id: c for c in chunks}
        chunk_by_file_idx: Dict[Tuple[str, int], RetrievedChunk] = {
            (c.filename, c.chunk_index): c for c in chunks
        }

        valid_citations: List[Citation] = []
        for cit in grounded.citations:
            matched_chunk = None

            # 1. Match by chunk_id
            if cit.chunk_id in chunk_by_id:
                matched_chunk = chunk_by_id[cit.chunk_id]
            # 2. Fallback match by filename and chunk_index
            elif (cit.filename, cit.chunk_index) in chunk_by_file_idx:
                matched_chunk = chunk_by_file_idx[(cit.filename, cit.chunk_index)]

            if matched_chunk:
                valid_citations.append(
                    Citation(
                        document_id=matched_chunk.document_id,
                        filename=matched_chunk.filename,
                        chunk_id=matched_chunk.chunk_id,
                        page_number=matched_chunk.page_number,
                        chunk_index=matched_chunk.chunk_index,
                        quote=cit.quote or matched_chunk.content[:200],
                    )
                )
            else:
                logger.warning(
                    "Ignored hallucinated citation: file='%s', chunk_id=%s, chunk_index=%d",
                    cit.filename,
                    cit.chunk_id,
                    cit.chunk_index,
                )

        grounded.citations = valid_citations
        return grounded


@lru_cache
def get_qa_service() -> QAService:
    """Singleton cached factory for QAService."""
    return QAService()
