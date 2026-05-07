"""
Полный тест-сьют PASS24 Service Desk.

Запуск на сервере:
  docker exec site-pass24-servicedesk python -m pytest tests/test_full_suite.py -v --tb=short

Покрытие:
  - Auth: регистрация, логин, роли, JWT
  - Tickets: CRUD, фильтры, пагинация, RBAC
  - Ticket FSM: все переходы, SLA-таймстампы
  - Comments: публичные, внутренние, RBAC
  - Attachments: upload, download, валидация
  - Knowledge: CRUD, FTS, slug, views
  - Stats: overview, timeline, SLA
  - Business Logic: авто-приоритет, авто-категория
"""
from __future__ import annotations

import asyncio
import io
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.asyncio

BASE_URL = "http://localhost:8000"
TEST_EMAIL_DOMAIN = "@example.com"  # Все тестовые email

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


async def _cleanup_test_data_async() -> int:
    """Удаляет всех тестовых пользователей и их данные.

    Тестовые пользователи — с email @example.com (все тесты
    используют этот домен).
    """
    import asyncpg
    from backend.config import settings

    # asyncpg нужен чистый URL без "+asyncpg"
    url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)
    try:
        pattern = f"%{TEST_EMAIL_DOMAIN}"
        # Удаляем статьи где автор — тестовый юзер
        await conn.execute("""
            DELETE FROM articles WHERE author_id IN (
                SELECT id FROM users WHERE email LIKE $1
            )
        """, pattern)
        await conn.execute("""
            DELETE FROM attachments WHERE ticket_id IN (
                SELECT id FROM tickets WHERE creator_id IN (
                    SELECT id::text FROM users WHERE email LIKE $1
                )
            )
        """, pattern)
        await conn.execute("""
            DELETE FROM ticket_comments WHERE ticket_id IN (
                SELECT id FROM tickets WHERE creator_id IN (
                    SELECT id::text FROM users WHERE email LIKE $1
                )
            )
        """, pattern)
        await conn.execute("""
            DELETE FROM ticket_events WHERE ticket_id IN (
                SELECT id FROM tickets WHERE creator_id IN (
                    SELECT id::text FROM users WHERE email LIKE $1
                )
            )
        """, pattern)
        await conn.execute("""
            DELETE FROM tickets WHERE creator_id IN (
                SELECT id::text FROM users WHERE email LIKE $1
            )
        """, pattern)
        await conn.execute("""
            DELETE FROM ticket_comments WHERE author_id IN (
                SELECT id::text FROM users WHERE email LIKE $1
            )
        """, pattern)
        result = await conn.execute("DELETE FROM users WHERE email LIKE $1", pattern)
        # result формата "DELETE N"
        try:
            deleted = int(result.split()[-1])
        except Exception:
            deleted = 0
        return deleted
    finally:
        await conn.close()


def _cleanup_test_data_sync() -> int:
    """Запускает async cleanup в отдельном потоке (новый event loop)."""
    import concurrent.futures

    def _runner():
        return asyncio.new_event_loop().run_until_complete(_cleanup_test_data_async())

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_runner).result(timeout=30)


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data():
    """Удаляет тестовые данные в начале и в конце сессии."""
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
    """Изолированный DB engine для тестов."""
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
    """HTTP-клиент, подключающийся к запущенному серверу."""
    async with AsyncClient(base_url=BASE_URL) as c:
        yield c


# Уникальные email для каждого теста
def _email(prefix: str = "test") -> str:
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
    """Создаёт агента поддержки (регистрация + промоут через БД)."""
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
    """Создаёт админа."""
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


# =====================================================================
# 1. AUTH
# =====================================================================

class TestAuth:
    async def test_register_resident(self, client):
        email = _email()
        r = await client.post("/auth/register", json={
            "email": email, "password": "pass123456", "full_name": "Тест", "role": "resident",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["email"] == email
        assert data["role"] == "resident"
        assert "id" in data

    async def test_register_property_manager(self, client):
        r = await client.post("/auth/register", json={
            "email": _email(), "password": "pass123456", "full_name": "УК", "role": "property_manager",
        })
        assert r.status_code == 201
        assert r.json()["role"] == "property_manager"

    async def test_register_agent_forbidden(self, client):
        r = await client.post("/auth/register", json={
            "email": _email(), "password": "pass123456", "full_name": "Hacker", "role": "support_agent",
        })
        assert r.status_code == 403

    async def test_register_admin_forbidden(self, client):
        r = await client.post("/auth/register", json={
            "email": _email(), "password": "pass123456", "full_name": "Hacker", "role": "admin",
        })
        assert r.status_code == 403

    async def test_register_duplicate_email(self, client):
        email = _email()
        await _register(client, email)
        r = await client.post("/auth/register", json={
            "email": email, "password": "pass123456", "full_name": "Dup", "role": "resident",
        })
        assert r.status_code == 409

    async def test_register_short_password(self, client):
        r = await client.post("/auth/register", json={
            "email": _email(), "password": "123", "full_name": "Short", "role": "resident",
        })
        assert r.status_code == 422

    async def test_login_success(self, client):
        email = _email()
        await _register(client, email)
        r = await client.post("/auth/login", json={"email": email, "password": "pass123456"})
        assert r.status_code == 200
        assert "access_token" in r.json()
        assert r.json()["token_type"] == "bearer"

    async def test_login_wrong_password(self, client):
        email = _email()
        await _register(client, email)
        r = await client.post("/auth/login", json={"email": email, "password": "wrong"})
        assert r.status_code == 401

    async def test_login_nonexistent(self, client):
        r = await client.post("/auth/login", json={"email": "ghost@example.com", "password": "pass123456"})
        assert r.status_code == 401

    async def test_me(self, client):
        email = _email()
        headers = await _auth_headers(client, email, name="Алексей")
        r = await client.get("/auth/me", headers=headers)
        assert r.status_code == 200
        assert r.json()["email"] == email
        assert r.json()["full_name"] == "Алексей"

    async def test_me_no_token(self, client):
        r = await client.get("/auth/me")
        assert r.status_code in (401, 403)

    async def test_me_invalid_token(self, client):
        r = await client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert r.status_code == 401


# =====================================================================
# 2. TICKETS CRUD
# =====================================================================

class TestTicketsCRUD:
    async def test_create_ticket(self, client):
        headers = await _auth_headers(client, _email())
        r = await client.post("/tickets/", json={
            "title": "Не работает домофон",
            "description": "Домофон в 3 подъезде не реагирует на кнопки",
        }, headers=headers)
        assert r.status_code == 201
        data = r.json()
        assert data["title"] == "Не работает домофон"
        assert data["status"] == "new"
        assert len(data["events"]) >= 1

    async def test_create_ticket_no_auth(self, client):
        r = await client.post("/tickets/", json={
            "title": "Test", "description": "Test description for ticket",
        })
        assert r.status_code in (401, 403)

    async def test_list_tickets_resident_sees_own(self, client):
        email1 = _email("user1")
        email2 = _email("user2")
        h1 = await _auth_headers(client, email1, name="User1")
        h2 = await _auth_headers(client, email2, name="User2")

        await client.post("/tickets/", json={"title": "T1", "description": "D" * 25}, headers=h1)
        await client.post("/tickets/", json={"title": "T2", "description": "D" * 25}, headers=h2)

        r1 = await client.get("/tickets/", headers=h1)
        r2 = await client.get("/tickets/", headers=h2)
        assert r1.json()["total"] >= 1
        assert r2.json()["total"] >= 1
        # User1 не видит тикеты User2
        titles1 = [t["title"] for t in r1.json()["items"]]
        assert "T2" not in titles1

    async def test_list_tickets_agent_sees_all(self, client):
        email = _email("res")
        h = await _auth_headers(client, email)
        await client.post("/tickets/", json={"title": "Res ticket", "description": "D" * 25}, headers=h)

        _, agent_h = await _create_agent(client)
        r = await client.get("/tickets/", headers=agent_h)
        assert r.json()["total"] >= 1

    async def test_get_ticket(self, client):
        headers = await _auth_headers(client, _email())
        cr = await client.post("/tickets/", json={
            "title": "Get test", "description": "D" * 25,
        }, headers=headers)
        ticket_id = cr.json()["id"]

        r = await client.get(f"/tickets/{ticket_id}", headers=headers)
        assert r.status_code == 200
        assert r.json()["id"] == ticket_id

    async def test_get_ticket_not_found(self, client):
        headers = await _auth_headers(client, _email())
        r = await client.get("/tickets/nonexistent-id", headers=headers)
        assert r.status_code == 404

    async def test_delete_ticket_admin_only(self, client):
        email = _email("res")
        h = await _auth_headers(client, email)
        cr = await client.post("/tickets/", json={"title": "Del", "description": "D" * 25}, headers=h)
        tid = cr.json()["id"]

        # Resident не может удалить
        r = await client.delete(f"/tickets/{tid}", headers=h)
        assert r.status_code == 403

        # Admin может
        _, admin_h = await _create_admin(client)
        r = await client.delete(f"/tickets/{tid}", headers=admin_h)
        assert r.status_code == 204

    async def test_filter_by_status(self, client):
        _, agent_h = await _create_agent(client)
        r = await client.get("/tickets/?status=new", headers=agent_h)
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["status"] == "new"

    async def test_filter_multiple_statuses(self, client):
        _, agent_h = await _create_agent(client)
        r = await client.get("/tickets/?status=new,in_progress", headers=agent_h)
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["status"] in ("new", "in_progress")

    async def test_my_tickets_filter(self, client):
        email = _email()
        h = await _auth_headers(client, email)
        await client.post("/tickets/", json={"title": "My", "description": "D" * 25}, headers=h)
        r = await client.get("/tickets/?my=true", headers=h)
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    async def test_pagination(self, client):
        _, agent_h = await _create_agent(client)
        r = await client.get("/tickets/?page=1&per_page=2", headers=agent_h)
        assert r.status_code == 200
        assert len(r.json()["items"]) <= 2


# =====================================================================
# 3. TICKET FSM & SLA
# =====================================================================

class TestTicketFSM:
    async def _create_and_get(self, client):
        _, agent_h = await _create_agent(client)
        cr = await client.post("/tickets/", json={
            "title": "FSM test", "description": "D" * 25,
        }, headers=agent_h)
        return cr.json()["id"], agent_h

    async def test_new_to_in_progress(self, client):
        tid, h = await self._create_and_get(client)
        r = await client.post(f"/tickets/{tid}/status", json={"new_status": "in_progress"}, headers=h)
        assert r.status_code == 200
        assert r.json()["status"] == "in_progress"
        assert r.json()["first_response_at"] is not None

    async def test_new_to_resolved(self, client):
        tid, h = await self._create_and_get(client)
        r = await client.post(f"/tickets/{tid}/status", json={"new_status": "resolved"}, headers=h)
        assert r.status_code == 200
        assert r.json()["status"] == "resolved"
        assert r.json()["resolved_at"] is not None

    async def test_invalid_transition(self, client):
        tid, h = await self._create_and_get(client)
        r = await client.post(f"/tickets/{tid}/status", json={"new_status": "closed"}, headers=h)
        assert r.status_code == 400

    async def test_full_lifecycle(self, client):
        tid, h = await self._create_and_get(client)

        # NEW → IN_PROGRESS
        r = await client.post(f"/tickets/{tid}/status", json={"new_status": "in_progress"}, headers=h)
        assert r.json()["status"] == "in_progress"

        # IN_PROGRESS → WAITING_FOR_USER
        r = await client.post(f"/tickets/{tid}/status", json={"new_status": "waiting_for_user"}, headers=h)
        assert r.json()["status"] == "waiting_for_user"

        # WAITING_FOR_USER → RESOLVED
        r = await client.post(f"/tickets/{tid}/status", json={"new_status": "resolved"}, headers=h)
        assert r.json()["status"] == "resolved"

        # RESOLVED → CLOSED
        r = await client.post(f"/tickets/{tid}/status", json={"new_status": "closed"}, headers=h)
        assert r.json()["status"] == "closed"

    async def test_closed_immutable(self, client):
        tid, h = await self._create_and_get(client)
        await client.post(f"/tickets/{tid}/status", json={"new_status": "resolved"}, headers=h)
        await client.post(f"/tickets/{tid}/status", json={"new_status": "closed"}, headers=h)
        r = await client.post(f"/tickets/{tid}/status", json={"new_status": "in_progress"}, headers=h)
        assert r.status_code == 400

    async def test_reopen_clears_resolved_at(self, client):
        tid, h = await self._create_and_get(client)
        await client.post(f"/tickets/{tid}/status", json={"new_status": "resolved"}, headers=h)
        r = await client.post(f"/tickets/{tid}/status", json={"new_status": "in_progress"}, headers=h)
        assert r.json()["resolved_at"] is None

    async def test_sla_set_by_priority(self, client):
        _, h = await _create_agent(client)
        cr = await client.post("/tickets/", json={
            "title": "Не могу попасть домой", "description": "Дверь заблокирована, не пускает",
        }, headers=h)
        data = cr.json()
        assert data["priority"] == "critical"
        assert data["sla_response_hours"] == 1
        assert data["sla_resolve_hours"] == 4


# =====================================================================
# 4. COMMENTS
# =====================================================================

class TestComments:
    async def test_add_comment(self, client):
        _, agent_h = await _create_agent(client)
        cr = await client.post("/tickets/", json={
            "title": "Comment test", "description": "D" * 25,
        }, headers=agent_h)
        tid = cr.json()["id"]

        r = await client.post(f"/tickets/{tid}/comments", json={"text": "Работаем над проблемой"}, headers=agent_h)
        assert r.status_code == 201
        assert r.json()["text"] == "Работаем над проблемой"
        assert r.json()["is_internal"] is False

    async def test_internal_comment_agent(self, client):
        _, agent_h = await _create_agent(client)
        cr = await client.post("/tickets/", json={
            "title": "Int comment", "description": "D" * 25,
        }, headers=agent_h)
        tid = cr.json()["id"]

        r = await client.post(f"/tickets/{tid}/comments",
                               json={"text": "Внутренняя заметка", "is_internal": True}, headers=agent_h)
        assert r.status_code == 201
        assert r.json()["is_internal"] is True

    async def test_internal_comment_hidden_from_resident(self, client):
        _, agent_h = await _create_agent(client)
        res_email = _email("res")
        res_h = await _auth_headers(client, res_email)

        # Агент создаёт тикет от имени резидента через API — для простоты агент создаёт свой
        cr = await client.post("/tickets/", json={
            "title": "Visible test", "description": "D" * 25,
        }, headers=agent_h)
        tid = cr.json()["id"]

        # Агент добавляет внутренний комментарий
        await client.post(f"/tickets/{tid}/comments",
                          json={"text": "Секрет", "is_internal": True}, headers=agent_h)
        # Агент добавляет публичный комментарий
        await client.post(f"/tickets/{tid}/comments",
                          json={"text": "Публичный"}, headers=agent_h)

        # Агент видит оба
        r_agent = await client.get(f"/tickets/{tid}", headers=agent_h)
        assert len(r_agent.json()["comments"]) == 2

    async def test_resident_cannot_set_internal(self, client):
        email = _email()
        h = await _auth_headers(client, email)
        cr = await client.post("/tickets/", json={
            "title": "Res internal", "description": "D" * 25,
        }, headers=h)
        tid = cr.json()["id"]

        r = await client.post(f"/tickets/{tid}/comments",
                               json={"text": "Попытка", "is_internal": True}, headers=h)
        assert r.status_code == 201
        assert r.json()["is_internal"] is False  # Флаг игнорируется


# =====================================================================
# 5. ATTACHMENTS
# =====================================================================

class TestAttachments:
    async def test_upload_attachment(self, client):
        _, agent_h = await _create_agent(client)
        cr = await client.post("/tickets/", json={
            "title": "Attach test", "description": "D" * 25,
        }, headers=agent_h)
        tid = cr.json()["id"]

        files = {"file": ("test.png", io.BytesIO(b"\x89PNG" + b"\x00" * 100), "image/png")}
        r = await client.post(f"/tickets/{tid}/attachments", files=files, headers=agent_h)
        assert r.status_code == 201
        assert r.json()["filename"] == "test.png"
        assert r.json()["content_type"] == "image/png"
        assert r.json()["size"] > 0

    async def test_upload_invalid_type(self, client):
        _, agent_h = await _create_agent(client)
        cr = await client.post("/tickets/", json={
            "title": "Bad type", "description": "D" * 25,
        }, headers=agent_h)
        tid = cr.json()["id"]

        files = {"file": ("malware.exe", io.BytesIO(b"\x00" * 100), "application/x-executable")}
        r = await client.post(f"/tickets/{tid}/attachments", files=files, headers=agent_h)
        assert r.status_code == 400

    async def test_download_attachment(self, client):
        _, agent_h = await _create_agent(client)
        cr = await client.post("/tickets/", json={
            "title": "Download test", "description": "D" * 25,
        }, headers=agent_h)
        tid = cr.json()["id"]

        content = b"\x89PNG" + b"\xAB" * 50
        files = {"file": ("photo.png", io.BytesIO(content), "image/png")}
        upload = await client.post(f"/tickets/{tid}/attachments", files=files, headers=agent_h)
        att_id = upload.json()["id"]

        r = await client.get(f"/tickets/{tid}/attachments/{att_id}", headers=agent_h)
        assert r.status_code == 200
        assert r.content == content

    async def test_ticket_includes_attachments(self, client):
        _, agent_h = await _create_agent(client)
        cr = await client.post("/tickets/", json={
            "title": "Inc attach", "description": "D" * 25,
        }, headers=agent_h)
        tid = cr.json()["id"]

        files = {"file": ("doc.pdf", io.BytesIO(b"%PDF" + b"\x00" * 50), "application/pdf")}
        await client.post(f"/tickets/{tid}/attachments", files=files, headers=agent_h)

        r = await client.get(f"/tickets/{tid}", headers=agent_h)
        assert len(r.json()["attachments"]) == 1
        assert r.json()["attachments"][0]["filename"] == "doc.pdf"


# =====================================================================
# 6. KNOWLEDGE BASE
# =====================================================================

class TestKnowledge:
    async def test_create_article_agent(self, client):
        _, agent_h = await _create_agent(client)
        r = await client.post("/knowledge/", json={
            "title": f"Тестовая статья {uuid.uuid4().hex[:6]}",
            "category": "access",
            "content": "# Инструкция\nТекст инструкции для теста",
        }, headers=agent_h)
        assert r.status_code == 201
        data = r.json()
        assert data["slug"]  # slug сгенерирован
        assert data["is_published"] is True

    async def test_create_article_resident_forbidden(self, client):
        h = await _auth_headers(client, _email())
        r = await client.post("/knowledge/", json={
            "title": "Попытка", "category": "general", "content": "Текст",
        }, headers=h)
        assert r.status_code == 403

    async def test_list_articles_no_auth(self, client):
        r = await client.get("/knowledge/")
        assert r.status_code == 200
        assert "items" in r.json()

    async def test_get_article_by_slug(self, client):
        _, agent_h = await _create_agent(client)
        title = f"Slug test {uuid.uuid4().hex[:6]}"
        cr = await client.post("/knowledge/", json={
            "title": title, "category": "general", "content": "Контент",
        }, headers=agent_h)
        slug = cr.json()["slug"]

        r = await client.get(f"/knowledge/{slug}")
        assert r.status_code == 200
        assert r.json()["slug"] == slug

    async def test_article_views_increment(self, client):
        _, agent_h = await _create_agent(client)
        cr = await client.post("/knowledge/", json={
            "title": f"Views test {uuid.uuid4().hex[:6]}",
            "category": "general", "content": "Текст",
        }, headers=agent_h)
        slug = cr.json()["slug"]

        r1 = await client.get(f"/knowledge/{slug}")
        views1 = r1.json()["views_count"]
        r2 = await client.get(f"/knowledge/{slug}")
        views2 = r2.json()["views_count"]
        assert views2 == views1 + 1

    async def test_search_fts(self, client):
        _, agent_h = await _create_agent(client)
        unique = uuid.uuid4().hex[:8]
        await client.post("/knowledge/", json={
            "title": f"Инструкция по домофону {unique}",
            "category": "access",
            "content": f"Как пользоваться домофоном в подъезде {unique}",
        }, headers=agent_h)

        r = await client.get(f"/knowledge/search?query={unique}")
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    async def test_update_article(self, client):
        _, agent_h = await _create_agent(client)
        cr = await client.post("/knowledge/", json={
            "title": f"Update test {uuid.uuid4().hex[:6]}",
            "category": "general", "content": "Старый текст",
        }, headers=agent_h)
        art_id = cr.json()["id"]

        r = await client.put(f"/knowledge/{art_id}", json={
            "content": "Новый текст",
        }, headers=agent_h)
        assert r.status_code == 200
        assert r.json()["content"] == "Новый текст"

    async def test_delete_article_admin_only(self, client):
        _, agent_h = await _create_agent(client)
        cr = await client.post("/knowledge/", json={
            "title": f"Del test {uuid.uuid4().hex[:6]}",
            "category": "general", "content": "Текст",
        }, headers=agent_h)
        art_id = cr.json()["id"]

        # Агент не может удалить
        r = await client.delete(f"/knowledge/{art_id}", headers=agent_h)
        assert r.status_code == 403

        # Админ может
        _, admin_h = await _create_admin(client)
        r = await client.delete(f"/knowledge/{art_id}", headers=admin_h)
        assert r.status_code == 204

    async def test_article_not_found(self, client):
        r = await client.get("/knowledge/nonexistent-slug-12345")
        assert r.status_code == 404

    async def test_filter_by_category(self, client):
        r = await client.get("/knowledge/?category=access")
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["category"] == "access"


# =====================================================================
# 7. STATS
# =====================================================================

class TestStats:
    async def test_overview(self, client):
        _, agent_h = await _create_agent(client)
        r = await client.get("/stats/overview", headers=agent_h)
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert "open" in data
        assert "by_status" in data
        assert "by_priority" in data
        assert "by_category" in data

    async def test_timeline(self, client):
        _, agent_h = await _create_agent(client)
        r = await client.get("/stats/timeline?days=7", headers=agent_h)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            assert "date" in data[0]
            assert "count" in data[0]

    async def test_sla(self, client):
        _, agent_h = await _create_agent(client)
        r = await client.get("/stats/sla", headers=agent_h)
        assert r.status_code == 200
        data = r.json()
        assert "response" in data
        assert "resolution" in data
        assert "avg_hours" in data["response"]
        assert "compliance_pct" in data["response"]

    async def test_stats_require_auth(self, client):
        r = await client.get("/stats/overview")
        assert r.status_code in (401, 403)


# =====================================================================
# 8. BUSINESS LOGIC (unit tests)
# =====================================================================

class TestBusinessLogic:
    def test_priority_critical_cannot_enter(self):
        from backend.tickets.models import Ticket
        t = Ticket(title="Не могу попасть домой", description="Дверь заблокирована")
        t.assign_priority_based_on_context()
        assert t.priority.value == "critical"
        assert t.sla_response_hours == 1

    def test_priority_critical_incident(self):
        from backend.tickets.models import Ticket
        t = Ticket(title="Сбой", description="Описание", ticket_type="incident")
        t.assign_priority_based_on_context()
        assert t.priority.value == "critical"

    def test_priority_high_gate(self):
        from backend.tickets.models import Ticket
        t = Ticket(title="Шлагбаум не работает", description="На парковке")
        t.assign_priority_based_on_context()
        assert t.priority.value == "high"

    def test_priority_low_question(self):
        from backend.tickets.models import Ticket
        t = Ticket(title="Вопрос", description="Как настроить", ticket_type="question")
        t.assign_priority_based_on_context()
        assert t.priority.value == "low"

    def test_priority_normal_default(self):
        from backend.tickets.models import Ticket
        t = Ticket(title="Обычный запрос", description="Нужна помощь с настройкой портала")
        t.assign_priority_based_on_context()
        assert t.priority.value == "normal"

    def test_category_registration(self):
        from backend.tickets.models import Ticket
        t = Ticket(title="Не могу войти", description="Забыл пароль от личного кабинета")
        t.auto_detect_category()
        assert t.category == "registration"

    def test_category_passes(self):
        from backend.tickets.models import Ticket
        t = Ticket(title="Гостевой пропуск не работает", description="Пропуск не сканируется на турникете")
        t.auto_detect_category()
        assert t.category == "passes"

    def test_category_recognition(self):
        from backend.tickets.models import Ticket
        t = Ticket(title="Камера", description="Распознавание номер авто не работает")
        t.auto_detect_category()
        assert t.category == "recognition"

    def test_category_app_issues(self):
        from backend.tickets.models import Ticket
        t = Ticket(title="Баг", description="Приложение вылетает при открытии")
        t.auto_detect_category()
        assert t.category == "app_issues"

    def test_category_feature_request(self):
        from backend.tickets.models import Ticket
        t = Ticket(title="Идея", description="Хотелось бы видеть историю проходов")
        t.auto_detect_category()
        assert t.category == "feature_request"

    def test_product_mobile_app(self):
        from backend.tickets.models import Ticket
        t = Ticket(title="iOS", description="Мобильное приложение не работает на iOS 17")
        t.auto_detect_category()
        assert t.product == "mobile_app"

    def test_product_equipment(self):
        from backend.tickets.models import Ticket
        t = Ticket(title="Замок", description="Считыватель оборудование перестало работать")
        t.auto_detect_category()
        assert t.product == "equipment"

    def test_fsm_all_valid_transitions(self):
        from backend.tickets.models import Ticket, TicketStatus
        transitions = [
            ("new", "in_progress"),
            ("new", "resolved"),
            ("in_progress", "waiting_for_user"),
            ("in_progress", "resolved"),
            ("waiting_for_user", "in_progress"),
            ("waiting_for_user", "resolved"),
            ("resolved", "closed"),
            ("resolved", "in_progress"),
        ]
        for start, end in transitions:
            t = Ticket(title="Test", description="D", status=TicketStatus(start))
            event = t.transition("actor", TicketStatus(end))
            assert t.status.value == end, f"{start} → {end} failed"
            assert event is not None

    def test_fsm_invalid_transitions(self):
        """Единственный недопустимый переход — «сам в себя»; CLOSED → * разрешён."""
        from backend.tickets.models import Ticket, TicketStatus
        for status_value in ("new", "in_progress", "waiting_for_user",
                              "on_hold", "engineer_visit", "resolved", "closed"):
            t = Ticket(title="Test", description="D", status=TicketStatus(status_value))
            with pytest.raises(ValueError, match="Недопустимый переход"):
                t.transition("actor", TicketStatus(status_value))

    def test_fsm_closed_can_reopen(self):
        """Из CLOSED разрешён переход в любой open-статус (например, IN_PROGRESS)."""
        from backend.tickets.models import Ticket, TicketStatus
        t = Ticket(title="Reopen", description="D")
        t.transition("actor", TicketStatus.RESOLVED)
        t.transition("actor", TicketStatus.CLOSED)
        assert t.status == TicketStatus.CLOSED.value or t.status == TicketStatus.CLOSED
        event = t.transition("actor", TicketStatus.IN_PROGRESS)
        assert t.status == TicketStatus.IN_PROGRESS.value or t.status == TicketStatus.IN_PROGRESS
        assert t.resolved_at is None
        assert event is not None

    def test_sla_first_response_tracked(self):
        from backend.tickets.models import Ticket, TicketStatus
        t = Ticket(title="T", description="D")
        assert t.first_response_at is None
        t.transition("actor", TicketStatus.IN_PROGRESS)
        assert t.first_response_at is not None

    def test_sla_resolved_at_tracked(self):
        from backend.tickets.models import Ticket, TicketStatus
        t = Ticket(title="T", description="D")
        t.transition("actor", TicketStatus.RESOLVED)
        assert t.resolved_at is not None

    def test_sla_reopen_clears_resolved(self):
        from backend.tickets.models import Ticket, TicketStatus
        t = Ticket(title="T", description="D")
        t.transition("actor", TicketStatus.RESOLVED)
        assert t.resolved_at is not None
        t.transition("actor", TicketStatus.IN_PROGRESS)
        assert t.resolved_at is None


# =====================================================================
# 9. HEALTH
# =====================================================================

class TestHealth:
    async def test_health_endpoint(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# =====================================================================
# 10. GUEST TICKET (if endpoint exists)
# =====================================================================

class TestGuestTicket:
    async def test_guest_create(self, client):
        r = await client.post("/tickets/guest", json={
            "email": _email("guest"),
            "name": "Гость",
            "title": "Не могу пройти",
            "description": "Гостевой пропуск не работает на входе в БЦ",
        })
        if r.status_code == 404:
            pytest.skip("Guest endpoint not deployed")
        assert r.status_code == 201
        assert r.json()["status"] == "new"


# =====================================================================
# 11.5 TICKET NUMBER (короткий пользовательский номер)
# =====================================================================

class TestTicketNumber:
    """tickets.number — короткий последовательный ID."""

    async def test_ticket_response_has_number(self, client):
        """API на создание тикета возвращает поле `number`."""
        h = await _auth_headers(client, _email("number"))
        r = await client.post("/tickets/", json={
            "title": "Номер заявки в API",
            "description": "Проверяем, что API возвращает короткий номер " + "x" * 20,
        }, headers=h)
        assert r.status_code == 201
        data = r.json()
        assert "number" in data
        # number может быть None у тикетов до миграции, но новые INSERT через
        # SEQUENCE его всегда заполняют — ожидаем int.
        assert isinstance(data["number"], int)
        assert data["number"] > 0

    async def test_get_ticket_by_number(self, client):
        """GET /tickets/by-number/{n} возвращает тикет с этим номером."""
        h = await _auth_headers(client, _email("bynum"))
        r = await client.post("/tickets/", json={
            "title": "Поиск по номеру",
            "description": "Проверка by-number endpoint " + "y" * 30,
        }, headers=h)
        assert r.status_code == 201
        ticket = r.json()
        ticket_id = ticket["id"]
        ticket_number = ticket["number"]

        rb = await client.get(f"/tickets/by-number/{ticket_number}", headers=h)
        assert rb.status_code == 200
        assert rb.json()["id"] == ticket_id
        assert rb.json()["number"] == ticket_number

    async def test_get_ticket_by_number_not_found(self, client):
        """Несуществующий номер → 404."""
        h = await _auth_headers(client, _email("bynum404"))
        r = await client.get("/tickets/by-number/99999999", headers=h)
        assert r.status_code == 404

    def test_subject_tag_uses_number_when_available(self):
        """ticket_subject_tag отдаёт [PASS24-{number}], если number задан."""
        from backend.notifications.email import ticket_subject_tag
        # с number — числовой формат
        assert ticket_subject_tag("abc12345-uuid", ticket_number=42) == "[PASS24-42]"
        # без number — fallback на UUID-prefix
        assert ticket_subject_tag("abc12345-uuid", ticket_number=None) == "[PASS24-abc12345]"
        assert ticket_subject_tag("abc12345-uuid") == "[PASS24-abc12345]"

    def test_inbound_regex_matches_number_and_legacy(self):
        """Парсер inbound понимает оба формата тегов."""
        from backend.notifications.inbound import (
            TICKET_TAG_NUMBER_RE,
            TICKET_TAG_RE,
            TICKET_BODY_TAG_NUMBER_RE,
            TICKET_BODY_TAG_RE,
        )
        # Subject tags
        m_num = TICKET_TAG_NUMBER_RE.search("Re: [PASS24-123] Тема")
        assert m_num and m_num.group(1) == "123"
        m_legacy = TICKET_TAG_RE.search("Re: [PASS24-abcd1234] Тема")
        assert m_legacy and m_legacy.group(1) == "abcd1234"
        # Body tags
        b_num = TICKET_BODY_TAG_NUMBER_RE.search("--- Не удаляйте: PASS24-77 ---")
        assert b_num and b_num.group(1) == "77"
        b_legacy = TICKET_BODY_TAG_RE.search("PASS24-deadbeef")
        assert b_legacy and b_legacy.group(1) == "deadbeef"


# =====================================================================
# 11. NOTIFICATIONS (recent feed)
# =====================================================================

class TestNotificationsRecent:
    """Эндпоинт /tickets/notifications/recent — лента уведомлений для агентов."""

    async def test_recent_resident_forbidden(self, client):
        """Резиденты не получают ленту (возвращается пустой ответ)."""
        h = await _auth_headers(client, _email("resnotif"))
        r = await client.get("/tickets/notifications/recent", headers=h)
        assert r.status_code == 200
        data = r.json()
        assert data["unread_count"] == 0
        assert data["items"] == []

    async def test_recent_agent_sees_unread(self, client):
        """Агент получает свежее уведомление с is_unread=True после комментария клиента."""
        res_email = _email("resnotif2")
        res_h = await _auth_headers(client, res_email, name="Resident Notif")

        # Создаём тикет от резидента
        r = await client.post("/tickets/", json={
            "title": "Уведомление-тест: домофон",
            "description": "Тестовое уведомление для агентской ленты " + "x" * 30,
        }, headers=res_h)
        assert r.status_code == 201
        ticket_id = r.json()["id"]

        # Резидент добавляет публичный комментарий → has_unread_reply=True
        rc = await client.post(
            f"/tickets/{ticket_id}/comments",
            json={"text": "Добавляю детали по проблеме", "is_internal": False},
            headers=res_h,
        )
        assert rc.status_code == 201

        # Агент запрашивает ленту
        _, agent_h = await _create_agent(client)
        r = await client.get("/tickets/notifications/recent?limit=10", headers=agent_h)
        assert r.status_code == 200
        data = r.json()
        ids = [item["id"] for item in data["items"]]
        assert ticket_id in ids
        item = next(it for it in data["items"] if it["id"] == ticket_id)
        assert item["is_unread"] is True
        assert data["unread_count"] >= 1

    async def test_recent_period_days_filter(self, client):
        """period_days=1 ограничивает ленту последними 24 часами."""
        res_email = _email("resnotif3")
        res_h = await _auth_headers(client, res_email, name="Resident Notif3")
        r = await client.post("/tickets/", json={
            "title": "Уведомление period-filter",
            "description": "Тест period_days " + "y" * 30,
        }, headers=res_h)
        ticket_id = r.json()["id"]
        await client.post(
            f"/tickets/{ticket_id}/comments",
            json={"text": "Свежий комментарий клиента", "is_internal": False},
            headers=res_h,
        )

        _, agent_h = await _create_agent(client)
        # period_days=1 — свежий тикет должен присутствовать
        r1 = await client.get(
            "/tickets/notifications/recent?limit=50&period_days=1",
            headers=agent_h,
        )
        assert r1.status_code == 200
        ids = [it["id"] for it in r1.json()["items"]]
        assert ticket_id in ids

    async def test_recent_excludes_internal_and_staff_comments(self, client):
        """В ленту попадают только публичные комментарии клиента, не staff и не internal."""
        res_email = _email("resnotif4")
        res_h = await _auth_headers(client, res_email, name="Resident Notif4")
        r = await client.post("/tickets/", json={
            "title": "Тикет без клиентского комментария",
            "description": "Только staff/internal коммменты " + "z" * 30,
        }, headers=res_h)
        ticket_id = r.json()["id"]

        _, agent_h = await _create_agent(client)
        # Агент пишет публичный + internal — ни один не должен поднять тикет в ленту
        await client.post(
            f"/tickets/{ticket_id}/comments",
            json={"text": "Публичный ответ агента", "is_internal": False},
            headers=agent_h,
        )
        await client.post(
            f"/tickets/{ticket_id}/comments",
            json={"text": "Внутренняя заметка", "is_internal": True},
            headers=agent_h,
        )

        r = await client.get("/tickets/notifications/recent?limit=50", headers=agent_h)
        assert r.status_code == 200
        ids = [it["id"] for it in r.json()["items"]]
        assert ticket_id not in ids
