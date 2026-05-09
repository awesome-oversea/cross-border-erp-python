from fastapi import APIRouter

admin_router = APIRouter(tags=["Admin"])


@admin_router.get("/ping", summary="Admin ping")
async def admin_ping():
    return {"message": "admin pong"}
