from fastapi import FastAPI

from app.config import get_settings
from app.utils.logger import configure_logging

settings = get_settings()
configure_logging(settings.app_env)
app = FastAPI(title=settings.app_name)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
