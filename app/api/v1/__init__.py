from fastapi import APIRouter

from app.api.v1.report_ready import router as report_ready_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(report_ready_router)

__all__ = ["api_v1_router"]
