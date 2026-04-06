"""Синхронизация компаний и контактов с Bitrix24 CRM.

Bitrix24 REST API через webhook:
  - crm.company.list — получение компаний
  - crm.contact.list — получение контактов

ИНН компании (поле UF_CRM_*INN* или стандартное) — ключ синхронизации.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import httpx
from sqlmodel import select

from backend.config import settings
from backend.database import async_session_factory

from .models import Customer

logger = logging.getLogger(__name__)

# Bitrix24 поле с ИНН компании (нужно проверить на портале через get_entity_fields)
# Стандартных полей: TITLE, PHONE, EMAIL, ADDRESS, COMMENTS, INDUSTRY и т.д.
# ИНН обычно в кастомном UF_ поле. Попробуем несколько вариантов.
INN_FIELD_CANDIDATES = [
    "UF_CRM_INN",              # кастомное поле "ИНН"
    "UF_CRM_COMPANY_INN",      # вариант с префиксом
    "UF_CRM_1234567890123",    # автосгенерированное (нужно уточнить)
]


def _get_webhook_url() -> str:
    """Возвращает Bitrix24 webhook URL из настроек."""
    url = getattr(settings, "bitrix24_webhook_url", "") or ""
    if not url:
        raise ValueError("BITRIX24_WEBHOOK_URL не настроен")
    return url.rstrip("/")


async def _b24_call(method: str, params: dict | None = None) -> dict:
    """Вызов Bitrix24 REST API через webhook."""
    url = f"{_get_webhook_url()}/{method}"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=params or {})
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise Exception(f"Bitrix24 API error: {data['error']} — {data.get('error_description', '')}")
        return data


async def _b24_list_all(method: str, select_fields: list[str] | None = None) -> list[dict]:
    """Получение ВСЕХ записей через ID-based пагинацию."""
    items = []
    last_id = 0
    while True:
        params: dict = {
            "filter": {">ID": last_id},
            "order": {"ID": "ASC"},
            "start": -1,
        }
        if select_fields:
            params["select"] = select_fields
        data = await _b24_call(method, params)
        batch = data.get("result", [])
        if not batch:
            break
        items.extend(batch)
        last_id = int(batch[-1]["ID"])
        if len(batch) < 50:
            break
    return items


async def discover_inn_field() -> Optional[str]:
    """Определяет имя поля ИНН на портале Bitrix24."""
    try:
        data = await _b24_call("crm.company.fields")
        fields = data.get("result", {})

        # Ищем поле с "инн" или "inn" в title
        for field_id, info in fields.items():
            title = (info.get("formLabel") or info.get("title") or "").lower()
            if "инн" in title or "inn" in title:
                logger.info("Found INN field: %s (%s)", field_id, title)
                return field_id

        # Пробуем кандидатов
        for candidate in INN_FIELD_CANDIDATES:
            if candidate in fields:
                logger.info("Found INN field by candidate: %s", candidate)
                return candidate

        logger.warning("INN field not found in Bitrix24 company fields. Available UF_* fields: %s",
                       [k for k in fields if k.startswith("UF_")])
        return None
    except Exception as exc:
        logger.error("Cannot discover INN field: %s", exc)
        return None


async def _load_inn_map() -> dict[int, str]:
    """Загружает маппинг company_id → ИНН из crm.requisite.list."""
    inn_map: dict[int, str] = {}
    last_id = 0
    while True:
        data = await _b24_call("crm.requisite.list", {
            "select": ["ID", "ENTITY_ID", "ENTITY_TYPE_ID", "RQ_INN"],
            "filter": {"ENTITY_TYPE_ID": 4, ">ID": last_id},  # 4 = company
            "order": {"ID": "ASC"},
            "start": -1,
        })
        batch = data.get("result", [])
        if not batch:
            break
        for r in batch:
            inn = (r.get("RQ_INN") or "").strip()
            if inn:
                inn_map[int(r["ENTITY_ID"])] = inn
        last_id = int(batch[-1]["ID"])
        if len(batch) < 50:
            break
    return inn_map


async def sync_companies(inn_field: Optional[str] = None) -> dict:
    """Синхронизация компаний из Bitrix24 → Customer.

    ИНН берётся из crm.requisite.list (RQ_INN), привязывается по company_id.

    Returns: { "created": N, "updated": N, "skipped_no_inn": N, "total": N }
    """
    # Загружаем маппинг company_id → ИНН из реквизитов
    inn_map = await _load_inn_map()
    logger.info("Loaded %d INN records from requisites", len(inn_map))

    # Загружаем все компании
    companies = await _b24_list_all("crm.company.list", [
        "ID", "TITLE", "PHONE", "EMAIL", "ADDRESS", "COMMENTS", "INDUSTRY",
    ])
    logger.info("Loaded %d companies from Bitrix24", len(companies))

    stats = {"created": 0, "updated": 0, "skipped_no_inn": 0, "total": len(companies)}

    async with async_session_factory() as session:
        for c in companies:
            b24_id = int(c["ID"])
            inn_val = inn_map.get(b24_id, "").strip()

            if not inn_val:
                stats["skipped_no_inn"] += 1
                continue

            name = c.get("TITLE", "").strip()
            address = c.get("ADDRESS", "")
            comment = c.get("COMMENTS", "")
            industry = c.get("INDUSTRY", "")

            # Телефон / Email — массив в Bitrix24
            phone = ""
            if isinstance(c.get("PHONE"), list) and c["PHONE"]:
                phone = c["PHONE"][0].get("VALUE", "")
            email_val = ""
            if isinstance(c.get("EMAIL"), list) and c["EMAIL"]:
                email_val = c["EMAIL"][0].get("VALUE", "")

            # Ищем по ИНН
            r = await session.execute(select(Customer).where(Customer.inn == inn_val))
            existing = r.scalar_one_or_none()

            if existing:
                existing.name = name or existing.name
                existing.bitrix24_company_id = b24_id
                existing.address = address or existing.address
                existing.phone = phone or existing.phone
                existing.email = email_val or existing.email
                existing.industry = industry or existing.industry
                existing.comment = comment or existing.comment
                existing.synced_at = datetime.utcnow()
                existing.updated_at = datetime.utcnow()
                session.add(existing)
                stats["updated"] += 1
            else:
                customer = Customer(
                    inn=inn_val,
                    name=name,
                    bitrix24_company_id=b24_id,
                    address=address,
                    phone=phone,
                    email=email_val,
                    industry=industry,
                    comment=comment,
                    synced_at=datetime.utcnow(),
                )
                session.add(customer)
                stats["created"] += 1

        await session.commit()

    logger.info("Sync result: %s", stats)
    return stats


async def sync_contacts(inn_field: Optional[str] = None) -> dict:
    """Синхронизация контактов из Bitrix24 → Users (property_manager).

    Привязка к Customer через company_id в Bitrix24 → Customer.bitrix24_company_id.

    Returns: { "created": N, "updated": N, "skipped_no_company": N, "total": N }
    """
    from backend.auth.models import User, UserRole
    from backend.auth.utils import hash_password
    import uuid

    # Загружаем все контакты
    contacts = await _b24_list_all("crm.contact.list", [
        "ID", "NAME", "LAST_NAME", "SECOND_NAME", "PHONE", "EMAIL",
        "COMPANY_ID", "COMMENTS", "POST",
    ])
    logger.info("Loaded %d contacts from Bitrix24", len(contacts))

    stats = {"created": 0, "updated": 0, "skipped_no_company": 0, "skipped_no_email": 0, "total": len(contacts)}

    async with async_session_factory() as session:
        # Кэш: bitrix24_company_id → customer_id
        r = await session.execute(
            select(Customer.bitrix24_company_id, Customer.id).where(Customer.bitrix24_company_id.is_not(None))
        )
        b24_to_customer = {row[0]: row[1] for row in r.all()}

        for c in contacts:
            company_b24_id = c.get("COMPANY_ID")
            if not company_b24_id or int(company_b24_id) == 0:
                stats["skipped_no_company"] += 1
                continue

            customer_id = b24_to_customer.get(int(company_b24_id))
            if not customer_id:
                stats["skipped_no_company"] += 1
                continue

            # Email
            email_val = ""
            if isinstance(c.get("EMAIL"), list) and c["EMAIL"]:
                email_val = c["EMAIL"][0].get("VALUE", "").strip().lower()
            if not email_val:
                stats["skipped_no_email"] += 1
                continue

            full_name = " ".join(filter(None, [
                c.get("LAST_NAME", ""),
                c.get("NAME", ""),
                c.get("SECOND_NAME", ""),
            ])).strip() or email_val

            # Ищем пользователя по email
            ur = await session.execute(select(User).where(User.email == email_val))
            user = ur.scalar_one_or_none()

            if user:
                user.full_name = full_name or user.full_name
                user.customer_id = customer_id
                session.add(user)
                stats["updated"] += 1
            else:
                user = User(
                    email=email_val,
                    hashed_password=hash_password(uuid.uuid4().hex[:16]),
                    full_name=full_name,
                    role=UserRole.PROPERTY_MANAGER,
                    customer_id=customer_id,
                )
                session.add(user)
                stats["created"] += 1

        await session.commit()

    logger.info("Contact sync result: %s", stats)
    return stats
