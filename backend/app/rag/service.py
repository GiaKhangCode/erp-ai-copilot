import logging
import uuid
from typing import List, Optional, Tuple

from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.models import Document, DocumentChunk
from app.rag.storage import get_storage_service, BaseStorageService, sanitize_filename
from app.rag.parser import parse_document
from app.rag.chunker import chunk_document
from app.rag.embeddings import get_embedding_service, GeminiEmbeddingService

logger = logging.getLogger(__name__)


class DocumentService:
    """
    Orchestrates the entire Document Ingestion Pipeline for ERP RAG:
    Storage Upload -> Security Checks -> Parsing -> Chunking -> Embedding -> Database Persistence.
    """

    def __init__(
        self,
        storage_service: Optional[BaseStorageService] = None,
        embedding_service: Optional[GeminiEmbeddingService] = None,
    ):
        self.storage = storage_service or get_storage_service()
        self.embeddings = embedding_service or get_embedding_service()

    async def ingest_document(
        self,
        session: AsyncSession,
        file_bytes: bytes,
        filename: str,
        mime_type: Optional[str] = None,
        owner_id: Optional[uuid.UUID] = None,
        access_scope: str = "internal",
    ) -> Document:
        """
        Full ingestion lifecycle:
        1. Store raw file to Object Storage (MinIO)
        2. Create Document record (status: processing)
        3. Parse document into sections
        4. Chunk sections into structured chunks with ACL
        5. Generate 1536-dim vector embeddings
        6. Bulk insert chunks into pgvector
        7. Update Document status to 'indexed'
        """
        clean_name = sanitize_filename(filename)

        # Step 1: Upload raw file to storage
        storage_key, checksum = self.storage.upload_file(
            content=file_bytes,
            filename=clean_name,
            mime_type=mime_type,
        )

        # Step 2: Create DB Document record
        doc = Document(
            id=uuid.uuid4(),
            filename=clean_name,
            mime_type=mime_type,
            storage_key=storage_key,
            checksum=checksum,
            owner_id=owner_id,
            access_scope=access_scope,
            status="processing",
            version=1,
        )
        session.add(doc)
        await session.flush()

        try:
            # Step 3: Parse document
            parsed_doc = parse_document(file_bytes, clean_name, mime_type)

            # Step 4: Chunk document
            chunks = chunk_document(
                parsed_doc=parsed_doc,
                document_id=doc.id,
                access_scope=access_scope,
                checksum=checksum,
            )

            if not chunks:
                raise ValueError(f"Document '{clean_name}' yielded zero valid chunks")

            # Step 5: Embed chunks in batches
            embeddings = self.embeddings.embed_chunks(chunks)

            # Step 6: Insert chunks into pgvector
            for payload, vector in zip(chunks, embeddings):
                db_chunk = DocumentChunk(
                    id=uuid.uuid4(),
                    document_id=doc.id,
                    chunk_index=payload.chunk_index,
                    content=payload.content,
                    metadata_=payload.metadata,
                    embedding=vector,
                )
                session.add(db_chunk)

            # Step 7: Update status to 'indexed'
            doc.status = "indexed"
            await session.commit()

            # Eagerly load document with chunks
            loaded_stmt = (
                select(Document)
                .options(selectinload(Document.chunks))
                .where(Document.id == doc.id)
            )
            loaded_res = await session.execute(loaded_stmt)
            loaded_doc = loaded_res.scalar_one()

            logger.info(
                "Successfully ingested document '%s' (ID: %s, Chunks: %d)",
                clean_name,
                loaded_doc.id,
                len(chunks),
            )
            return loaded_doc

        except Exception as e:
            logger.error("Failed to ingest document '%s': %s", clean_name, e, exc_info=True)
            doc.status = "failed"
            await session.commit()
            raise

    async def list_documents(
        self,
        session: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
        access_scope: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
        is_admin: bool = False,
        can_read_confidential: bool = False,
    ) -> Tuple[List[Document], int]:
        """List documents with pagination, filters and ACL scoping."""
        from sqlalchemy import or_
        query = select(Document).options(selectinload(Document.chunks))
        count_query = select(func.count(Document.id))

        if status:
            query = query.where(Document.status == status)
            count_query = count_query.where(Document.status == status)

        if access_scope:
            query = query.where(Document.access_scope == access_scope)
            count_query = count_query.where(Document.access_scope == access_scope)

        # ACL Scoping: Người không có quyền confidential và không phải admin chỉ xem public, internal hoặc tài liệu của chính mình
        if not is_admin and not can_read_confidential:
            if user_id:
                acl_filter = or_(
                    Document.access_scope.in_(["public", "internal"]),
                    Document.owner_id == user_id,
                )
            else:
                acl_filter = Document.access_scope == "public"

            query = query.where(acl_filter)
            count_query = count_query.where(acl_filter)

        total_res = await session.execute(count_query)
        total = total_res.scalar() or 0

        query = query.order_by(Document.created_at.desc()).offset(skip).limit(limit)
        result = await session.execute(query)
        docs = list(result.scalars().all())

        return docs, total

    async def get_document(
        self,
        session: AsyncSession,
        document_id: uuid.UUID,
    ) -> Optional[Document]:
        """Get document details with its chunks."""
        query = (
            select(Document)
            .options(selectinload(Document.chunks))
            .where(Document.id == document_id)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def delete_document(
        self,
        session: AsyncSession,
        document_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
        is_admin: bool = False,
    ) -> bool:
        """Delete document from storage and database (cascades chunks) with ownership check."""
        doc = await self.get_document(session, document_id)
        if not doc:
            return False

        # Kiểm tra quyền sở hữu (BOLA/IDOR protection)
        if not is_admin and actor_id and doc.owner_id != actor_id:
            raise PermissionError("Chỉ người tải lên tài liệu hoặc Quản trị viên mới được phép xóa tài liệu này.")

        # Delete physical file from MinIO
        try:
            self.storage.delete_file(doc.storage_key)
        except Exception as e:
            logger.warning("Could not delete storage object '%s': %s", doc.storage_key, e)

        # Delete database row (cascades to document_chunks)
        await session.delete(doc)
        await session.commit()
        logger.info("Deleted document ID %s and associated vector chunks", document_id)
        return True

    async def reindex_document(
        self,
        session: AsyncSession,
        document_id: uuid.UUID,
    ) -> Document:
        """
        Re-index an existing document:
        Downloads raw file from storage, removes old chunks, re-chunks, re-embeds, updates version.
        """
        doc = await self.get_document(session, document_id)
        if not doc:
            raise ValueError(f"Document with ID {document_id} not found")

        logger.info("Re-indexing document '%s' (ID: %s)", doc.filename, doc.id)

        # Download raw file from MinIO
        file_bytes = self.storage.download_file(doc.storage_key)

        # Delete existing chunks in DB
        await session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == doc.id)
        )
        doc.status = "processing"
        await session.flush()

        try:
            parsed_doc = parse_document(file_bytes, doc.filename, doc.mime_type)
            chunks = chunk_document(
                parsed_doc=parsed_doc,
                document_id=doc.id,
                access_scope=doc.access_scope,
                checksum=doc.checksum,
            )

            embeddings = self.embeddings.embed_chunks(chunks)

            for payload, vector in zip(chunks, embeddings):
                db_chunk = DocumentChunk(
                    id=uuid.uuid4(),
                    document_id=doc.id,
                    chunk_index=payload.chunk_index,
                    content=payload.content,
                    metadata_=payload.metadata,
                    embedding=vector,
                )
                session.add(db_chunk)

            doc.status = "indexed"
            doc.version += 1
            await session.commit()

            loaded_stmt = (
                select(Document)
                .options(selectinload(Document.chunks))
                .where(Document.id == doc.id)
            )
            loaded_res = await session.execute(loaded_stmt)
            loaded_doc = loaded_res.scalar_one()

            logger.info("Successfully re-indexed document '%s' to version %d", loaded_doc.filename, loaded_doc.version)
            return loaded_doc

        except Exception as e:
            logger.error("Failed to re-index document '%s': %s", doc.filename, e, exc_info=True)
            doc.status = "failed"
            await session.commit()
            raise

    def get_download_url(self, doc: Document, expires_in: int = 3600) -> Optional[str]:
        """Generate presigned download URL for a document."""
        return self.storage.get_presigned_url(doc.storage_key, expires_in=expires_in)
