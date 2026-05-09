from fastapi import APIRouter

open_router = APIRouter(tags=["OpenAPI"])


@open_router.get("/ping", summary="Open API ping")
async def open_ping():
    return {"message": "open pong"}
