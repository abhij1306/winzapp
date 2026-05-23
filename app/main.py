from fastapi import FastAPI

from app.config import get_settings
from app.utils.logger import configure_logging
from app.webhooks import whatsapp_router

settings = get_settings()
configure_logging(settings.app_env)
app = FastAPI(title=settings.app_name)
app.include_router(whatsapp_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
