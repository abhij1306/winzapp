from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

import structlog.contextvars
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.api import api_v1_router
from app.api.errors import error_response
from app.config import get_settings
from app.services.health import get_health_status
from app.services.observability import configure_observability
from app.services.scheduler import create_scheduler, write_scheduler_heartbeat
from app.utils.logger import configure_logging
from app.webhooks import whatsapp_router

settings = get_settings()
configure_logging(settings.app_env)
configure_observability(settings)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    scheduler = create_scheduler()
    await write_scheduler_heartbeat()
    scheduler.start()
    application.state.scheduler = scheduler
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(whatsapp_router)
app.include_router(api_v1_router)


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return error_response(
        422,
        "REQUEST_VALIDATION_ERROR",
        "Request validation failed.",
        details={
            "errors": [
                {
                    "type": error["type"],
                    "location": list(error["loc"]),
                    "message": error["msg"],
                }
                for error in exc.errors()
            ],
        },
    )


@app.middleware("http")
async def bind_request_context(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health")
async def health() -> JSONResponse:
    payload = await get_health_status()
    status_code = 200 if payload["status"] == "ok" else 503
    return JSONResponse(content=payload, status_code=status_code)
