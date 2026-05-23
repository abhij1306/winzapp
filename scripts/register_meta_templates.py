from __future__ import annotations

import asyncio

import httpx

GRAPH_API_TEMPLATE_URL = "https://graph.facebook.com/v18.0/{waba_id}/message_templates"


def build_template_payloads() -> list[dict[str, object]]:
    payloads = [
        template_payload(
            name="fasting_reminder",
            category="UTILITY",
            header_text="Fasting reminder",
            body_text="Kal ke test ke liye fasting zaroori hai. Kripya raat se fasting rakhein.",
        ),
        template_payload(
            name="report_ready",
            category="UTILITY",
            header_text="Report ready",
            body_text="Aapka test report ready hai. Hum secure PDF WhatsApp par bhej rahe hain.",
        ),
        template_payload(
            name="recall_reminder",
            category="MARKETING",
            header_text="Health check reminder",
            body_text="Aapka follow-up test due hai. Booking ke liye reply karein.",
        ),
        template_payload(
            name="review_request",
            category="MARKETING",
            header_text="Review request",
            body_text="Visit ke liye dhanyavaad. Kripya apna feedback is link par share karein.",
        ),
        template_payload(
            name="daily_digest",
            category="UTILITY",
            header_text="Daily digest",
            body_text=(
                "Daily summary: {{1}} tests booked, "
                "{{2}} reports pending, {{3}} reports sent."
            ),
            body_examples=[["28", "6", "22"]],
        ),
    ]
    validate_template_payloads(payloads)
    return payloads


def template_payload(
    name: str,
    category: str,
    header_text: str,
    body_text: str,
    body_examples: list[list[str]] | None = None,
) -> dict[str, object]:
    body_component: dict[str, object] = {"type": "BODY", "text": body_text}
    if body_examples is not None:
        body_component["example"] = {"body_text": body_examples}
    payload: dict[str, object] = {
        "name": name,
        "language": "en_US",
        "category": category,
        "components": [
            {"type": "HEADER", "format": "TEXT", "text": header_text},
            body_component,
        ],
    }
    return payload


def validate_template_payloads(payloads: list[dict[str, object]]) -> None:
    names = set()
    for payload in payloads:
        name = require_string(payload, "name")
        if name in names:
            raise ValueError(f"Duplicate template name: {name}")
        names.add(name)
        validate_template_category(payload, name)
        validate_template_components(payload, name)


def validate_template_category(payload: dict[str, object], name: str) -> None:
    category = require_string(payload, "category")
    if category not in {"UTILITY", "MARKETING", "AUTHENTICATION"}:
        raise ValueError(f"{name} has invalid category")


def validate_template_components(payload: dict[str, object], name: str) -> None:
    components = payload.get("components")
    if not isinstance(components, list) or not components:
        raise ValueError(f"{name} must define components")
    body_components = [
        component
        for component in components
        if isinstance(component, dict) and component.get("type") == "BODY"
    ]
    if len(body_components) != 1:
        raise ValueError(f"{name} must define exactly one BODY component")
    validate_body_examples(name, body_components[0])


def validate_body_examples(name: str, body_component: dict[str, object]) -> None:
    text = require_string(body_component, "text")
    has_variables = "{{" in text and "}}" in text
    if has_variables and "example" not in body_component:
        raise ValueError(f"{name} must include BODY examples for variables")


def require_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Template payload requires non-empty {key}")
    return value


async def register_templates(
    waba_id: str,
    access_token: str,
    dry_run: bool = True,
) -> dict[str, object]:
    payloads = build_template_payloads()
    validate_template_payloads(payloads)
    if dry_run:
        return {"dry_run": True, "template_count": len(payloads), "payloads": payloads}

    results: list[dict[str, object]] = []
    url = GRAPH_API_TEMPLATE_URL.format(waba_id=waba_id)
    async with httpx.AsyncClient() as client:
        for payload in payloads:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                json=payload,
            )
            response.raise_for_status()
            results.append(response.json())
    return {"dry_run": False, "template_count": len(payloads), "results": results}


async def main() -> None:
    result = await register_templates(waba_id="", access_token="", dry_run=True)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
