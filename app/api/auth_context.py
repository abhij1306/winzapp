from __future__ import annotations

from dataclasses import dataclass

from fastapi.responses import JSONResponse

from app.api.errors import error_response
from app.services.auth import AuthTokenError, decode_access_token


@dataclass(frozen=True)
class CurrentOwner:
    owner_whatsapp: str
    clinic_id: str
    role: str


def authenticate_owner(authorization: str | None, clinic_id: str) -> CurrentOwner | JSONResponse:
    if authorization is None or not authorization.startswith("Bearer "):
        return error_response(401, "AUTH_REQUIRED", "Bearer token is required.")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        claims = decode_access_token(token)
    except AuthTokenError:
        return error_response(401, "INVALID_TOKEN", "Bearer token is invalid or expired.")

    owner = owner_from_claims(claims)
    if owner is None:
        return error_response(401, "INVALID_TOKEN", "Bearer token is invalid or expired.")
    if owner.role != "owner":
        return error_response(403, "OWNER_REQUIRED", "Owner access is required.")
    if owner.clinic_id != clinic_id:
        return error_response(
            403,
            "CLINIC_FORBIDDEN",
            "Token does not allow access to this clinic.",
        )
    return owner


def owner_from_claims(claims: dict[str, object]) -> CurrentOwner | None:
    owner_whatsapp = claims.get("sub")
    clinic_id = claims.get("clinic_id")
    role = claims.get("role")
    if not isinstance(owner_whatsapp, str):
        return None
    if not isinstance(clinic_id, str):
        return None
    if not isinstance(role, str):
        return None
    return CurrentOwner(owner_whatsapp=owner_whatsapp, clinic_id=clinic_id, role=role)
