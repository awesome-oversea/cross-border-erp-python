from fastapi import APIRouter

webhook_router = APIRouter(tags=["Webhooks"])


@webhook_router.post("/{provider}", summary="Receive webhook")
async def receive_webhook(provider: str):
    return {"message": f"webhook received from {provider}"}
