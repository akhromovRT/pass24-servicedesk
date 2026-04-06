"""Поиск компании по ИНН и по названию через DaData API.

DaData Suggestions API: https://dadata.ru/api/find-party/
Бесплатный тариф: 10 000 запросов/сутки.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

DADATA_FIND_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"
DADATA_SUGGEST_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/party"


def _headers() -> dict:
    return {
        "Authorization": f"Token {settings.dadata_api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _parse_suggestion(s: dict) -> dict:
    """Преобразует raw suggestion в плоский dict."""
    d = s.get("data", {})
    address_data = d.get("address", {}) or {}
    management = d.get("management", {}) or {}

    result = {
        "name": s.get("value", ""),
        "inn": d.get("inn", ""),
        "kpp": d.get("kpp", ""),
        "ogrn": d.get("ogrn", ""),
        "address": address_data.get("unrestricted_value") or address_data.get("value") or "",
        "director": management.get("name", ""),
        "phone": "",
        "email": "",
        "type": d.get("type", ""),
        "opf": d.get("opf", {}).get("short", ""),
        "status": d.get("state", {}).get("status", ""),
    }

    phones = d.get("phones", []) or []
    if phones:
        result["phone"] = phones[0].get("value", "")
    emails = d.get("emails", []) or []
    if emails:
        result["email"] = emails[0].get("value", "")

    return result


async def lookup_by_inn(inn: str) -> Optional[dict]:
    """Поиск компании по ИНН через DaData (findById)."""
    if not settings.dadata_api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(DADATA_FIND_URL, json={"query": inn, "count": 1}, headers=_headers())
            r.raise_for_status()
            suggestions = r.json().get("suggestions", [])
            return _parse_suggestion(suggestions[0]) if suggestions else None
    except Exception as exc:
        logger.error("DaData lookup failed for INN %s: %s", inn, exc)
        return None


async def search_by_name(query: str, count: int = 5) -> list[dict]:
    """Поиск компаний по названию через DaData (suggest).

    Возвращает до `count` результатов.
    """
    if not settings.dadata_api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                DADATA_SUGGEST_URL,
                json={"query": query, "count": count, "status": ["ACTIVE"]},
                headers=_headers(),
            )
            r.raise_for_status()
            return [_parse_suggestion(s) for s in r.json().get("suggestions", [])]
    except Exception as exc:
        logger.error("DaData search failed for '%s': %s", query, exc)
        return []
