from fastapi import APIRouter

api_router = APIRouter()


@api_router.get("/status", tags=["System"])
async def api_status():
    return {"status": "online", "version": "v1"}
