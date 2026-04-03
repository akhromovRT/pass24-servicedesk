"""
RAG-поиск: находит релевантные документы в Qdrant по запросу пользователя.
Использует OpenAI embeddings (text-embedding-3-small, dim=1536) через тот же proxy.
"""
from __future__ import annotations

import logging
from typing import Optional

from backend.config import settings

logger = logging.getLogger(__name__)

_qdrant_client = None
_openai_client = None


def _get_qdrant():
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient
        _qdrant_client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )
    return _qdrant_client


def _get_openai():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        # Используем тот же proxy что и pass24-api
        base_url = settings.anthropic_base_url.replace("/anthropic", "/openai/v1")
        _openai_client = OpenAI(
            api_key=settings.anthropic_api_key,
            base_url=base_url,
        )
    return _openai_client


def search_knowledge(query: str, limit: int = 5) -> list[dict]:
    """
    Семантический поиск по базе знаний Qdrant.
    Возвращает список {text, source_file, score}.
    """
    if not settings.qdrant_api_key:
        logger.warning("QDRANT_API_KEY не задан — RAG недоступен")
        return []

    try:
        # Получаем embedding запроса
        openai = _get_openai()
        resp = openai.embeddings.create(
            input=query,
            model="text-embedding-3-small",
        )
        query_vector = resp.data[0].embedding

        # Ищем в Qdrant
        qdrant = _get_qdrant()
        results = qdrant.search(
            collection_name=settings.qdrant_collection,
            query_vector=query_vector,
            limit=limit,
            with_payload=True,
        )

        docs = []
        for point in results:
            docs.append({
                "text": point.payload.get("text", "")[:2000],
                "source_file": point.payload.get("source_file", "unknown"),
                "score": round(point.score, 3),
            })

        logger.info("RAG: query='%s' → %d документов", query[:50], len(docs))
        return docs

    except Exception as exc:
        logger.error("Ошибка RAG-поиска: %s", exc)
        return []
