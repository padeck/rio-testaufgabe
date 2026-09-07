"""Ticket classification: a two-tier cascade.

1. OpenAI (if OPENAI_API_KEY is set and AI_PROVIDER allows it) — structured,
   schema-validated output.
2. A deterministic, keyword-based "simulated AI" — always succeeds, so the
   API never fails to classify a ticket even without any external service.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger("ai_service")

CATEGORIES = ["incident", "account_access", "billing", "how_to", "general"]
PRIORITIES = ["critical", "high", "medium", "low"]

TEAM_MAPPING = {
    "incident": "platform-operations",
    "account_access": "identity-operations",
    "billing": "finance-operations",
    "how_to": "customer-success",
    "general": "first-level-support",
}

# Bilingual (DE/EN) keyword lists with a weight per category/priority tier.
# Weight reflects how strongly a matched keyword indicates that bucket.
CATEGORY_KEYWORDS: dict[str, tuple[int, list[str]]] = {
    "incident": (4, [
        "down", "outage", "unavailable", "not working", "not reachable",
        "crash", "crashed", "broken", "unreachable", "offline",
        "ausfall", "nicht erreichbar", "abgestürzt", "störung",
        "funktioniert nicht", "offline", "produktivsystem",
    ]),
    "account_access": (3, [
        "locked", "log in", "login", "sign in", "password", "account locked",
        "authenticate", "2fa", "mfa",
        "gesperrt", "anmelden", "anmeldung", "passwort", "konto ist",
        "zugang", "login",
    ]),
    "billing": (3, [
        "invoice", "billing", "payment", "charge", "refund", "subscription",
        "billing address",
        "rechnung", "zahlung", "abrechnung", "rückerstattung", "abo",
        "rechnungsadresse",
    ]),
    "how_to": (2, [
        "how do i", "how can i", "how to", "guide", "instructions",
        "wie kann ich", "wie geht", "anleitung",
    ]),
}

PRIORITY_KEYWORDS: dict[str, tuple[int, list[str]]] = {
    "critical": (5, [
        "production", "critical", "urgent system", "outage", "unavailable",
        "produktiv", "produktivsystem", "kritisch", "nicht erreichbar",
        "ausfall",
    ]),
    "high": (4, [
        "cannot", "can't", "locked", "blocked", "unable to",
        "kann mich nicht", "kann nicht", "gesperrt", "blockiert", "dringend",
    ]),
    "low": (2, [
        "how do i", "how can i", "question", "wondering",
        "wie kann ich", "wie geht", "frage",
    ]),
}


@dataclass
class AnalysisResult:
    category: str
    priority: str
    assigned_team: str
    summary: str
    analysis_method: str  # "openai" | "simulated"


def _score(text: str, table: dict[str, tuple[int, list[str]]]) -> dict[str, int]:
    lowered = text.lower()
    scores: dict[str, int] = {}
    for bucket, (weight, keywords) in table.items():
        hits = sum(1 for kw in keywords if kw in lowered)
        if hits:
            scores[bucket] = weight * hits
    return scores


def _summarize(text: str, limit: int = 120) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def classify_rule_based(text: str) -> AnalysisResult:
    category_scores = _score(text, CATEGORY_KEYWORDS)
    category = max(category_scores, key=category_scores.get) if category_scores else "general"

    priority_scores = _score(text, PRIORITY_KEYWORDS)
    priority = max(priority_scores, key=priority_scores.get) if priority_scores else "medium"

    return AnalysisResult(
        category=category,
        priority=priority,
        assigned_team=TEAM_MAPPING[category],
        summary=_summarize(text),
        analysis_method="simulated",
    )


_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": CATEGORIES},
        "priority": {"type": "string", "enum": PRIORITIES},
        "assignedTeam": {"type": "string", "enum": list(TEAM_MAPPING.values())},
        "summary": {"type": "string"},
    },
    "required": ["category", "priority", "assignedTeam", "summary"],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = (
    "You classify customer support requests (which may be written in German "
    "or English). Respond with the classification only, following the "
    "provided JSON schema exactly.\n\n"
    "category: incident (system/service outage or malfunction), "
    "account_access (login/password/account lockout issues), "
    "billing (invoices, payments, billing address), "
    "how_to (a question about how to do something), "
    "general (anything else).\n"
    "priority: critical (production/business-critical outage), "
    "high (user is actively blocked from working), "
    "medium (a real but non-blocking problem), "
    "low (a question or minor request).\n"
    "assignedTeam: platform-operations (incident), identity-operations "
    "(account_access), finance-operations (billing), customer-success "
    "(how_to), first-level-support (general) — must match the category.\n"
    "summary: a concise English summary of the request, max 20 words."
)


def classify_openai(text: str) -> AnalysisResult | None:
    if not settings.openai_api_key:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "ticket_analysis",
                    "schema": _RESPONSE_SCHEMA,
                    "strict": True,
                },
            },
        )
        data = json.loads(response.choices[0].message.content)

        category = data["category"]
        if category not in CATEGORIES:
            return None
        priority = data["priority"]
        if priority not in PRIORITIES:
            return None

        return AnalysisResult(
            category=category,
            priority=priority,
            assigned_team=TEAM_MAPPING[category],
            summary=data.get("summary") or _summarize(text),
            analysis_method="openai",
        )
    except Exception:
        logger.exception("OpenAI classification failed; falling back")
        return None


def compute_status(category: str, priority: str) -> str:
    if priority == "critical":
        return "manual_review_required"
    if category == "incident" and priority == "high":
        return "manual_review_required"
    return "open"


def analyze(text: str) -> AnalysisResult:
    provider = settings.ai_provider.lower()

    if provider in ("auto", "openai"):
        result = classify_openai(text)
        if result is not None:
            return result
        if provider == "openai":
            logger.warning("AI_PROVIDER=openai but OpenAI call failed; using simulated fallback")

    return classify_rule_based(text)
