from types import SimpleNamespace

from pytest import MonkeyPatch

from app.services import observability


def test_configure_observability_initializes_enabled_providers(monkeypatch: MonkeyPatch) -> None:
    sentry_calls: list[dict[str, object]] = []
    logfire_calls: list[dict[str, object]] = []

    sentry = SimpleNamespace(init=lambda **kwargs: sentry_calls.append(kwargs))
    logfire = SimpleNamespace(configure=lambda **kwargs: logfire_calls.append(kwargs))

    def fake_import(module_name: str) -> SimpleNamespace | None:
        return {"sentry_sdk": sentry, "logfire": logfire}.get(module_name)

    monkeypatch.setattr(observability, "import_optional", fake_import)
    settings = SimpleNamespace(
        app_env="production",
        app_name="WhatsApp Clinic Suite",
        sentry_dsn="https://sentry.example/1",
        logfire_token="logfire-token",
        observability_alerts_enabled=True,
    )

    configured = observability.configure_observability(settings)

    assert configured == ["sentry", "logfire"]
    assert sentry_calls[0]["environment"] == "production"
    assert sentry_calls[0]["send_default_pii"] is False
    assert logfire_calls[0]["service_name"] == "WhatsApp Clinic Suite"


def test_record_webhook_latency_emits_threshold_alert(monkeypatch: MonkeyPatch) -> None:
    alerts: list[dict[str, object]] = []

    def fake_alert(alert_type: str, message: str, **fields: object) -> None:
        alerts.append({"alert_type": alert_type, "message": message, **fields})

    monkeypatch.setattr(observability, "emit_alert", fake_alert)

    observability.record_webhook_latency(20_500, message_count=2, threshold_ms=15_000)

    assert alerts == [
        {
            "alert_type": "webhook_latency",
            "message": "WhatsApp webhook latency exceeded threshold.",
            "duration_ms": 20500,
            "threshold_ms": 15000,
            "message_count": 2,
        },
    ]


def test_emit_alert_respects_disabled_alerts(monkeypatch: MonkeyPatch) -> None:
    warnings: list[tuple[object, ...]] = []

    monkeypatch.setattr(
        observability,
        "get_settings",
        lambda: SimpleNamespace(observability_alerts_enabled=False),
    )
    monkeypatch.setattr(
        observability.logger,
        "warning",
        lambda *args, **_kwargs: warnings.append(args),
    )

    observability.emit_alert("wa_delivery_failure", "Delivery failed.")

    assert warnings == []
