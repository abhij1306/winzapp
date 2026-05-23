from __future__ import annotations

import asyncio

import httpx

GRAPH_API_TEMPLATE_URL = "https://graph.facebook.com/v18.0/{waba_id}/message_templates"


def build_template_payloads() -> list[dict[str, object]]:
    return [
        template_payload(
            "fasting_reminder",
            "Fasting reminder",
            "Please keep fasting before your scheduled test tomorrow morning.",
        ),
        template_payload(
            "report_ready",
            "Report ready",
            "Your test report is ready. We are sending the secure PDF link on WhatsApp.",
        ),
        template_payload(
            "recall_reminder",
            "Health check reminder",
            "It is time for your recommended follow-up test. Reply to book a slot.",
        ),
        template_payload(
            "review_request",
            "Review request",
            "Thank you for visiting us. Please share your feedback with this link.",
        ),
        template_payload(
            "daily_digest",
            "Daily digest",
            "Daily summary: {{1}} tests booked, {{2}} reports pending, {{3}} reports sent.",
        ),
    ]


def template_payload(name: str, body_text: str, body: str) -> dict[str, object]:
    return {
        "name": name,
        "language": "en_US",
        "category": "UTILITY",
        "components": [
            {"type": "HEADER", "format": "TEXT", "text": body_text},
            {"type": "BODY", "text": body},
        ],
    }


async def register_templates(
    waba_id: str,
    access_token: str,
    dry_run: bool = True,
) -> dict[str, object]:
    payloads = build_template_payloads()
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
