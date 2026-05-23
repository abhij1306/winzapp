from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import cast

from app.config import get_settings
from app.services.cache import redis_delete, redis_get, redis_set_json

OTP_TTL_SECONDS = 5 * 60


class AuthTokenError(RuntimeError):
    pass


def otp_cache_key(owner_whatsapp: str) -> str:
    return f"auth:otp:{owner_whatsapp}"


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def store_otp(owner_whatsapp: str, clinic_id: str, otp: str) -> None:
    await redis_set_json(
        otp_cache_key(owner_whatsapp),
        OTP_TTL_SECONDS,
        {
            "clinic_id": clinic_id,
            "otp_hash": hash_otp(owner_whatsapp, otp),
        },
    )


async def verify_stored_otp(owner_whatsapp: str, otp: str) -> str | None:
    cached = await redis_get(otp_cache_key(owner_whatsapp))
    if cached is None:
        return None
    payload = cast(dict[str, object], json.loads(cached))
    expected = payload.get("otp_hash")
    clinic_id = payload.get("clinic_id")
    if not isinstance(expected, str) or not isinstance(clinic_id, str):
        return None
    if not hmac.compare_digest(expected, hash_otp(owner_whatsapp, otp)):
        return None
    await redis_delete(otp_cache_key(owner_whatsapp))
    return clinic_id


def hash_otp(owner_whatsapp: str, otp: str) -> str:
    settings = get_settings()
    return hmac.new(
        settings.jwt_secret.encode("utf-8"),
        f"{owner_whatsapp}:{otp}".encode(),
        hashlib.sha256,
    ).hexdigest()


def create_access_token(owner_whatsapp: str, clinic_id: str, role: str = "owner") -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": owner_whatsapp,
        "clinic_id": clinic_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_access_token_minutes)).timestamp()),
    }
    return encode_jwt(payload)


def decode_access_token(token: str) -> dict[str, object]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError as exc:
        raise AuthTokenError("Invalid token format") from exc

    signed = f"{header_b64}.{payload_b64}".encode("ascii")
    expected = sign_bytes(signed)
    if not hmac.compare_digest(signature_b64, expected):
        raise AuthTokenError("Invalid token signature")

    payload = cast(dict[str, object], json.loads(base64url_decode(payload_b64)))
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(datetime.now(UTC).timestamp()):
        raise AuthTokenError("Token expired")
    return payload


def encode_jwt(payload: dict[str, object]) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signed = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = sign_bytes(signed)
    return f"{header_b64}.{payload_b64}.{signature}"


def sign_bytes(value: bytes) -> str:
    settings = get_settings()
    digest = hmac.new(settings.jwt_secret.encode("utf-8"), value, hashlib.sha256).digest()
    return base64url_encode(digest)


def base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))
