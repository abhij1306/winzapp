from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api import api_v1_router
from app.config import get_settings
from app.services.health import get_health_status
from app.utils.logger import configure_logging
from app.webhooks import whatsapp_router

settings = get_settings()
configure_logging(settings.app_env)
app = FastAPI(title=settings.app_name)
app.include_router(whatsapp_router)
app.include_router(api_v1_router)


@app.get("/health")
async def health() -> JSONResponse:
    payload = await get_health_status()
    status_code = 200 if payload["status"] == "ok" else 503
    return JSONResponse(content=payload, status_code=status_code)
