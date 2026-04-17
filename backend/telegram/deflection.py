"""Thin wrapper around KB search for ticket-wizard deflection.

Kept as its own module so future logic (scoring, ML ranker, deflection
metrics) has a clean home without bloating kb_service. Task 8 intentionally
omits deflection tracking metrics — flag for a follow-up.
"""
from __future__ import annotations

from backend.telegram.services.kb_service import search_articles


async def suggest_articles(description: str) -> list[dict]:
    """Return top-3 KB articles relevant to the description. Empty list if none."""
    return await search_articles(description, limit=3)
