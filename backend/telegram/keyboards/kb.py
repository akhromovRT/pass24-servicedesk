from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


_BUTTON_LABEL_LIMIT = 55


def _truncate(text: str, limit: int) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def kb_search_results_kb(articles: list[dict]) -> InlineKeyboardMarkup:
    """List of article buttons + [📝 Не нашёл — создать заявку] + [🏠 Меню].

    Callback pattern: ``kb:open:<slug>``.

    NOTE: callback_data is capped at 64 bytes by Telegram. The `kb:open:` prefix
    costs 8 bytes, leaving ~56 bytes for the slug. If a slug exceeds ~50 chars,
    the callback will be rejected. All current slugs in the KB fit comfortably,
    but if a longer slug appears, we fall back to a truncated slug with a
    trailing marker so the click at least routes somewhere sane — the open
    handler will simply answer "Статья не найдена" since the truncated slug
    won't match. A future cleanup should switch to `kb:openid:<short_id>`.
    """
    builder = InlineKeyboardBuilder()

    for art in articles:
        title = art.get("title") or ""
        slug = art.get("slug") or ""
        label = _truncate(f"📄 {title}", _BUTTON_LABEL_LIMIT)
        # Guard oversized slug → truncate (handler will 'not found' it).
        cb_slug = slug if len(slug) <= 50 else slug[:48] + "…"
        builder.row(
            InlineKeyboardButton(text=label, callback_data=f"kb:open:{cb_slug}")
        )

    builder.row(
        InlineKeyboardButton(
            text="📝 Не нашёл — создать заявку",
            callback_data="kb:mkticket:none",
        )
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Меню", callback_data="mm:main")
    )
    return builder.as_markup()


def kb_article_kb(slug: str) -> InlineKeyboardMarkup:
    """Article-view keyboard.

    [👍 Помогло] [👎 Не помогло]
    [📝 Создать заявку по теме]
    [⬅ Назад к результатам] [🏠 Меню]
    """
    builder = InlineKeyboardBuilder()

    # Same slug-length guard as above.
    cb_slug = slug if len(slug) <= 50 else slug[:48] + "…"

    builder.row(
        InlineKeyboardButton(
            text="👍 Помогло",
            callback_data=f"kb:helpful:{cb_slug}:yes",
        ),
        InlineKeyboardButton(
            text="👎 Не помогло",
            callback_data=f"kb:helpful:{cb_slug}:no",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="📝 Создать заявку по теме",
            callback_data=f"kb:mkticket:{cb_slug}",
        )
    )
    builder.row(
        InlineKeyboardButton(text="⬅ Назад к результатам", callback_data="kb:back"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="mm:main"),
    )
    return builder.as_markup()
