"""Интеграционные тесты автосвязывания guest-тикета с Customer по embed_host.

Идёт против запущенного backend (localhost:8000), как все остальные тесты
проекта — см. tests/test_customers.py для образца.

Запуск:
  docker exec site-pass24-servicedesk python -m pytest \\
      tests/test_guest_ticket_subdomain_match.py -v --tb=short

Проверяет три кейса:
  1. embed_host = bristol.pass24online.ru + Customer(subdomain='bristol',
     is_permanent_client=True) → ticket.customer_id / company / object_name
     заполнены.
  2. embed_host тот же, но Customer.is_permanent_client=False →
     match не происходит (с реестром не связан).
  3. embed_host = example.com (не наш домен) → match не происходит,
     никакой выборки в customers не падает.
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import select

pytestmark = pytest.mark.asyncio

BASE_URL = "http://localhost:8000"


# -----------------------------------------------------------------------
# Cleanup (паттерн из test_customers.py — TEST-префикс по ИНН/email)
# -----------------------------------------------------------------------

async def _cleanup_async() -> None:
    import asyncpg

    from backend.config import settings

    url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)
    try:
        # Удаляем тестовые тикеты (по creator_email паттерну) и тест-customers
        await conn.execute("""
            DELETE FROM ticket_events WHERE ticket_id IN (
                SELECT id FROM tickets WHERE contact_email LIKE 'guest-subdom-%@example.com'
            )
        """)
        await conn.execute("""
            DELETE FROM tickets WHERE contact_email LIKE 'guest-subdom-%@example.com'
        """)
        await conn.execute("""
            UPDATE users SET customer_id = NULL
            WHERE email LIKE 'guest-subdom-%@example.com'
        """)
        await conn.execute("""
            DELETE FROM users WHERE email LIKE 'guest-subdom-%@example.com'
        """)
        await conn.execute("DELETE FROM customers WHERE inn LIKE 'TESTSUBDOM%'")
    finally:
        await conn.close()


def _cleanup_sync() -> None:
    import concurrent.futures

    def _runner():
        return asyncio.new_event_loop().run_until_complete(_cleanup_async())

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_runner).result(timeout=30)


@pytest.fixture(scope="session", autouse=True)
def cleanup():
    try:
        _cleanup_sync()
    except Exception as e:
        print(f"[cleanup] pre-cleanup failed: {e}")
    yield
    try:
        _cleanup_sync()
    except Exception as e:
        print(f"[cleanup] post-cleanup failed: {e}")


@pytest.fixture(autouse=True)
def _isolate_db():
    import backend.database as db_mod
    from backend.config import settings

    engine = create_async_engine(settings.database_url, echo=False)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    original = db_mod.async_session_factory
    db_mod.async_session_factory = factory
    yield
    db_mod.async_session_factory = original


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(base_url=BASE_URL) as c:
        yield c


# -----------------------------------------------------------------------
# Хелперы
# -----------------------------------------------------------------------

async def _create_customer(
    inn: str, name: str, subdomain: str | None,
    is_permanent: bool = True, is_active: bool = True,
) -> str:
    """Создаёт Customer напрямую в БД, возвращает id."""
    from backend.customers.models import Customer
    from backend.database import async_session_factory

    async with async_session_factory() as session:
        customer = Customer(
            inn=inn, name=name, subdomain=subdomain,
            is_permanent_client=is_permanent, is_active=is_active,
        )
        session.add(customer)
        await session.commit()
        await session.refresh(customer)
        return customer.id


async def _fetch_ticket(ticket_id: str) -> dict:
    """Достаёт тикет напрямую из БД, чтобы проверить заполненные поля."""
    from backend.database import async_session_factory
    from backend.tickets.models import Ticket

    async with async_session_factory() as session:
        result = await session.execute(select(Ticket).where(Ticket.id == ticket_id))
        ticket = result.scalar_one()
        return {
            "customer_id": ticket.customer_id,
            "company": ticket.company,
            "object_name": ticket.object_name,
        }


def _email(slug: str) -> str:
    return f"guest-subdom-{slug}-{uuid.uuid4().hex[:6]}@example.com"


# -----------------------------------------------------------------------
# Тесты
# -----------------------------------------------------------------------

class TestSubdomainMatching:

    async def test_match_permanent_client(self, client):
        """embed_host = bristol.pass24online.ru → matched, customer_id выставлен."""
        cid = await _create_customer(
            inn="TESTSUBDOM01", name="ЖК Бристоль",
            subdomain="bristol", is_permanent=True, is_active=True,
        )
        r = await client.post("/tickets/guest", json={
            "email": _email("match"),
            "name": "Резидент",
            "title": "Не работает шлагбаум",
            "description": "Не открывается утром.",
            "embed_host": "bristol.pass24online.ru",
        })
        assert r.status_code == 201, r.text
        ticket_id = r.json()["ticket_id"]
        ticket = await _fetch_ticket(ticket_id)
        assert ticket["customer_id"] == cid
        assert ticket["company"] == "ЖК Бристоль"
        assert ticket["object_name"] == "ЖК Бристоль"

    async def test_payload_object_name_wins_over_customer(self, client):
        """Если payload явно указал object_name — его и сохраняем (не перезатираем)."""
        cid = await _create_customer(
            inn="TESTSUBDOM02", name="ЖК Бристоль 2",
            subdomain="bristol2", is_permanent=True, is_active=True,
        )
        r = await client.post("/tickets/guest", json={
            "email": _email("explicit-obj"),
            "title": "Тест",
            "description": "Тест",
            "object_name": "Корпус 5",
            "embed_host": "bristol2.pass24online.ru",
        })
        assert r.status_code == 201, r.text
        ticket = await _fetch_ticket(r.json()["ticket_id"])
        assert ticket["customer_id"] == cid
        assert ticket["company"] == "ЖК Бристоль 2"
        # object_name из payload приоритетнее имени Customer
        assert ticket["object_name"] == "Корпус 5"

    async def test_not_permanent_client_no_match(self, client):
        """Customer найден по subdomain, но is_permanent_client=False — match не происходит."""
        await _create_customer(
            inn="TESTSUBDOM03", name="Бывший клиент",
            subdomain="ex-client", is_permanent=False, is_active=True,
        )
        r = await client.post("/tickets/guest", json={
            "email": _email("not-permanent"),
            "title": "Тест",
            "description": "Тест",
            "embed_host": "ex-client.pass24online.ru",
        })
        assert r.status_code == 201, r.text
        ticket = await _fetch_ticket(r.json()["ticket_id"])
        assert ticket["customer_id"] is None
        assert ticket["company"] is None

    async def test_foreign_domain_no_match(self, client):
        """embed_host не из pass24online.ru — никакой выборки, customer_id остаётся None."""
        r = await client.post("/tickets/guest", json={
            "email": _email("foreign"),
            "title": "Тест",
            "description": "Тест",
            "embed_host": "example.com",
        })
        assert r.status_code == 201, r.text
        ticket = await _fetch_ticket(r.json()["ticket_id"])
        assert ticket["customer_id"] is None
        assert ticket["company"] is None

    async def test_no_embed_host_field(self, client):
        """Обратная совместимость: payload без embed_host работает как раньше."""
        r = await client.post("/tickets/guest", json={
            "email": _email("no-host"),
            "title": "Тест",
            "description": "Тест",
        })
        assert r.status_code == 201, r.text
        ticket = await _fetch_ticket(r.json()["ticket_id"])
        assert ticket["customer_id"] is None
        assert ticket["company"] is None

    async def test_subdomain_not_in_registry(self, client):
        """embed_host корректный, но в registry нет такого subdomain — без матча."""
        r = await client.post("/tickets/guest", json={
            "email": _email("missing"),
            "title": "Тест",
            "description": "Тест",
            "embed_host": "unknown-zhk.pass24online.ru",
        })
        assert r.status_code == 201, r.text
        ticket = await _fetch_ticket(r.json()["ticket_id"])
        assert ticket["customer_id"] is None
        assert ticket["company"] is None
