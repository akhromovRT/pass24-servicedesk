"""Thin KB search service for the Telegram bot.

Duplicates the FTS ranking query in ``backend.knowledge.router.search_articles``
because the HTTP route bakes request/response shaping into the same function.
A future cleanup should extract the shared SQL into a service layer so both
entrypoints call the same code — tracked as a follow-up for the knowledge
module refactor (out of scope for Telegram bot v2 Task 8).
"""
from __future__ import annotations

from sqlalchemy import text as sa_text
from sqlmodel import select

from backend.database import async_session_factory
from backend.knowledge.models import Article
from backend.knowledge.synonyms import expand_query


async def search_articles(query: str, limit: int = 3) -> list[dict]:
    """FTS search over the knowledge base.

    Returns ``[{id, slug, title, category, article_type, helpful_count,
    not_helpful_count}]``. Empty list when the query is blank or when both
    FTS and ILIKE fallback produce no hits.
    """
    q = (query or "").strip()
    if not q:
        return []

    expanded = expand_query(q)

    # FTS — same weighted tsvector as backend/knowledge/router.py.
    fts_condition = sa_text(
        """
        (
            setweight(to_tsvector('russian', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('russian', coalesce(
                (SELECT string_agg(value, ' ') FROM jsonb_array_elements_text(synonyms) AS value),
                ''
            )), 'A') ||
            setweight(to_tsvector('russian', coalesce(
                (SELECT string_agg(value, ' ') FROM jsonb_array_elements_text(tags) AS value),
                ''
            )), 'B') ||
            setweight(to_tsvector('russian', coalesce(content, '')), 'C')
        ) @@ websearch_to_tsquery('russian', :query)
        """
    ).bindparams(query=expanded)

    rank_expr = sa_text(
        """
        ts_rank_cd(
            setweight(to_tsvector('russian', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('russian', coalesce(
                (SELECT string_agg(value, ' ') FROM jsonb_array_elements_text(synonyms) AS value),
                ''
            )), 'A') ||
            setweight(to_tsvector('russian', coalesce(
                (SELECT string_agg(value, ' ') FROM jsonb_array_elements_text(tags) AS value),
                ''
            )), 'B') ||
            setweight(to_tsvector('russian', coalesce(content, '')), 'C'),
            websearch_to_tsquery('russian', :query)
        ) DESC
        """
    ).bindparams(query=expanded)

    async with async_session_factory() as session:
        stmt = (
            select(Article)
            .where(Article.is_published == True, fts_condition)  # noqa: E712
            .order_by(rank_expr, Article.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        articles = result.scalars().all()

        if not articles:
            # Fallback: ILIKE on title | content with the ORIGINAL (non-expanded) query.
            pattern = f"%{q}%"
            stmt = (
                select(Article)
                .where(
                    Article.is_published == True,  # noqa: E712
                    Article.title.ilike(pattern) | Article.content.ilike(pattern),
                )
                .order_by(Article.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            articles = result.scalars().all()

        return [
            {
                "id": str(a.id),
                "slug": a.slug,
                "title": a.title,
                "category": a.category.value if hasattr(a.category, "value") else str(a.category or ""),
                "article_type": a.article_type.value if hasattr(a.article_type, "value") else str(a.article_type or ""),
                "helpful_count": int(a.helpful_count or 0),
                "not_helpful_count": int(a.not_helpful_count or 0),
            }
            for a in articles
        ]


async def get_article_by_slug(slug: str) -> dict | None:
    """Fetch one published article by slug. Returns dict or None."""
    if not slug:
        return None
    async with async_session_factory() as session:
        result = await session.execute(
            select(Article).where(
                Article.slug == slug,
                Article.is_published == True,  # noqa: E712
            ).limit(1)
        )
        article = result.scalar_one_or_none()
        if article is None:
            return None
        return {
            "id": str(article.id),
            "slug": article.slug,
            "title": article.title,
            "content": article.content,
            "category": article.category.value if hasattr(article.category, "value") else str(article.category or ""),
            "article_type": article.article_type.value if hasattr(article.article_type, "value") else str(article.article_type or ""),
        }
