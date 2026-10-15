import uuid
from typing import Optional
from urllib.parse import quote
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
get_async_session = get_db
from app.auth.dependencies import (
    get_current_user,
    require_permission,
    get_current_user_permissions,
)
from app.erp.models import User
from app.rag.service import DocumentService
from app.rag.schemas import (
    DocumentResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentChunkResponse,
)

router = APIRouter(prefix="/documents", tags=["RAG Documents"])


def get_document_service() -> DocumentService:
    return DocumentService()


def _to_doc_response(doc, service: DocumentService) -> DocumentResponse:
    try:
        chunk_count = len(doc.chunks) if doc.chunks is not None else 0
    except Exception:
        chunk_count = 0
    download_url = service.get_download_url(doc)
    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        mime_type=doc.mime_type,
        storage_key=doc.storage_key,
        checksum=doc.checksum,
        owner_id=doc.owner_id,
        access_scope=doc.access_scope,
        status=doc.status,
        version=doc.version,
        created_at=doc.created_at,
        chunk_count=chunk_count,
        download_url=download_url,
    )


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a document into the RAG pipeline",
)
async def upload_document(
    file: UploadFile = File(...),
    access_scope: str = Form("internal"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_permission("documents:upload")),
    user_permissions: set[str] = Depends(get_current_user_permissions),
    service: DocumentService = Depends(get_document_service),
):
    # Kiểm tra quyền nếu gán nhãn confidential
    if access_scope == "confidential":
        is_admin = current_user.is_superuser or current_user.role == "admin"
        if not is_admin and "documents:read_confidential" not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền tải lên tài liệu thuộc phạm vi mật (Confidential).",
            )

    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty",
            )

        doc = await service.ingest_document(
            session=session,
            file_bytes=file_bytes,
            filename=file.filename or "uploaded_document",
            mime_type=file.content_type,
            owner_id=current_user.id,
            access_scope=access_scope,
        )
        return _to_doc_response(doc, service)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {e}",
        )


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List ingested documents with pagination and filters",
)
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    access_scope: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_permission("documents:read")),
    user_permissions: set[str] = Depends(get_current_user_permissions),
    service: DocumentService = Depends(get_document_service),
):
    is_admin = current_user.is_superuser or current_user.role == "admin"
    can_read_confidential = "*" in user_permissions or "documents:read_confidential" in user_permissions

    docs, total = await service.list_documents(
        session=session,
        skip=skip,
        limit=limit,
        status=status,
        access_scope=access_scope,
        user_id=current_user.id,
        is_admin=is_admin,
        can_read_confidential=can_read_confidential,
    )
    items = [_to_doc_response(doc, service) for doc in docs]
    return DocumentListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Get detailed document metadata and list of vector chunks",
)
async def get_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_permission("documents:read")),
    user_permissions: set[str] = Depends(get_current_user_permissions),
    service: DocumentService = Depends(get_document_service),
):
    doc = await service.get_document(session, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found",
        )

    # Chống xem trái phép tài liệu confidential
    is_admin = current_user.is_superuser or current_user.role == "admin"
    can_read_confidential = "*" in user_permissions or "documents:read_confidential" in user_permissions
    if doc.access_scope == "confidential" and not is_admin and not can_read_confidential and doc.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài liệu thuộc phạm vi mật (Confidential). Bạn không có quyền truy cập.",
        )

    chunk_responses = [
        DocumentChunkResponse(
            id=c.id,
            chunk_index=c.chunk_index,
            content=c.content,
            metadata_=c.metadata_,
        )
        for c in (doc.chunks or [])
    ]

    base_resp = _to_doc_response(doc, service)
    return DocumentDetailResponse(
        **base_resp.model_dump(),
        chunks=chunk_responses,
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a document from storage and delete all associated chunks",
)
async def delete_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_permission("documents:delete")),
    service: DocumentService = Depends(get_document_service),
):
    is_admin = current_user.is_superuser or current_user.role == "admin"
    try:
        deleted = await service.delete_document(
            session=session,
            document_id=document_id,
            actor_id=current_user.id,
            is_admin=is_admin,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found",
        )
    return {"message": f"Document '{document_id}' deleted successfully"}



@router.post(
    "/{document_id}/reindex",
    response_model=DocumentResponse,
    summary="Re-index an existing document from stored raw file",
)
async def reindex_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_permission("documents:upload")),
    service: DocumentService = Depends(get_document_service),
):
    try:
        doc = await service.reindex_document(session, document_id)
        return _to_doc_response(doc, service)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Re-indexing failed: {e}",
        )


@router.get(
    "/{document_id}/download-url",
    summary="Generate temporary presigned download URL for the original file",
)
async def get_download_url(
    document_id: uuid.UUID,
    expires_in: int = Query(3600, ge=60, le=86400),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_permission("documents:read")),
    user_permissions: set[str] = Depends(get_current_user_permissions),
    service: DocumentService = Depends(get_document_service),
):
    doc = await service.get_document(session, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found",
        )

    # Chống tải trái phép tài liệu confidential
    is_admin = current_user.is_superuser or current_user.role == "admin"
    can_read_confidential = "*" in user_permissions or "documents:read_confidential" in user_permissions
    if doc.access_scope == "confidential" and not is_admin and not can_read_confidential and doc.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài liệu thuộc phạm vi mật (Confidential). Bạn không có quyền truy cập liên kết tải.",
        )

    url = service.get_download_url(doc, expires_in=expires_in)
    return {"download_url": url, "expires_in": expires_in}


@router.get(
    "/{document_id}/file",
    summary="Download or stream the original raw document file directly",
)
async def get_document_file(
    document_id: uuid.UUID,
    inline: bool = Query(False, description="Whether to show inline for browser preview"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_permission("documents:read")),
    user_permissions: set[str] = Depends(get_current_user_permissions),
    service: DocumentService = Depends(get_document_service),
):
    doc = await service.get_document(session, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found",
        )

    # Chống tải trái phép tài liệu confidential
    is_admin = current_user.is_superuser or current_user.role == "admin"
    can_read_confidential = "*" in user_permissions or "documents:read_confidential" in user_permissions
    if doc.access_scope == "confidential" and not is_admin and not can_read_confidential and doc.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài liệu thuộc phạm vi mật (Confidential). Bạn không có quyền tải tệp này.",
        )

    try:
        file_bytes = service.storage.download_file(doc.storage_key)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Không thể tải tệp tin từ hệ thống lưu trữ: {e}",
        )

    disposition = "inline" if inline else "attachment"
    encoded_name = quote(doc.filename)
    return Response(
        content=file_bytes,
        media_type=doc.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'{disposition}; filename="{encoded_name}"; filename*=UTF-8\'\'{encoded_name}',
        },
    )

