"""Knowledge base services — shared by the HTTP router and the Telegram bot.

This module centralises the FTS-with-ILIKE-fallback pipeline used by
``knowledge/router.py::search_articles`` and
``telegram/services/kb_service.py::search_articles``. Both call sites had
near-identical SQL copies; routing through a single service keeps them in
sync and makes the pipeline behaviour easier to reason about.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from .models import Article, ArticleCategory, ArticleType
from .synonyms import expand_query


async def search_articles_with_fts(
    session: AsyncSession,
    query: str,
    *,
    limit: int = 20,
    offset: int = 0,
    article_type: Optional[ArticleType] = None,
    category: Optional[ArticleCategory] = None,
    tag: Optional[str] = None,
) -> tuple[list[Article], int]:
    """Search published articles via Postgres FTS with ILIKE fallback.

    Pipeline:
    1. Query expansion via synonyms dictionary (``expand_query``).
    2. Weighted ``to_tsvector`` on title (A), synonyms (A), tags (B), content (C)
       matched against ``websearch_to_tsquery('russian', :query)``.
    3. Rank with ``ts_rank_cd`` desc, then ``created_at`` desc.
    4. If FTS returns 0 rows, retry with ``ILIKE '%original_query%'`` over
       title/content — typo-friendly fallback.

    Args:
        session: active AsyncSession.
        query: user input (not expanded).
        limit/offset: pagination.
        article_type/category/tag: optional filters.

    Returns:
        (articles, total) — `total` is the pre-pagination count for the current
        filter set (uses ILIKE count if FTS was empty).
    """
    expanded = expand_query(query)

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

    base_filter = (Article.is_published == True) & fts_condition  # noqa: E712

    stmt = select(Article).where(base_filter)
    count_stmt = select(func.count()).select_from(Article).where(base_filter)

    if article_type is not None:
        stmt = stmt.where(Article.article_type == article_type)
        count_stmt = count_stmt.where(Article.article_type == article_type)
    if category is not None:
        stmt = stmt.where(Article.category == category)
        count_stmt = count_stmt.where(Article.category == category)
    if tag:
        tag_filter = sa_text("tags @> CAST(:tag_arr AS jsonb)").bindparams(
            tag_arr=f'["{tag}"]'
        )
        stmt = stmt.where(tag_filter)
        count_stmt = count_stmt.where(tag_filter)

    total = int((await session.execute(count_stmt)).scalar_one() or 0)

    if total == 0:
        # ILIKE fallback on the ORIGINAL query (not expanded) — forgiving for typos.
        search_pattern = f"%{query}%"
        ilike_filter = (
            (Article.is_published == True)  # noqa: E712
            & (Article.title.ilike(search_pattern) | Article.content.ilike(search_pattern))
        )
        stmt = select(Article).where(ilike_filter)
        count_stmt = select(func.count()).select_from(Article).where(ilike_filter)
        if article_type is not None:
            stmt = stmt.where(Article.article_type == article_type)
            count_stmt = count_stmt.where(Article.article_type == article_type)
        if category is not None:
            stmt = stmt.where(Article.category == category)
            count_stmt = count_stmt.where(Article.category == category)
        if tag:
            tag_filter = sa_text("tags @> CAST(:tag_arr AS jsonb)").bindparams(
                tag_arr=f'["{tag}"]'
            )
            stmt = stmt.where(tag_filter)
            count_stmt = count_stmt.where(tag_filter)
        total = int((await session.execute(count_stmt)).scalar_one() or 0)

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

    stmt = stmt.order_by(rank_expr, Article.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    articles = list(result.scalars().all())
    return articles, total
