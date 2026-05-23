from __future__ import annotations

import base64
import binascii
from urllib.parse import quote

import httpx

from app.config import get_settings

REPORT_SIGNED_URL_TTL_SECONDS = 24 * 60 * 60


class StorageError(RuntimeError):
    pass


async def copy_report_from_url(report_pdf_url: str, clinic_id: str, booking_id: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get(report_pdf_url)
    if response.status_code >= 400:
        raise StorageError(f"Report download failed with status {response.status_code}")
    return await upload_report_pdf(response.content, clinic_id, booking_id)


async def upload_report_base64(
    report_pdf_base64: str,
    clinic_id: str,
    booking_id: str,
) -> str:
    try:
        pdf_bytes = base64.b64decode(report_pdf_base64, validate=True)
    except binascii.Error as exc:
        raise StorageError("Invalid base64 report payload") from exc
    return await upload_report_pdf(pdf_bytes, clinic_id, booking_id)


async def upload_report_pdf(pdf_bytes: bytes, clinic_id: str, booking_id: str) -> str:
    settings = get_settings()
    path = report_storage_path(clinic_id, booking_id)
    url = storage_object_url(path)
    headers = storage_headers(content_type="application/pdf") | {"x-upsert": "true"}
    async with httpx.AsyncClient() as client:
        response = await client.put(url, content=pdf_bytes, headers=headers)
    if response.status_code >= 400:
        raise StorageError(f"Report upload failed with status {response.status_code}")
    if not settings.supabase_url:
        raise StorageError("SUPABASE_URL is required for report storage")
    return path


async def create_signed_url(
    path: str,
    expires_in: int = REPORT_SIGNED_URL_TTL_SECONDS,
) -> str:
    url = storage_object_url(path, action="object/sign")
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json={"expiresIn": expires_in}, headers=storage_headers())
    if response.status_code >= 400:
        raise StorageError(f"Signed URL creation failed with status {response.status_code}")
    signed_path = response.json().get("signedURL")
    if not isinstance(signed_path, str):
        raise StorageError("Signed URL response did not include signedURL")
    return absolute_signed_url(signed_path)


def report_storage_path(clinic_id: str, booking_id: str) -> str:
    return f"reports/{clinic_id}/{booking_id}/report.pdf"


def storage_object_url(path: str, action: str = "object") -> str:
    settings = get_settings()
    if not settings.supabase_url:
        raise StorageError("SUPABASE_URL is required for report storage")
    bucket = quote(settings.supabase_storage_bucket, safe="")
    quoted_path = quote(path, safe="/")
    return f"{settings.supabase_url.rstrip('/')}/storage/v1/{action}/{bucket}/{quoted_path}"


def storage_headers(content_type: str | None = None) -> dict[str, str]:
    settings = get_settings()
    if not settings.supabase_service_key:
        raise StorageError("SUPABASE_SERVICE_KEY is required for report storage")
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_key}",
        "apikey": settings.supabase_service_key,
    }
    if content_type is not None:
        headers["Content-Type"] = content_type
    return headers


def absolute_signed_url(signed_path: str) -> str:
    if signed_path.startswith("http://") or signed_path.startswith("https://"):
        return signed_path
    settings = get_settings()
    return f"{settings.supabase_url.rstrip('/')}/storage/v1{signed_path}"
