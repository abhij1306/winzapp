from __future__ import annotations

import importlib
from collections.abc import Callable
from types import ModuleType
from typing import Protocol, cast

from app.config import Settings, get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SettingsLike(Protocol):
    app_env: str
    app_name: str
    sentry_dsn: str
    logfire_token: str
    observability_alerts_enabled: bool


def configure_observability(settings: Settings | None = None) -> list[str]:
    active_settings = settings or get_settings()
    configured: list[str] = []
    if active_settings.sentry_dsn and configure_sentry(active_settings):
        configured.append("sentry")
    if active_settings.logfire_token and configure_logfire(active_settings):
        configured.append("logfire")
    logger.info("observability.configured", providers=configured)
    return configured


def configure_sentry(settings: SettingsLike) -> bool:
    module = import_optional("sentry_sdk")
    if module is None:
        logger.warning("observability.sentry_missing")
        return False
    init = cast(Callable[..., object], module.__dict__["init"])
    init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
    return True


def configure_logfire(settings: SettingsLike) -> bool:
    module = import_optional("logfire")
    if module is None:
        logger.warning("observability.logfire_missing")
        return False
    configure = cast(Callable[..., object], module.__dict__["configure"])
    configure(
        token=settings.logfire_token,
        service_name=settings.app_name,
        environment=settings.app_env,
    )
    return True


def capture_exception(exc: Exception, **context: object) -> None:
    module = import_optional("sentry_sdk")
    if module is None:
        logger.warning("observability.exception", error=str(exc), **context)
        return
    push_scope = cast(Callable[[], SentryScope], module.__dict__["push_scope"])
    with push_scope() as scope:
        set_context = getattr(scope, "set_context", None)
        if callable(set_context):
            set_context("app_context", context)
        capture = cast(Callable[[Exception], object], module.__dict__["capture_exception"])
        capture(exc)


def emit_alert(alert_type: str, message: str, **fields: object) -> None:
    settings = get_settings()
    if not settings.observability_alerts_enabled:
        return
    logger.warning(
        "alert.triggered",
        alert_type=alert_type,
        message=message,
        **fields,
    )
    module = import_optional("sentry_sdk")
    if module is not None:
        capture_message = cast(Callable[..., object], module.__dict__["capture_message"])
        capture_message(message, level="warning")


def record_webhook_latency(
    duration_ms: float,
    message_count: int,
    threshold_ms: int | None = None,
) -> None:
    limit = threshold_ms if threshold_ms is not None else get_settings().webhook_latency_alert_ms
    if duration_ms < limit:
        return
    emit_alert(
        "webhook_latency",
        "WhatsApp webhook latency exceeded threshold.",
        duration_ms=round(duration_ms, 2),
        threshold_ms=limit,
        message_count=message_count,
    )


def record_wa_delivery_failure(phone_number_id: str, status_code: int, error: str) -> None:
    emit_alert(
        "wa_delivery_failure",
        "WhatsApp delivery failed.",
        phone_number_id=phone_number_id,
        status_code=status_code,
        error=error[:500],
    )


def import_optional(module_name: str) -> ModuleType | None:
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


class SentryScope(Protocol):
    def __enter__(self) -> object: ...
    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool | None: ...
