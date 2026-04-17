from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.telegram.formatters import escape_html
from backend.telegram.keyboards.kb import kb_article_kb, kb_search_results_kb
from backend.telegram.services.kb_service import get_article_by_slug, search_articles

logger = logging.getLogger(__name__)

router = Router(name="kb")


class KbStates(StatesGroup):
    awaiting_query = State()


_QUERY_PROMPT = (
    "📚 <b>База знаний</b>\n\n"
    "Напишите, что ищете (2–3 слова достаточно)."
)

_ARTICLE_CONTENT_LIMIT = 3500
_SNIPPET_LIMIT = 120


def _menu_only_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Меню", callback_data="mm:main")
    builder.adjust(1)
    return builder.as_markup()


def _snippet(text: str, limit: int = _SNIPPET_LIMIT) -> str:
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


async def _render_results(
    chat_target: Message | CallbackQuery,
    query: str,
    articles: list[dict],
    state: FSMContext,
) -> None:
    """Render the search results list.

    If the entry is a CallbackQuery, edits the existing message. If it's a
    Message (incoming user text), answers with a new message.
    """
    await state.update_data(kb_last_query=query)

    if not articles:
        text = (
            "📚 <b>Результаты для:</b> «" + escape_html(query) + "»\n\n"
            "Ничего не нашёл. Можно создать заявку, и мы разберёмся лично."
        )
        builder = InlineKeyboardBuilder()
        # Encode the query into the mkticket callback. Truncate hard so the
        # 64-byte ceiling isn't breached (prefix = 14 chars → ~50 free).
        stub = (query or "").strip()[:40].replace(":", " ")
        builder.button(
            text="📝 Создать заявку",
            callback_data=f"kb:mkticket:{stub}" if stub else "kb:mkticket:none",
        )
        builder.button(text="🏠 Меню", callback_data="mm:main")
        builder.adjust(1)
        kb = builder.as_markup()
    else:
        lines: list[str] = [
            "📚 <b>Результаты для:</b> «" + escape_html(query) + "»",
            "",
        ]
        for art in articles:
            title = escape_html(art.get("title") or "")
            # kb_service.search_articles returns {id, slug, title, category,
            # article_type, helpful_count, not_helpful_count} — no content
            # snippet. Use category as a compact one-line subtitle.
            subtitle_raw = art.get("category") or art.get("article_type") or ""
            subtitle = escape_html(_snippet(subtitle_raw))
            if subtitle:
                lines.append(f"📄 <b>{title}</b>\n{subtitle}")
            else:
                lines.append(f"📄 <b>{title}</b>")
        text = "\n".join(lines)
        kb = kb_search_results_kb(articles)

    if isinstance(chat_target, CallbackQuery):
        if chat_target.message:
            try:
                await chat_target.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
            except TelegramBadRequest as exc:
                logger.debug("kb results edit skipped: %s", exc)
    else:
        await chat_target.answer(text, parse_mode="HTML", reply_markup=kb)


# --- mm:kb entry ---------------------------------------------------------


@router.callback_query(F.data == "mm:kb")
async def cb_kb_entry(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await state.set_state(KbStates.awaiting_query)
    # Reset any previous search context.
    await state.update_data(kb_last_query=None)
    if callback.message:
        try:
            await callback.message.edit_text(
                _QUERY_PROMPT,
                parse_mode="HTML",
                reply_markup=_menu_only_kb(),
            )
        except TelegramBadRequest as exc:
            logger.debug("kb entry edit skipped: %s", exc)
    await callback.answer()


# --- ft:kb entry (free-text fallback) ------------------------------------


@router.callback_query(F.data == "ft:kb")
async def cb_ft_to_kb(callback: CallbackQuery, state: FSMContext, **data) -> None:
    """Free-text fallback sent the captured text into the KB search."""
    existing = await state.get_data()
    pending = (existing.get("pending_text") or "").strip()

    await state.set_state(KbStates.awaiting_query)

    if pending:
        try:
            articles = await search_articles(pending, limit=5)
        except Exception as exc:
            logger.warning("kb search failed: %s", exc)
            articles = []
        await _render_results(callback, pending, articles, state)
        await callback.answer()
        return

    # No pending text — fall through to the regular awaiting_query prompt.
    if callback.message:
        try:
            await callback.message.edit_text(
                _QUERY_PROMPT,
                parse_mode="HTML",
                reply_markup=_menu_only_kb(),
            )
        except TelegramBadRequest as exc:
            logger.debug("kb ft entry edit skipped: %s", exc)
    await callback.answer()


# --- query text ----------------------------------------------------------


@router.message(KbStates.awaiting_query, F.text)
async def msg_kb_query(message: Message, state: FSMContext, **data) -> None:
    query = (message.text or "").strip()
    if not query:
        return
    try:
        articles = await search_articles(query, limit=5)
    except Exception as exc:
        logger.warning("kb search failed: %s", exc)
        articles = []
    # Keep the FSM state so consecutive searches work without re-entering.
    await _render_results(message, query, articles, state)


# --- kb:open:<slug> ------------------------------------------------------


@router.callback_query(F.data.startswith("kb:open:"))
async def cb_kb_open(callback: CallbackQuery, state: FSMContext, **data) -> None:
    slug = (callback.data or "").split(":", 2)[2] if callback.data else ""
    article = await get_article_by_slug(slug)
    if not article:
        await callback.answer("Статья не найдена", show_alert=False)
        return

    title = article.get("title") or ""
    content = article.get("content") or ""
    if len(content) > _ARTICLE_CONTENT_LIMIT:
        content = content[: _ARTICLE_CONTENT_LIMIT - 1].rstrip() + "…"
    text = f"📄 <b>{escape_html(title)}</b>\n\n{escape_html(content)}"

    if callback.message:
        try:
            await callback.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=kb_article_kb(slug),
            )
        except TelegramBadRequest as exc:
            logger.debug("kb article edit skipped: %s", exc)
    await callback.answer()


# --- kb:helpful:<slug>:<yes|no> -----------------------------------------


@router.callback_query(F.data.startswith("kb:helpful:"))
async def cb_kb_helpful(callback: CallbackQuery, state: FSMContext, **data) -> None:
    """Persist 👍/👎 into ArticleFeedback; idempotent per (user, article)."""
    parts = (callback.data or "").split(":")
    # kb:helpful:<slug>:<yes|no>
    if len(parts) < 4:
        await callback.answer()
        return
    slug = ":".join(parts[2:-1])  # slugs may contain colons (edge case)
    verdict = parts[-1]
    helpful = verdict == "yes"

    user = data.get("user")
    if user is None:
        await callback.answer("Нужна авторизация.", show_alert=True)
        return

    session_key = f"tg:{user.id}"  # one row per (user, article) — unique constraint in DB
    try:
        from sqlmodel import select

        from backend.database import async_session_factory
        from backend.knowledge.models import Article, ArticleFeedback

        async with async_session_factory() as session:
            article = (await session.execute(
                select(Article).where(Article.slug == slug, Article.is_published == True)  # noqa: E712
            )).scalar_one_or_none()
            if article is None:
                await callback.answer("Статья не найдена.", show_alert=True)
                return
            # Idempotency: if this user already voted on this article, don't double-count.
            existing = (await session.execute(
                select(ArticleFeedback).where(
                    ArticleFeedback.session_id == session_key,
                    ArticleFeedback.article_id == str(article.id),
                )
            )).scalar_one_or_none()
            if existing is None:
                session.add(ArticleFeedback(
                    article_id=str(article.id),
                    session_id=session_key,
                    user_id=str(user.id),
                    helpful=helpful,
                    source="telegram",
                ))
                if helpful:
                    article.helpful_count += 1
                else:
                    article.not_helpful_count += 1
                session.add(article)
                await session.commit()
    except Exception:  # noqa: BLE001 — feedback capture must never break the flow
        logger.exception("kb_helpful persist failed for slug=%s", slug)

    await callback.answer("Спасибо!" if helpful else "Учли.", show_alert=False)


# --- kb:mkticket:<slug|none|query-stub> ---------------------------------


@router.callback_query(F.data.startswith("kb:mkticket:"))
async def cb_kb_mkticket(callback: CallbackQuery, state: FSMContext, **data) -> None:
    """Jump into the ticket wizard seeded with an article ref or the last query.

    Duplicates ~10 lines of setup from ``tickets_create.cb_start_wizard`` —
    flagged as a refactor candidate. A shared ``start_wizard(...)`` helper
    would remove the duplication.
    """
    raw = (callback.data or "").split(":", 2)
    suffix = raw[2] if len(raw) == 3 else ""

    # Build description seed.
    seed_lines: list[str] = []
    existing = await state.get_data()
    pending = (existing.get("pending_text") or "").strip()
    last_query = (existing.get("kb_last_query") or "").strip()

    if suffix and suffix not in ("none", ""):
        # Could be a slug or a truncated query stub. We don't distinguish —
        # both go into a note so the PM sees the context.
        seed_lines.append(f"Из статьи / поиска: {suffix}")
    elif last_query:
        seed_lines.append(f"Поиск в базе знаний: {last_query}")

    if pending:
        if seed_lines:
            seed_lines.append("")
        seed_lines.append(pending)

    description_seed = "\n".join(seed_lines).strip()

    # Lazy import to avoid circular imports with tickets_create.
    from backend.telegram.handlers.tickets_create import (
        CreateTicketStates,
        _PRODUCT_PROMPT,
    )
    from backend.telegram.keyboards.ticket_wizard import product_kb

    await state.set_state(CreateTicketStates.product)
    new_data: dict = {"attachments": []}
    if description_seed:
        new_data["description"] = description_seed
        new_data["pending_text"] = description_seed
    await state.set_data(new_data)

    if callback.message:
        try:
            await callback.message.edit_text(
                _PRODUCT_PROMPT,
                parse_mode="HTML",
                reply_markup=product_kb(),
            )
        except TelegramBadRequest as exc:
            logger.debug("kb mkticket edit skipped: %s", exc)
    await callback.answer()


# --- kb:back -------------------------------------------------------------


@router.callback_query(F.data == "kb:back")
async def cb_kb_back(callback: CallbackQuery, state: FSMContext, **data) -> None:
    """Return to the last search results (re-runs the query)."""
    existing = await state.get_data()
    last_query = (existing.get("kb_last_query") or "").strip()
    if not last_query:
        # No prior query — fall back to the awaiting_query prompt.
        await state.set_state(KbStates.awaiting_query)
        if callback.message:
            try:
                await callback.message.edit_text(
                    _QUERY_PROMPT,
                    parse_mode="HTML",
                    reply_markup=_menu_only_kb(),
                )
            except TelegramBadRequest as exc:
                logger.debug("kb back empty edit skipped: %s", exc)
        await callback.answer()
        return

    try:
        articles = await search_articles(last_query, limit=5)
    except Exception as exc:
        logger.warning("kb search failed: %s", exc)
        articles = []
    await state.set_state(KbStates.awaiting_query)
    await _render_results(callback, last_query, articles, state)
    await callback.answer()
