from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import llm_service
from app.services.cache import get_clinic_by_id_cached
from app.services.feature_flags import get_features

DiagnosticIntent = Literal[
    "test_booking",
    "report_inquiry",
    "home_collection",
    "cancel",
    "admin",
    "unknown",
]
IntentSource = Literal["rule", "llm"]
KNOWN_DIAGNOSTIC_INTENTS: set[str] = {
    "test_booking",
    "report_inquiry",
    "home_collection",
    "cancel",
    "admin",
    "unknown",
}
APPOINTMENT_WORDS = {"appointment", "doctor", "consultation", "slot"}


@dataclass(frozen=True)
class IntentResult:
    intent: DiagnosticIntent
    source: IntentSource
    matched_terms: tuple[str, ...] = ()


async def classify_diagnostics_intent(
    message_text: str,
    clinic_id: str,
    db: AsyncSession,
    is_admin: bool = False,
) -> IntentResult:
    rule_result = classify_with_rules(message_text, is_admin=is_admin)
    if rule_result.intent != "unknown":
        return rule_result
    if is_diagnostics_scope_rejection(rule_result):
        return rule_result

    if not await llm_fallback_enabled(clinic_id, db):
        return rule_result

    llm_intent = await llm_service.classify_intent(
        message_text,
        {"clinic_id": clinic_id},
    )
    return IntentResult(intent=normalize_llm_intent(llm_intent), source="llm")


def classify_with_rules(message_text: str, is_admin: bool) -> IntentResult:
    words = tokenize(message_text)
    if is_admin and has_any(words, {"today", "aaj", "pending", "digest", "stats", "send"}):
        return IntentResult(intent="admin", source="rule", matched_terms=tuple(sorted(words)))

    if APPOINTMENT_WORDS & words:
        return IntentResult(intent="unknown", source="rule", matched_terms=tuple(sorted(words)))

    if has_phrase(message_text, ("home collection", "sample collection")) or has_any(
        words,
        {"home", "ghar", "collection", "sample"},
    ):
        return IntentResult(
            intent="home_collection",
            source="rule",
            matched_terms=tuple(sorted(words)),
        )

    if has_any(words, {"cancel", "cancellation", "stop", "delete", "radd"}):
        return IntentResult(intent="cancel", source="rule", matched_terms=tuple(sorted(words)))

    if has_any(words, {"report", "reports", "result", "pdf", "ready"}):
        return IntentResult(
            intent="report_inquiry",
            source="rule",
            matched_terms=tuple(sorted(words)),
        )

    if has_any(words, {"test", "tests", "cbc", "hba1c", "thyroid", "blood", "book"}):
        return IntentResult(
            intent="test_booking",
            source="rule",
            matched_terms=tuple(sorted(words)),
        )

    return IntentResult(intent="unknown", source="rule")


def tokenize(message_text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9]+", message_text.lower()))


def has_any(words: set[str], candidates: set[str]) -> bool:
    return bool(words & candidates)


def has_phrase(message_text: str, phrases: tuple[str, ...]) -> bool:
    normalized = message_text.lower()
    return any(phrase in normalized for phrase in phrases)


def is_diagnostics_scope_rejection(result: IntentResult) -> bool:
    return bool(set(result.matched_terms) & APPOINTMENT_WORDS)


async def llm_fallback_enabled(clinic_id: str, db: AsyncSession) -> bool:
    clinic = await get_clinic_by_id_cached(clinic_id, db)
    return get_features(clinic).get("llm_intent_fallback") is True


def normalize_llm_intent(intent: str) -> DiagnosticIntent:
    normalized = intent.strip().lower()
    if normalized in KNOWN_DIAGNOSTIC_INTENTS and normalized != "appointment":
        return normalized  # type: ignore[return-value]
    return "unknown"
