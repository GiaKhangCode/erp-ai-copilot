from fastapi import APIRouter
from app.api.v1.erp import router as erp_router
from app.auth.router import router as auth_router
from app.api.v1.documents import router as documents_router

api_router = APIRouter()

# System endpoints
@api_router.get("/status", tags=["System"])
async def api_status():
    return {"status": "online", "version": "v1"}


# Auth endpoints
api_router.include_router(auth_router)

# ERP Domain endpoints
api_router.include_router(erp_router)

# RAG Document Ingestion endpoints
api_router.include_router(documents_router)

