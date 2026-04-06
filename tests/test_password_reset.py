"""
Тесты сброса пароля (forgot-password / reset-password).

Покрытие:
  - forgot-password: валидный email, несуществующий, деактивированный пользователь
  - reset-password: валидный токен, невалидный, истёкший
  - Полный цикл: forgot → reset → login с новым паролем
  - Security: токен одноразовый, повторное использование = ошибка

Запуск:
  docker exec site-pass24-servicedesk python -m pytest tests/test_password_reset.py -v --tb=short
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
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
# Fixtures
# ---------------------------------------------------------------------------

async def _cleanup_test_data_async() -> int:
    import asyncpg
    from backend.config import settings
    url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)
    try:
        pattern = f"%{TEST_EMAIL_DOMAIN}"
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


def _email(prefix: str = "reset") -> str:
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


# ---------------------------------------------------------------------------
# Helper: установить токен сброса напрямую в БД
# ---------------------------------------------------------------------------

async def _set_reset_token(email: str, raw_token: str, expires_at: datetime | None = None):
    """Устанавливает токен сброса пароля напрямую в БД (для тестов)."""
    from backend.auth.utils import hash_reset_token
    from backend.auth.models import User
    from backend.database import async_session_factory
    from sqlmodel import select

    token_hash = hash_reset_token(raw_token)
    if expires_at is None:
        expires_at = datetime.utcnow() + timedelta(hours=1)

    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        user.password_reset_token = token_hash
        user.password_reset_expires_at = expires_at
        session.add(user)
        await session.commit()


async def _deactivate_user(email: str):
    """Деактивирует пользователя."""
    from backend.auth.models import User
    from backend.database import async_session_factory
    from sqlmodel import select

    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        user.is_active = False
        session.add(user)
        await session.commit()


# =====================================================================
# 1. FORGOT PASSWORD
# =====================================================================

class TestForgotPassword:
    async def test_forgot_password_valid_email(self, client):
        """Запрос сброса для существующего пользователя — 200.

        Реальный SMTP отправит письмо на @example.com (bounce), но endpoint вернёт 200.
        Проверяем что токен записан в БД.
        """
        email = _email()
        await _register(client, email)

        r = await client.post("/auth/forgot-password", json={"email": email})
        assert r.status_code == 200
        data = r.json()
        assert "отправлено" in data["message"].lower() or "письмо" in data["message"].lower()

        # Проверяем что токен записался в БД
        from backend.auth.models import User
        from backend.database import async_session_factory
        from sqlmodel import select
        async with async_session_factory() as session:
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one()
            assert user.password_reset_token is not None
            assert user.password_reset_expires_at is not None

    async def test_forgot_password_unknown_email(self, client):
        """Несуществующий email — 404."""
        r = await client.post("/auth/forgot-password", json={"email": "nonexistent@example.com"})
        assert r.status_code == 404

    async def test_forgot_password_inactive_user(self, client):
        """Деактивированный пользователь — 403."""
        email = _email("inactive")
        await _register(client, email)
        await _deactivate_user(email)

        r = await client.post("/auth/forgot-password", json={"email": email})
        assert r.status_code == 403

    async def test_forgot_password_invalid_email_format(self, client):
        """Невалидный формат email — 422."""
        r = await client.post("/auth/forgot-password", json={"email": "not-an-email"})
        assert r.status_code == 422


# =====================================================================
# 2. RESET PASSWORD
# =====================================================================

class TestResetPassword:
    async def test_reset_password_valid_token(self, client):
        """Валидный токен — пароль меняется."""
        email = _email()
        await _register(client, email, "oldpassword123")

        raw_token = "test-valid-token-" + uuid.uuid4().hex[:16]
        await _set_reset_token(email, raw_token)

        r = await client.post("/auth/reset-password", json={
            "token": raw_token,
            "new_password": "newpassword456",
        })
        assert r.status_code == 200
        assert "изменён" in r.json()["message"].lower() or "успешно" in r.json()["message"].lower()

    async def test_reset_password_invalid_token(self, client):
        """Невалидный токен — 400."""
        r = await client.post("/auth/reset-password", json={
            "token": "completely-invalid-token",
            "new_password": "newpassword456",
        })
        assert r.status_code == 400

    async def test_reset_password_expired_token(self, client):
        """Истёкший токен — 400."""
        email = _email("expired")
        await _register(client, email)

        raw_token = "test-expired-token-" + uuid.uuid4().hex[:16]
        expired_time = datetime.utcnow() - timedelta(hours=2)
        await _set_reset_token(email, raw_token, expires_at=expired_time)

        r = await client.post("/auth/reset-password", json={
            "token": raw_token,
            "new_password": "newpassword456",
        })
        assert r.status_code == 400
        assert "истёк" in r.json()["detail"].lower() or "срок" in r.json()["detail"].lower()

    async def test_reset_password_short_password(self, client):
        """Слишком короткий новый пароль — 422."""
        email = _email()
        await _register(client, email)

        raw_token = "test-short-pw-" + uuid.uuid4().hex[:16]
        await _set_reset_token(email, raw_token)

        r = await client.post("/auth/reset-password", json={
            "token": raw_token,
            "new_password": "123",  # менее 6 символов
        })
        assert r.status_code == 422

    async def test_token_is_one_time_use(self, client):
        """Токен можно использовать только один раз."""
        email = _email("onetime")
        await _register(client, email, "oldpassword123")

        raw_token = "test-onetime-" + uuid.uuid4().hex[:16]
        await _set_reset_token(email, raw_token)

        # Первый раз — успех
        r = await client.post("/auth/reset-password", json={
            "token": raw_token,
            "new_password": "newpassword456",
        })
        assert r.status_code == 200

        # Второй раз тем же токеном — ошибка (токен очищен)
        r = await client.post("/auth/reset-password", json={
            "token": raw_token,
            "new_password": "anotherpassword789",
        })
        assert r.status_code == 400


# =====================================================================
# 3. FULL CYCLE
# =====================================================================

class TestFullResetCycle:
    async def test_forgot_then_reset_then_login(self, client):
        """Полный цикл: token в БД → reset → login с новым паролем.

        Вместо перехвата email-токена устанавливаем его напрямую в БД
        (серверный процесс отдельный, mock не работает cross-process).
        """
        email = _email("fullcycle")
        old_password = "oldpassword123"
        new_password = "newpassword456"

        await _register(client, email, old_password)

        # 1) Устанавливаем токен сброса напрямую в БД
        raw_token = "fullcycle-test-token-" + uuid.uuid4().hex[:16]
        await _set_reset_token(email, raw_token)

        # 2) Сброс пароля через API
        r = await client.post("/auth/reset-password", json={
            "token": raw_token,
            "new_password": new_password,
        })
        assert r.status_code == 200

        # 3) Логин со старым паролем — должен упасть
        r = await client.post("/auth/login", json={"email": email, "password": old_password})
        assert r.status_code == 401

        # 4) Логин с новым паролем — успех
        r = await client.post("/auth/login", json={"email": email, "password": new_password})
        assert r.status_code == 200
        assert "access_token" in r.json()


# =====================================================================
# 4. UNIT TESTS — token utilities
# =====================================================================

class TestTokenUtilities:
    def test_create_reset_token_returns_pair(self):
        from backend.auth.utils import create_reset_token
        raw, hashed = create_reset_token()
        assert len(raw) > 20  # url-safe token
        assert len(hashed) == 64  # SHA-256 hex

    def test_hash_reset_token_deterministic(self):
        from backend.auth.utils import hash_reset_token
        token = "test-token-12345"
        h1 = hash_reset_token(token)
        h2 = hash_reset_token(token)
        assert h1 == h2
        assert len(h1) == 64

    def test_create_and_hash_match(self):
        from backend.auth.utils import create_reset_token, hash_reset_token
        raw, stored_hash = create_reset_token()
        computed_hash = hash_reset_token(raw)
        assert stored_hash == computed_hash

    def test_different_tokens_different_hashes(self):
        from backend.auth.utils import create_reset_token
        raw1, hash1 = create_reset_token()
        raw2, hash2 = create_reset_token()
        assert raw1 != raw2
        assert hash1 != hash2
