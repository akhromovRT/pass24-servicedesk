"""
Тесты модуля компаний-клиентов (backend/customers/).

Покрытие:
  - Customer CRUD: список, поиск, получение, создание (ручное + по ИНН)
  - RBAC: агент/админ/PM/резидент — разные уровни доступа
  - DaData: mock lookup_by_inn, search_by_name
  - Bitrix24 sync: RBAC (только админ)
  - Контакты компании

Запуск:
  docker exec site-pass24-servicedesk python -m pytest tests/test_customers.py -v --tb=short
"""
from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.asyncio

BASE_URL = "http://localhost:8000"
TEST_EMAIL_DOMAIN = "@example.com"


# ---------------------------------------------------------------------------
# Fixtures (аналогичны test_full_suite.py)
# ---------------------------------------------------------------------------

async def _cleanup_test_data_async() -> int:
    import asyncpg
    from backend.config import settings
    url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)
    try:
        pattern = f"%{TEST_EMAIL_DOMAIN}"
        # Удаляем тестовых клиентов (customers)
        await conn.execute("""
            UPDATE users SET customer_id = NULL WHERE email LIKE $1
        """, pattern)
        await conn.execute("""
            DELETE FROM customers WHERE inn LIKE 'TEST%'
        """)
        # Удаляем тестовых юзеров (стандартная очистка)
        await conn.execute("""
            DELETE FROM ticket_comments WHERE author_id IN (
                SELECT id::text FROM users WHERE email LIKE $1
            )
        """, pattern)
        await conn.execute("""
            DELETE FROM tickets WHERE creator_id IN (
                SELECT id::text FROM users WHERE email LIKE $1
            )
        """, pattern)
        result = await conn.execute("DELETE FROM users WHERE email LIKE $1", pattern)
        try:
            deleted = int(result.split()[-1])
        except Exception:
            deleted = 0
        return deleted
    finally:
        await conn.close()


def _cleanup_test_data_sync() -> int:
    import concurrent.futures
    def _runner():
        return asyncio.new_event_loop().run_until_complete(_cleanup_test_data_async())
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_runner).result(timeout=30)


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data():
    try:
        removed = _cleanup_test_data_sync()
        print(f"\n[cleanup] Removed {removed} test users before session")
    except Exception as e:
        print(f"\n[cleanup] Pre-cleanup failed: {e}")
    yield
    try:
        removed = _cleanup_test_data_sync()
        print(f"\n[cleanup] Removed {removed} test users after session")
    except Exception as e:
        print(f"\n[cleanup] Post-cleanup failed: {e}")


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


def _email(prefix: str = "cust") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


async def _register(client: AsyncClient, email: str, password: str = "pass123456",
                    name: str = "Test", role: str = "resident") -> dict:
    r = await client.post("/auth/register", json={
        "email": email, "password": password, "full_name": name, "role": role,
    })
    return r.json()


async def _login(client: AsyncClient, email: str, password: str = "pass123456") -> str:
    r = await client.post("/auth/login", json={"email": email, "password": password})
    return r.json()["access_token"]


async def _auth_headers(client: AsyncClient, email: str, password: str = "pass123456",
                        name: str = "Test", role: str = "resident") -> dict:
    await _register(client, email, password, name, role)
    token = await _login(client, email, password)
    return {"Authorization": f"Bearer {token}"}


async def _create_agent(client: AsyncClient) -> tuple[str, dict]:
    email = _email("agent")
    await _register(client, email, "pass123456", "Agent Test", "resident")
    from backend.database import async_session_factory
    from backend.auth.models import User
    from sqlmodel import select
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        user.role = "support_agent"
        session.add(user)
        await session.commit()
    token = await _login(client, email)
    return email, {"Authorization": f"Bearer {token}"}


async def _create_admin(client: AsyncClient) -> tuple[str, dict]:
    email = _email("admin")
    await _register(client, email, "pass123456", "Admin Test", "resident")
    from backend.database import async_session_factory
    from backend.auth.models import User
    from sqlmodel import select
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        user.role = "admin"
        session.add(user)
        await session.commit()
    token = await _login(client, email)
    return email, {"Authorization": f"Bearer {token}"}


async def _create_customer_in_db(inn: str, name: str) -> str:
    """Создаёт Customer напрямую в БД, возвращает id."""
    from backend.database import async_session_factory
    from backend.customers.models import Customer
    async with async_session_factory() as session:
        customer = Customer(inn=inn, name=name)
        session.add(customer)
        await session.commit()
        await session.refresh(customer)
        return customer.id


async def _link_user_to_customer(email: str, customer_id: str):
    """Привязывает пользователя к компании по email."""
    from backend.database import async_session_factory
    from backend.auth.models import User
    from sqlmodel import select
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        user.customer_id = customer_id
        session.add(user)
        await session.commit()


# =====================================================================
# 1. CUSTOMER LIST — RBAC
# =====================================================================

class TestCustomerListRBAC:
    """Тесты доступа к списку компаний по ролям."""

    async def test_agent_sees_all_customers(self, client):
        """Агент видит всех клиентов."""
        cid = await _create_customer_in_db("TEST0000000001", "ООО Тестовая Компания")
        _, agent_headers = await _create_agent(client)

        r = await client.get("/customers/", headers=agent_headers)
        assert r.status_code == 200
        data = r.json()
        # Агент видит как минимум созданную компанию
        inns = [c["inn"] for c in data]
        assert "TEST0000000001" in inns

    async def test_admin_sees_all_customers(self, client):
        """Админ видит всех клиентов."""
        cid = await _create_customer_in_db("TEST0000000002", "ООО Админская")
        _, admin_headers = await _create_admin(client)

        r = await client.get("/customers/", headers=admin_headers)
        assert r.status_code == 200
        inns = [c["inn"] for c in r.json()]
        assert "TEST0000000002" in inns

    async def test_pm_sees_only_own_customer(self, client):
        """Property Manager видит только свою компанию."""
        cid = await _create_customer_in_db("TEST0000000003", "ООО Моя УК")
        other_cid = await _create_customer_in_db("TEST0000000004", "ООО Чужая УК")

        pm_email = _email("pm")
        await _auth_headers(client, pm_email, role="property_manager")
        await _link_user_to_customer(pm_email, cid)
        token = await _login(client, pm_email)
        pm_headers = {"Authorization": f"Bearer {token}"}

        r = await client.get("/customers/", headers=pm_headers)
        assert r.status_code == 200
        data = r.json()
        inns = [c["inn"] for c in data]
        assert "TEST0000000003" in inns
        assert "TEST0000000004" not in inns

    async def test_resident_sees_empty_list(self, client):
        """Резидент не видит компаний."""
        await _create_customer_in_db("TEST0000000005", "ООО Невидимая")
        resident_headers = await _auth_headers(client, _email("res"), role="resident")

        r = await client.get("/customers/", headers=resident_headers)
        assert r.status_code == 200
        assert r.json() == []

    async def test_unauthenticated_401(self, client):
        """Без авторизации — 401."""
        r = await client.get("/customers/")
        assert r.status_code == 401


# =====================================================================
# 2. CUSTOMER SEARCH
# =====================================================================

class TestCustomerSearch:
    """Поиск компаний по названию/ИНН."""

    async def test_search_by_name(self, client):
        await _create_customer_in_db("TEST1000000001", "ООО Альфа Тех")
        _, agent_headers = await _create_agent(client)

        r = await client.get("/customers/search", params={"q": "Альфа"}, headers=agent_headers)
        assert r.status_code == 200
        data = r.json()
        assert any(c["inn"] == "TEST1000000001" for c in data)

    async def test_search_by_inn(self, client):
        await _create_customer_in_db("TEST1000000002", "ООО Бета")
        _, agent_headers = await _create_agent(client)

        r = await client.get("/customers/search", params={"q": "TEST1000000002"}, headers=agent_headers)
        assert r.status_code == 200
        data = r.json()
        assert any(c["inn"] == "TEST1000000002" for c in data)

    async def test_search_empty_result(self, client):
        _, agent_headers = await _create_agent(client)
        r = await client.get("/customers/search", params={"q": "НЕСУЩЕСТВУЮЩЕЕ999"}, headers=agent_headers)
        assert r.status_code == 200
        assert r.json() == []


# =====================================================================
# 3. GET CUSTOMER
# =====================================================================

class TestGetCustomer:
    async def test_get_existing_customer(self, client):
        cid = await _create_customer_in_db("TEST2000000001", "ООО Гамма")
        _, agent_headers = await _create_agent(client)

        r = await client.get(f"/customers/{cid}", headers=agent_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["inn"] == "TEST2000000001"
        assert data["name"] == "ООО Гамма"

    async def test_get_nonexistent_customer(self, client):
        _, agent_headers = await _create_agent(client)
        r = await client.get("/customers/nonexistent-uuid", headers=agent_headers)
        assert r.status_code == 404


# =====================================================================
# 4. CREATE CUSTOMER (ручное)
# =====================================================================

class TestCreateCustomer:
    async def test_agent_creates_customer(self, client):
        _, agent_headers = await _create_agent(client)
        r = await client.post("/customers/", json={
            "inn": "TEST3000000001",
            "name": "ООО Дельта",
            "address": "Москва, ул. Тестовая, 1",
            "phone": "+7 (999) 123-45-67",
        }, headers=agent_headers)
        assert r.status_code == 201
        data = r.json()
        assert data["inn"] == "TEST3000000001"
        assert data["name"] == "ООО Дельта"
        assert data["address"] == "Москва, ул. Тестовая, 1"

    async def test_duplicate_inn_returns_409(self, client):
        await _create_customer_in_db("TEST3000000002", "ООО Дубликат Раз")
        _, agent_headers = await _create_agent(client)

        r = await client.post("/customers/", json={
            "inn": "TEST3000000002",
            "name": "ООО Дубликат Два",
        }, headers=agent_headers)
        assert r.status_code == 409

    async def test_resident_cannot_create_customer(self, client):
        resident_headers = await _auth_headers(client, _email("res"), role="resident")
        r = await client.post("/customers/", json={
            "inn": "TEST3000000003",
            "name": "ООО Нет Доступа",
        }, headers=resident_headers)
        assert r.status_code == 403

    async def test_pm_cannot_create_customer(self, client):
        pm_headers = await _auth_headers(client, _email("pm"), role="property_manager")
        r = await client.post("/customers/", json={
            "inn": "TEST3000000004",
            "name": "ООО Нет Доступа PM",
        }, headers=pm_headers)
        assert r.status_code == 403


# =====================================================================
# 5. CREATE CUSTOMER BY INN (DaData)
# =====================================================================

class TestCreateByINN:
    async def test_create_by_inn_with_dadata(self, client):
        """Создание компании по ИНН — DaData возвращает реальные данные (Газпром)."""
        _, agent_headers = await _create_agent(client)

        # Используем реальный ИНН Газпрома — стабильные данные из ФНС
        r = await client.post(
            "/customers/create-by-inn",
            params={"inn": "7736050003"},
            headers=agent_headers,
        )
        assert r.status_code in (200, 201)  # 200 если уже существует, 201 если создан
        data = r.json()
        assert data["inn"] == "7736050003"
        assert len(data["name"]) > 0  # DaData вернёт название

    async def test_create_by_inn_already_exists(self, client):
        """Если компания с таким ИНН уже есть — возвращает существующую."""
        await _create_customer_in_db("TEST4000000002", "ООО Уже Есть")
        _, agent_headers = await _create_agent(client)

        r = await client.post(
            "/customers/create-by-inn",
            params={"inn": "TEST4000000002"},
            headers=agent_headers,
        )
        # Возвращает 200 (существующую запись — не 201)
        assert r.status_code in (200, 201)
        data = r.json()
        assert data["inn"] == "TEST4000000002"
        assert data["name"] == "ООО Уже Есть"

    async def test_create_by_inn_dadata_not_found(self, client):
        """DaData не нашла компанию — создаётся с fallback-именем."""
        _, agent_headers = await _create_agent(client)

        with patch("backend.customers.dadata.lookup_by_inn", new_callable=AsyncMock,
                    return_value=None):
            r = await client.post(
                "/customers/create-by-inn",
                params={"inn": "TEST4000000003"},
                headers=agent_headers,
            )
            assert r.status_code == 201
            data = r.json()
            assert data["inn"] == "TEST4000000003"
            assert "TEST4000000003" in data["name"]  # fallback: "Компания ИНН ..."

    async def test_resident_cannot_create_by_inn(self, client):
        resident_headers = await _auth_headers(client, _email("res"), role="resident")
        r = await client.post(
            "/customers/create-by-inn",
            params={"inn": "TEST4000000004"},
            headers=resident_headers,
        )
        assert r.status_code == 403


# =====================================================================
# 6. DADATA ENDPOINTS (mocked)
# =====================================================================

class TestDaDataEndpoints:
    async def test_lookup_inn_found(self, client):
        """Поиск по реальному ИНН (Сбербанк) — DaData возвращает данные."""
        _, agent_headers = await _create_agent(client)

        r = await client.get("/customers/lookup-inn/7707083893", headers=agent_headers)
        assert r.status_code == 200
        data = r.json()
        assert "сбер" in data["name"].lower() or "sber" in data["name"].lower()
        assert data["inn"] == "7707083893"

    async def test_lookup_inn_not_found(self, client):
        """Несуществующий ИНН — 404."""
        _, agent_headers = await _create_agent(client)

        r = await client.get("/customers/lookup-inn/0000000000", headers=agent_headers)
        assert r.status_code == 404

    async def test_dadata_search(self, client):
        """Поиск по названию через DaData — реальный запрос."""
        _, agent_headers = await _create_agent(client)

        r = await client.get("/customers/dadata-search", params={"q": "Сбербанк"}, headers=agent_headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        # Среди результатов должен быть Сбербанк
        assert any("сбер" in item.get("name", "").lower() for item in data)


# =====================================================================
# 7. CONTACTS
# =====================================================================

class TestCustomerContacts:
    async def test_get_contacts_for_customer(self, client):
        cid = await _create_customer_in_db("TEST5000000001", "ООО С Контактами")
        # Создаём PM и привязываем к компании
        pm_email = _email("contact-pm")
        await _register(client, pm_email, "pass123456", "Контакт ПМ", "property_manager")
        await _link_user_to_customer(pm_email, cid)

        _, agent_headers = await _create_agent(client)

        r = await client.get(f"/customers/{cid}/contacts", headers=agent_headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        emails = [c["email"] for c in data]
        assert pm_email in emails

    async def test_get_contacts_empty(self, client):
        cid = await _create_customer_in_db("TEST5000000002", "ООО Без Контактов")
        _, agent_headers = await _create_agent(client)

        r = await client.get(f"/customers/{cid}/contacts", headers=agent_headers)
        assert r.status_code == 200
        assert r.json() == []


# =====================================================================
# 8. BITRIX24 SYNC — RBAC
# =====================================================================

class TestBitrix24Sync:
    async def test_sync_admin_only(self, client):
        """Только админ может запускать синхронизацию."""
        _, admin_headers = await _create_admin(client)

        with patch("backend.customers.bitrix24_sync.sync_companies", new_callable=AsyncMock, return_value={}), \
             patch("backend.customers.bitrix24_sync.sync_contacts", new_callable=AsyncMock, return_value={}):
            r = await client.post("/customers/sync", headers=admin_headers)
            assert r.status_code == 200
            data = r.json()
            assert data["status"] == "sync_started"

    async def test_sync_agent_forbidden(self, client):
        _, agent_headers = await _create_agent(client)
        r = await client.post("/customers/sync", headers=agent_headers)
        assert r.status_code == 403

    async def test_sync_resident_forbidden(self, client):
        resident_headers = await _auth_headers(client, _email("res"), role="resident")
        r = await client.post("/customers/sync", headers=resident_headers)
        assert r.status_code == 403


# =====================================================================
# 9. DADATA UNIT TESTS (функции)
# =====================================================================

class TestDaDataFunctions:
    """Unit-тесты для функций dadata.py с мокнутым httpx."""

    async def test_parse_suggestion(self):
        from backend.customers.dadata import _parse_suggestion
        suggestion = {
            "value": "ООО Тест",
            "data": {
                "inn": "1234567890",
                "kpp": "123456789",
                "ogrn": "1234567890123",
                "address": {"unrestricted_value": "г Москва"},
                "management": {"name": "Директор Тест"},
                "type": "LEGAL",
                "opf": {"short": "ООО"},
                "state": {"status": "ACTIVE"},
                "phones": [{"value": "+7 999 000 0000"}],
                "emails": [{"value": "test@test.ru"}],
            },
        }
        result = _parse_suggestion(suggestion)
        assert result["name"] == "ООО Тест"
        assert result["inn"] == "1234567890"
        assert result["kpp"] == "123456789"
        assert result["address"] == "г Москва"
        assert result["director"] == "Директор Тест"
        assert result["phone"] == "+7 999 000 0000"
        assert result["email"] == "test@test.ru"
        assert result["opf"] == "ООО"
        assert result["status"] == "ACTIVE"

    async def test_parse_suggestion_minimal(self):
        """Минимальный suggestion без опциональных полей."""
        from backend.customers.dadata import _parse_suggestion
        suggestion = {
            "value": "ИП Иванов",
            "data": {
                "inn": "123456789012",
                "state": {"status": "ACTIVE"},
            },
        }
        result = _parse_suggestion(suggestion)
        assert result["name"] == "ИП Иванов"
        assert result["inn"] == "123456789012"
        assert result["phone"] == ""
        assert result["email"] == ""
        assert result["director"] == ""

    async def test_lookup_by_inn_no_api_key(self):
        """Без API-ключа возвращает None."""
        from backend.customers.dadata import lookup_by_inn
        with patch("backend.customers.dadata.settings") as mock_settings:
            mock_settings.dadata_api_key = ""
            result = await lookup_by_inn("1234567890")
            assert result is None

    async def test_search_by_name_no_api_key(self):
        """Без API-ключа возвращает пустой список."""
        from backend.customers.dadata import search_by_name
        with patch("backend.customers.dadata.settings") as mock_settings:
            mock_settings.dadata_api_key = ""
            result = await search_by_name("тест")
            assert result == []
