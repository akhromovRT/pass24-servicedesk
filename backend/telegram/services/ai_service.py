"""Trimmed AI wrapper for the Telegram bot.

Deliberately lighter than ``backend/assistant/router.py`` (which does role-
adaptive prompting + ticket-data extraction). Here we just want:
  - RAG lookup via ``backend.assistant.rag.search_knowledge`` (best-effort)
  - Claude call via ``AsyncAnthropic`` (best-effort)
  - Graceful fallback when either piece is unavailable

NEVER raises to the caller — always returns a ``{answer, sources}`` dict.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.config import settings

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = (
    "Ты — AI-помощник PASS24 Service Desk. "
    "Отвечай на русском языке, кратко и по делу. "
    "Опирайся на предоставленный контекст из базы знаний. "
    "Если не знаешь ответа или вопрос выходит за рамки контекста — "
    "честно признайся и предложи создать заявку в поддержку."
)

_HISTORY_TURN_LIMIT = 6  # last N role-content entries kept for prompt budget
_FALLBACK_ANSWER = (
    "🤖 AI-ассистент временно недоступен. Попробуйте поиск по базе знаний "
    "(📚 База знаний) или создайте заявку (📝 Новая заявка)."
)


def _fallback(query: str) -> dict:
    return {"answer": _FALLBACK_ANSWER, "sources": []}


async def _rag_search(query: str, limit: int = 5) -> list[dict]:
    """Call RAG safely — off the event loop, never raise."""
    try:
        from backend.assistant.rag import search_knowledge
    except Exception as exc:  # pragma: no cover — import guard
        logger.warning("ai_service: cannot import search_knowledge: %s", exc)
        return []
    try:
        docs = await asyncio.to_thread(search_knowledge, query, limit)
        return docs or []
    except Exception as exc:
        logger.warning("ai_service: search_knowledge failed: %s", exc)
        return []


def _build_user_prompt(query: str, docs: list[dict]) -> str:
    """Concatenate the user query with a short RAG context block.

    ``search_knowledge`` returns ``{text, source_file, score}``, not a KB
    article record. We extract the text and source_file and expose them as
    snippets — the caller's 'sources' surface degrades gracefully when the
    shape differs from what we expect.
    """
    parts: list[str] = [f"Вопрос: {query}"]
    if docs:
        parts.append("")
        parts.append("Контекст из базы знаний:")
        for i, d in enumerate(docs[:3], start=1):
            text = (d.get("text") or d.get("content") or "")[:500]
            source = d.get("source_file") or d.get("title") or d.get("slug") or ""
            if source:
                parts.append(f"[{i}] {source}")
            if text:
                parts.append(text)
    return "\n".join(parts)


def _sources_from_docs(docs: list[dict]) -> list[dict]:
    """Return up to 3 source dicts ``{title, slug}`` for the bot UI.

    ``search_knowledge`` doesn't expose slug/title, only ``source_file``. We
    map source_file → title and leave slug empty; the bot turns an empty slug
    into a dead-link button suppression. If the payload shape changes to
    include slug/title, they are preferred.
    """
    out: list[dict] = []
    for d in docs[:3]:
        title = d.get("title") or d.get("source_file") or ""
        slug = d.get("slug") or ""
        if not title:
            continue
        out.append({"title": str(title), "slug": str(slug)})
    return out


async def ask(query: str, history: list[dict] | None = None) -> dict:
    """Answer a user query using RAG + Claude.

    Args:
        query: user's latest message.
        history: optional list of ``{"role": "user"|"assistant", "content": str}``
            entries. The last ``_HISTORY_TURN_LIMIT`` are kept.

    Returns:
        ``{"answer": str, "sources": [{"title": str, "slug": str}, ...]}``
        Always — on any failure returns a fallback dict.
    """
    query = (query or "").strip()
    if not query:
        return {"answer": "Пожалуйста, задайте вопрос текстом.", "sources": []}

    api_key = getattr(settings, "anthropic_api_key", "") or ""
    if not api_key:
        return _fallback(query)

    # Best-effort RAG — empty context is fine, Claude can still answer general qs.
    docs = await _rag_search(query, limit=5)

    # Build Claude messages: prior history (clamped) + current user turn.
    messages: list[dict] = []
    if history:
        for entry in history[-_HISTORY_TURN_LIMIT:]:
            role = entry.get("role")
            content = entry.get("content")
            if role in ("user", "assistant") and isinstance(content, str) and content:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": _build_user_prompt(query, docs)})

    try:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(
            api_key=api_key,
            base_url=getattr(settings, "anthropic_base_url", None) or None,
        )
        msg = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            system=_SYSTEM_PROMPT,
            messages=messages,
        )
        # Extract the first text block.
        answer = ""
        if getattr(msg, "content", None):
            first = msg.content[0]
            answer = getattr(first, "text", "") or ""
        if not answer:
            answer = "Не удалось сформировать ответ. Попробуйте переформулировать вопрос."
    except Exception as exc:
        logger.warning("ai_service: Anthropic call failed: %s", exc)
        return _fallback(query)

    return {"answer": answer, "sources": _sources_from_docs(docs)}
