"""Thin KB search wrapper for the Telegram bot.

Delegates FTS search to ``backend.knowledge.services.search_articles_with_fts``
so the bot and the HTTP API share a single implementation.
"""
from __future__ import annotations

from sqlmodel import select

from backend.database import async_session_factory
from backend.knowledge.models import Article
from backend.knowledge.services import search_articles_with_fts


def _article_to_dict(article: Article) -> dict:
    return {
        "id": str(article.id),
        "slug": article.slug,
        "title": article.title,
        "category": (
            article.category.value
            if hasattr(article.category, "value")
            else str(article.category or "")
        ),
        "article_type": (
            article.article_type.value
            if hasattr(article.article_type, "value")
            else str(article.article_type or "")
        ),
        "helpful_count": int(article.helpful_count or 0),
        "not_helpful_count": int(article.not_helpful_count or 0),
    }


async def search_articles(query: str, limit: int = 3) -> list[dict]:
    """Top-N KB articles for a user query.

    Returns dicts — ORM objects would be detached once the session closes here.
    Empty list on empty query or when both FTS + ILIKE fallback produce no hits.
    """
    q = (query or "").strip()
    if not q:
        return []
    async with async_session_factory() as session:
        articles, _total = await search_articles_with_fts(
            session, q, limit=limit, offset=0,
        )
        return [_article_to_dict(a) for a in articles]


async def get_article_by_slug(slug: str) -> dict | None:
    """Fetch one published article by slug. Returns dict or None."""
    if not slug:
        return None
    async with async_session_factory() as session:
        article = (await session.execute(
            select(Article).where(
                Article.slug == slug,
                Article.is_published == True,  # noqa: E712
            ).limit(1)
        )).scalar_one_or_none()
        if article is None:
            return None
        return {
            "id": str(article.id),
            "slug": article.slug,
            "title": article.title,
            "content": article.content,
            "category": (
                article.category.value
                if hasattr(article.category, "value")
                else str(article.category or "")
            ),
            "article_type": (
                article.article_type.value
                if hasattr(article.article_type, "value")
                else str(article.article_type or "")
            ),
        }
