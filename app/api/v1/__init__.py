from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.clinic_settings import router as clinic_settings_router
from app.api.v1.patients import router as patients_router
from app.api.v1.report_ready import router as report_ready_router
from app.api.v1.report_upload import router as report_upload_router
from app.api.v1.test_bookings import router as test_bookings_router
from app.api.v1.tests import router as tests_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(clinic_settings_router)
api_v1_router.include_router(patients_router)
api_v1_router.include_router(report_ready_router)
api_v1_router.include_router(test_bookings_router)
api_v1_router.include_router(report_upload_router)
api_v1_router.include_router(tests_router)

__all__ = ["api_v1_router"]
