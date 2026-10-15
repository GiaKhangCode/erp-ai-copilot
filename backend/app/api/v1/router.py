from fastapi import APIRouter
from app.api.v1.erp import router as erp_router
from app.auth.router import router as auth_router
from app.api.v1.documents import router as documents_router
from app.api.v1.rag import router as rag_router
from app.api.v1.chat import router as chat_router
from app.api.v1.orders import router as orders_router
from app.api.v1.admin import router as admin_router

api_router = APIRouter()

# System endpoints
@api_router.get("/status", tags=["System"])
async def api_status():
    return {"status": "online", "version": "v1"}


# Auth endpoints
api_router.include_router(auth_router)

# ERP Domain endpoints
api_router.include_router(erp_router)

# Admin User & Role Management endpoints
api_router.include_router(admin_router)

# RAG Document Ingestion endpoints
api_router.include_router(documents_router)

# RAG Retrieval & Q&A Assistant endpoints
api_router.include_router(rag_router)

# AI Chat & Conversation endpoints
api_router.include_router(chat_router)

# Document AI & Approval Inbox endpoints
api_router.include_router(orders_router)


