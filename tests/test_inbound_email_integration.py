"""
Интеграционный тест входящей почты.

Запускается внутри контейнера на сервере:
  docker exec site-pass24-servicedesk python -m pytest tests/test_inbound_email_integration.py -v

Тестирует:
1. Создание тикета из email (новое письмо)
2. Ответ на тикет по тегу [PASS24-xxx] → комментарий
3. Ответ без тега (Re: ...) → комментарий по теме
4. Сохранение вложений из email
5. Авто-анализ: поиск по базе знаний
"""
import asyncio
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Для запуска async тестов
pytestmark = pytest.mark.asyncio

TEST_EMAIL_DOMAIN = "@example.com"


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


async def _cleanup_test_data_async() -> int:
    """Удаляет тестовые @example.com данные."""
    import asyncpg
    from backend.config import settings

    url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)
    try:
        pattern = f"%{TEST_EMAIL_DOMAIN}"
        await conn.execute(
            "DELETE FROM articles WHERE author_id IN "
            "(SELECT id FROM users WHERE email LIKE $1)", pattern)
        await conn.execute(
            "DELETE FROM attachments WHERE ticket_id IN "
            "(SELECT id FROM tickets WHERE creator_id IN "
            "(SELECT id::text FROM users WHERE email LIKE $1))", pattern)
        await conn.execute(
            "DELETE FROM ticket_comments WHERE ticket_id IN "
            "(SELECT id FROM tickets WHERE creator_id IN "
            "(SELECT id::text FROM users WHERE email LIKE $1))", pattern)
        await conn.execute(
            "DELETE FROM ticket_events WHERE ticket_id IN "
            "(SELECT id FROM tickets WHERE creator_id IN "
            "(SELECT id::text FROM users WHERE email LIKE $1))", pattern)
        await conn.execute(
            "DELETE FROM tickets WHERE creator_id IN "
            "(SELECT id::text FROM users WHERE email LIKE $1)", pattern)
        await conn.execute(
            "DELETE FROM ticket_comments WHERE author_id IN "
            "(SELECT id::text FROM users WHERE email LIKE $1)", pattern)
        result = await conn.execute("DELETE FROM users WHERE email LIKE $1", pattern)
        try:
            return int(result.split()[-1])
        except Exception:
            return 0
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
def _isolate_db_connections():
    """Создаёт изолированный engine для тестов, чтобы не конфликтовать с приложением."""
    import backend.database as db_mod
    from backend.config import settings

    test_engine = create_async_engine(settings.database_url, echo=False)
    test_session_factory = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    # Подменяем фабрику сессий на изолированную
    original_factory = db_mod.async_session_factory
    db_mod.async_session_factory = test_session_factory
    yield
    db_mod.async_session_factory = original_factory
    asyncio.get_event_loop().run_until_complete(test_engine.dispose())


def _fake_attachment(filename="photo.jpg", content_type="image/jpeg", size=1024):
    return {
        "filename": filename,
        "content_type": content_type,
        "data": b"\xff\xd8" + b"\x00" * (size - 2),
        "size": size,
    }


async def _get_or_create_user(email_addr: str, name: str = "Test User"):
    from backend.database import async_session_factory
    from backend.auth.models import User
    from backend.auth.utils import hash_password
    from sqlmodel import select

    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.email == email_addr))
        user = result.scalar_one_or_none()
        if user:
            return user

        user = User(
            email=email_addr,
            hashed_password=hash_password("test123"),
            full_name=name,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _get_ticket(ticket_id: str):
    from backend.database import async_session_factory
    from backend.tickets.models import Ticket
    from sqlalchemy.orm import selectinload
    from sqlmodel import select

    async with async_session_factory() as session:
        result = await session.execute(
            select(Ticket)
            .where(Ticket.id == ticket_id)
            .options(
                selectinload(Ticket.comments),
                selectinload(Ticket.attachments),
            )
        )
        return result.scalar_one_or_none()


async def _create_ticket(user_id: str, title: str):
    from backend.database import async_session_factory
    from backend.tickets.models import Ticket, TicketEvent

    async with async_session_factory() as session:
        ticket = Ticket(
            creator_id=user_id,
            title=title,
            description=f"Тестовое описание для: {title}",
            source="email",
            contact_email="test-inbound@example.com",
        )
        ticket.assign_priority_based_on_context()
        event = TicketEvent(
            ticket_id=ticket.id,
            actor_id=user_id,
            description="Тикет создан (тест)",
        )
        session.add(ticket)
        session.add(event)
        await session.commit()
        await session.refresh(ticket)
        return ticket


async def _cleanup_ticket(ticket_id: str):
    from backend.database import async_session_factory
    from backend.tickets.models import Ticket, TicketEvent, TicketComment, Attachment
    from sqlalchemy import delete as sa_delete

    async with async_session_factory() as session:
        await session.execute(sa_delete(Attachment).where(Attachment.ticket_id == ticket_id))
        await session.execute(sa_delete(TicketComment).where(TicketComment.ticket_id == ticket_id))
        await session.execute(sa_delete(TicketEvent).where(TicketEvent.ticket_id == ticket_id))
        await session.execute(sa_delete(Ticket).where(Ticket.id == ticket_id))
        await session.commit()


# -----------------------------------------------------------------------
# Тесты
# -----------------------------------------------------------------------


class TestReplyByTag:
    """Ответ с тегом [PASS24-xxxxxxxx] → комментарий к тикету."""

    async def test_reply_creates_comment(self):
        from backend.notifications.inbound import _handle_reply

        user = await _get_or_create_user("test-inbound@example.com", "Тест Ответ")
        ticket = await _create_ticket(str(user.id), "Тест тега в ответе")

        try:
            mail_data = {
                "subject": f"Re: [PASS24-{ticket.id[:8]}] Заявка создана: Тест тега в ответе",
                "from_email": "test-inbound@example.com",
                "from_name": "Тест Ответ",
                "body": "Вот дополнительная информация по заявке",
                "attachments": [],
            }

            result = await _handle_reply(mail_data, ticket.id[:8])
            assert result is True, "Ответ должен быть обработан"

            updated = await _get_ticket(ticket.id)
            assert len(updated.comments) == 1, f"Ожидался 1 комментарий, получено {len(updated.comments)}"
            assert "дополнительная информация" in updated.comments[0].text
            assert updated.comments[0].author_name == "Тест Ответ"
        finally:
            await _cleanup_ticket(ticket.id)

    async def test_reply_with_attachment(self):
        from backend.notifications.inbound import _handle_reply

        user = await _get_or_create_user("test-inbound@example.com", "Тест Ответ")
        ticket = await _create_ticket(str(user.id), "Тест вложения в ответе")

        try:
            mail_data = {
                "subject": f"Re: [PASS24-{ticket.id[:8]}] Тест",
                "from_email": "test-inbound@example.com",
                "from_name": "Тест Ответ",
                "body": "Прикрепляю скриншот",
                "attachments": [_fake_attachment("screenshot.png", "image/png", 2048)],
            }

            result = await _handle_reply(mail_data, ticket.id[:8])
            assert result is True

            updated = await _get_ticket(ticket.id)
            assert len(updated.comments) == 1
            assert len(updated.attachments) == 1, f"Ожидалось 1 вложение, получено {len(updated.attachments)}"
            assert updated.attachments[0].filename == "screenshot.png"
            assert updated.attachments[0].size == 2048
            # Вложение должно быть привязано к комментарию, чтобы UI
            # отображал его внутри пузыря ответа, а не в описании тикета.
            assert updated.attachments[0].comment_id == updated.comments[0].id, (
                "comment_id вложения должен совпадать с id созданного комментария"
            )
        finally:
            await _cleanup_ticket(ticket.id)

    async def test_reply_clears_sla_reply_pause(self):
        """Клиент ответил по email → sla_paused_by_reply = false, пауза накопилась."""
        from datetime import datetime, timedelta
        from backend.notifications.inbound import _handle_reply
        from backend.database import async_session_factory
        from backend.tickets.models import Ticket

        user = await _get_or_create_user("test-inbound@example.com", "Тест Ответ")
        ticket = await _create_ticket(str(user.id), "Проверка снятия reply-паузы")

        # Искусственно ставим reply-паузу на 1 час назад
        async with async_session_factory() as s:
            t = await s.get(Ticket, ticket.id)
            t.sla_paused_by_reply = True
            t.sla_paused_at = datetime.utcnow() - timedelta(hours=1)
            s.add(t)
            await s.commit()

        try:
            mail_data = {
                "subject": f"Re: [PASS24-{ticket.id[:8]}] Тест",
                "from_email": "test-inbound@example.com",
                "from_name": "Тест Ответ",
                "body": "Отвечаю",
                "attachments": [],
            }
            await _handle_reply(mail_data, ticket.id[:8])

            updated = await _get_ticket(ticket.id)
            assert updated.sla_paused_by_reply is False, "reply-флаг должен сняться"
            assert updated.sla_paused_at is None, "сводная пауза должна сняться"
            assert updated.sla_total_pause_seconds >= 3500, (
                f"пауза должна накопиться (~3600), получено {updated.sla_total_pause_seconds}"
            )
        finally:
            await _cleanup_ticket(ticket.id)

    async def test_reply_nonexistent_ticket(self):
        from backend.notifications.inbound import _handle_reply

        mail_data = {
            "subject": "Re: [PASS24-00000000] Несуществующий",
            "from_email": "test-inbound@example.com",
            "from_name": "Test",
            "body": "Текст",
            "attachments": [],
        }

        result = await _handle_reply(mail_data, "00000000")
        assert result is False, "Должен вернуть False для несуществующего тикета"

    async def test_reply_idempotent_by_message_id(self):
        """Повторный заход с тем же message_id не создаёт второй комментарий.

        Моделирует реальный сценарий: IMAP SINCE-окно / рестарт контейнера /
        сброс in-memory кеша — то же письмо попадает в `_handle_reply` дважды.
        Unique-индекс по `email_message_id` (миграция 022) должен защитить БД.
        """
        from backend.notifications.inbound import _handle_reply

        user = await _get_or_create_user("test-inbound@example.com", "Тест Ответ")
        ticket = await _create_ticket(str(user.id), "Идемпотентный ответ")

        try:
            mail_data = {
                "subject": f"Re: [PASS24-{ticket.id[:8]}] Идемпотентный ответ",
                "from_email": "test-inbound@example.com",
                "from_name": "Тест Ответ",
                "body": "Мой ответ",
                "attachments": [],
                "message_id": "<unique-reply-abc@example.com>",
            }

            first = await _handle_reply(mail_data, ticket.id[:8])
            second = await _handle_reply(mail_data, ticket.id[:8])
            assert first is True and second is True, (
                "Оба вызова должны завершиться успешно — второй просто без эффекта"
            )

            updated = await _get_ticket(ticket.id)
            assert len(updated.comments) == 1, (
                f"Ожидался 1 комментарий на повторной обработке, получено {len(updated.comments)}"
            )
            assert updated.comments[0].email_message_id == "<unique-reply-abc@example.com>"
        finally:
            await _cleanup_ticket(ticket.id)

    async def test_reply_duplicate_does_not_create_orphan_attachment(self):
        """Дубль с вложением: файл не должен записаться на диск и в БД."""
        from backend.notifications.inbound import _handle_reply

        user = await _get_or_create_user("test-inbound@example.com", "Тест Ответ")
        ticket = await _create_ticket(str(user.id), "Дубль с вложением")

        try:
            mail_data = {
                "subject": f"Re: [PASS24-{ticket.id[:8]}] Дубль с вложением",
                "from_email": "test-inbound@example.com",
                "from_name": "Тест Ответ",
                "body": "Вложение во вложении",
                "attachments": [_fake_attachment("dup.png", "image/png", 512)],
                "message_id": "<dup-with-att@example.com>",
            }

            await _handle_reply(mail_data, ticket.id[:8])
            await _handle_reply(mail_data, ticket.id[:8])

            updated = await _get_ticket(ticket.id)
            assert len(updated.comments) == 1
            assert len(updated.attachments) == 1, (
                f"На повторе вложение не должно записаться, получено {len(updated.attachments)}"
            )
        finally:
            await _cleanup_ticket(ticket.id)


class TestReplyBySubject:
    """Ответ без тега (Re: ...) → поиск тикета по теме."""

    async def test_reply_by_subject_creates_comment(self):
        from backend.notifications.inbound import _handle_reply_by_subject

        user = await _get_or_create_user("test-inbound@example.com", "Тест Ответ")
        ticket = await _create_ticket(str(user.id), "Проблема с домофоном")

        try:
            mail_data = {
                "subject": "Re: Заявка создана: Проблема с домофоном",
                "from_email": "test-inbound@example.com",
                "from_name": "Тест Ответ",
                "body": "Уточняю: домофон на 3 подъезде",
                "attachments": [],
            }

            result = await _handle_reply_by_subject(mail_data)
            assert result is True, "Ответ по теме должен быть обработан"

            updated = await _get_ticket(ticket.id)
            assert len(updated.comments) == 1
            assert "домофон на 3 подъезде" in updated.comments[0].text
        finally:
            await _cleanup_ticket(ticket.id)

    async def test_reply_by_subject_wrong_user(self):
        from backend.notifications.inbound import _handle_reply_by_subject

        user = await _get_or_create_user("test-inbound@example.com", "Тест Ответ")
        ticket = await _create_ticket(str(user.id), "Мой тикет")

        try:
            mail_data = {
                "subject": "Re: Заявка создана: Мой тикет",
                "from_email": "other-user@example.com",
                "from_name": "Другой",
                "body": "Не мой тикет",
                "attachments": [],
            }

            result = await _handle_reply_by_subject(mail_data)
            assert result is False, "Чужой пользователь не должен привязаться к тикету"
        finally:
            await _cleanup_ticket(ticket.id)


class TestNewTicketFromEmail:
    """Новое письмо → тикет + авто-анализ."""

    async def test_new_ticket_created(self):
        from unittest.mock import AsyncMock, patch
        from backend.notifications.inbound import _handle_new_ticket
        from backend.database import async_session_factory
        from backend.tickets.models import Ticket
        from sqlmodel import select

        test_email = f"test-new-{uuid.uuid4().hex[:8]}@example.com"

        # Мокаем отправку email чтобы не слать реальные письма из теста
        with patch("backend.notifications.email._send_email", new_callable=AsyncMock):
            await _handle_new_ticket({
                "subject": "Не работает шлагбаум на парковке",
                "from_email": test_email,
                "from_name": "Новый Пользователь",
                "body": "Шлагбаум не открывается, стою на парковке ЖК Солнечный уже 30 минут. Приложение показывает ошибку.",
                "attachments": [_fake_attachment("error.png", "image/png", 500)],
            })

            # Проверяем что тикет создан
            async with async_session_factory() as session:
                result = await session.execute(
                    select(Ticket).where(Ticket.contact_email == test_email)
                )
                ticket = result.scalar_one_or_none()
                assert ticket is not None, "Тикет должен быть создан"
                assert "шлагбаум" in ticket.title.lower() or "шлагбаум" in ticket.description.lower()
                assert ticket.source == "email"

                # Cleanup
                await _cleanup_ticket(ticket.id)

                # Cleanup user
                from backend.auth.models import User
                from sqlalchemy import delete as sa_delete
                await session.execute(sa_delete(User).where(User.email == test_email))
                await session.commit()

    async def test_insufficient_info_no_ticket(self):
        from unittest.mock import AsyncMock, patch
        from backend.notifications.inbound import _handle_new_ticket
        from backend.database import async_session_factory
        from backend.tickets.models import Ticket
        from sqlmodel import select

        test_email = f"test-short-{uuid.uuid4().hex[:8]}@example.com"

        with patch("backend.notifications.email._send_email", new_callable=AsyncMock):
            await _handle_new_ticket({
                "subject": "Ок",
                "from_email": test_email,
                "from_name": "Test",
                "body": "Ок",
                "attachments": [],
            })

        # Тикет НЕ должен быть создан (недостаточно информации)
        async with async_session_factory() as session:
            result = await session.execute(
                select(Ticket).where(Ticket.contact_email == test_email)
            )
            ticket = result.scalar_one_or_none()
            assert ticket is None, "Тикет не должен быть создан при недостаточной информации"


class TestKnowledgeBaseSearch:
    """Авто-анализ: поиск релевантных статей."""

    async def test_search_finds_articles(self):
        from backend.notifications.inbound import _search_knowledge_base
        from backend.database import async_session_factory

        async with async_session_factory() as session:
            articles = await _search_knowledge_base("открыть дверь", session)
            # Может найти или не найти — зависит от данных в БД
            # Проверяем что функция работает без ошибок
            assert isinstance(articles, list)
            for art in articles:
                assert "title" in art
                assert "slug" in art


class TestTagParsing:
    """Парсинг тега [PASS24-xxxxxxxx] из темы."""

    def test_tag_found(self):
        from backend.notifications.inbound import TICKET_TAG_RE

        subject = "Re: [PASS24-4467ddd8] Новый комментарий: Не могу зайти"
        match = TICKET_TAG_RE.search(subject)
        assert match is not None
        assert match.group(1) == "4467ddd8"

    def test_tag_not_found(self):
        from backend.notifications.inbound import TICKET_TAG_RE

        subject = "Re: Новый комментарий: Не могу зайти"
        match = TICKET_TAG_RE.search(subject)
        assert match is None

    def test_tag_case_insensitive(self):
        from backend.notifications.inbound import TICKET_TAG_RE

        subject = "Re: [pass24-AABB1122] Test"
        match = TICKET_TAG_RE.search(subject)
        assert match is not None
        assert match.group(1).lower() == "aabb1122"


class TestCleanBody:
    """Очистка тела письма."""

    def test_removes_quotes(self):
        from backend.notifications.inbound import _clean_body

        body = "Мой ответ\n> Цитата из предыдущего письма\n> Ещё цитата"
        cleaned = _clean_body(body)
        assert "Мой ответ" in cleaned
        assert "Цитата" not in cleaned

    def test_stops_at_signature(self):
        from backend.notifications.inbound import _clean_body

        body = "Текст ответа\n--\nС уважением, Тест"
        cleaned = _clean_body(body)
        assert "Текст ответа" in cleaned
        assert "С уважением" not in cleaned
