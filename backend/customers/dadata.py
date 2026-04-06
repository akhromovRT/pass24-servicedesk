"""Поиск компании по ИНН через DaData API.

DaData Suggestions API: https://dadata.ru/api/find-party/
Бесплатный тариф: 10 000 запросов/сутки.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

DADATA_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"


async def lookup_by_inn(inn: str) -> Optional[dict]:
    """Поиск компании по ИНН через DaData.

    Returns: { name, inn, kpp, ogrn, address, director, phone, email, type } or None
    """
    api_key = settings.dadata_api_key
    if not api_key:
        logger.warning("DADATA_API_KEY not set — lookup skipped")
        return None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                DADATA_URL,
                json={"query": inn, "count": 1},
                headers={
                    "Authorization": f"Token {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            r.raise_for_status()
            data = r.json()

        suggestions = data.get("suggestions", [])
        if not suggestions:
            return None

        s = suggestions[0]
        d = s.get("data", {})
        address_data = d.get("address", {}) or {}

        result = {
            "name": s.get("value", ""),
            "inn": d.get("inn", inn),
            "kpp": d.get("kpp", ""),
            "ogrn": d.get("ogrn", ""),
            "address": address_data.get("unrestricted_value") or address_data.get("value") or "",
            "director": "",
            "phone": "",
            "email": "",
            "type": d.get("type", ""),  # LEGAL / INDIVIDUAL
            "opf": d.get("opf", {}).get("short", ""),  # ООО, АО, ИП
            "status": d.get("state", {}).get("status", ""),  # ACTIVE / LIQUIDATED
        }

        # Директор
        management = d.get("management", {}) or {}
        result["director"] = management.get("name", "")

        # Телефоны и email из контактов (DaData может не отдавать)
        phones = d.get("phones", []) or []
        if phones:
            result["phone"] = phones[0].get("value", "")
        emails = d.get("emails", []) or []
        if emails:
            result["email"] = emails[0].get("value", "")

        return result

    except Exception as exc:
        logger.error("DaData lookup failed for INN %s: %s", inn, exc)
        return None
