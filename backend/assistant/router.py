"""
API-эндпоинт AI-помощника: принимает сообщение, ищет контекст в Qdrant,
отвечает через Claude с учётом базы знаний.
"""
from __future__ import annotations

import logging
from typing import Optional

import anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user
from backend.auth.models import User
from backend.config import settings
from backend.database import get_session

from .rag import search_knowledge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant", tags=["assistant"])

SYSTEM_PROMPT = """Ты — AI-помощник службы технической поддержки PASS24 Service Desk.

PASS24.online — облачная платформа для управления доступом на территорию жилых комплексов, коттеджных посёлков и бизнес-центров. Платформа включает:
- PASS24.online — управление пропусками через веб и мобильное приложение
- PASS24.Key — мобильные BLE-ключи для открытия дверей смартфоном
- PASS24.auto — распознавание автомобильных номеров
- PASS24.control — СКУД-контроллер
- Мобильное приложение — для iOS и Android

Твои задачи:
1. Отвечать на вопросы пользователей по продуктам PASS24
2. Помогать решать типичные проблемы (регистрация, пропуска, шлагбаумы, приложение)
3. Давать пошаговые инструкции
4. Если проблема требует вмешательства специалиста — рекомендовать создать заявку

Правила:
- Отвечай на русском языке
- Будь кратким и конкретным
- Давай пошаговые инструкции когда это уместно
- Используй информацию из базы знаний (контекст ниже)
- Если не знаешь ответа — честно скажи и предложи создать заявку
- Не выдумывай информацию, которой нет в контексте
- Будь дружелюбным и профессиональным"""


class ChatMessage(BaseModel):
    role: str = Field(..., description="user или assistant")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    reply: str
    sources: list[str] = Field(default_factory=list, description="Источники из базы знаний")
    suggest_ticket: bool = Field(default=False, description="Рекомендовать создать заявку")


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: Optional[User] = Depends(get_current_user),
) -> ChatResponse:
    """AI-помощник: отвечает на вопросы с учётом базы знаний PASS24."""
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI-помощник временно недоступен",
        )

    # 1. RAG — находим релевантные документы
    docs = search_knowledge(payload.message, limit=4)

    # 2. Формируем контекст из найденных документов
    context_parts = []
    sources = []
    for doc in docs:
        if doc["score"] > 0.3:  # порог релевантности
            context_parts.append(doc["text"])
            src = doc["source_file"]
            if src not in sources:
                sources.append(src)

    context_text = "\n\n---\n\n".join(context_parts) if context_parts else "Релевантных документов не найдено."

    # 3. Собираем историю + системный промпт
    messages = []
    for msg in payload.history[-10:]:  # последние 10 сообщений
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": payload.message})

    # 4. Вызов Claude
    try:
        client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_base_url,
        )

        full_system = f"""{SYSTEM_PROMPT}

--- КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ ---
{context_text}
--- КОНЕЦ КОНТЕКСТА ---

Пользователь: {current_user.full_name if current_user else 'Гость'}"""

        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            system=full_system,
            messages=messages,
        )

        reply = response.content[0].text

        # Определяем, нужно ли предложить создать заявку
        suggest_ticket = any(phrase in reply.lower() for phrase in [
            "создайте заявку", "обратитесь в поддержку", "создать заявку",
            "обратиться к специалисту", "требуется помощь специалиста",
            "не могу помочь", "к сожалению, не",
        ])

        logger.info(
            "AI chat: user=%s, query='%s', docs=%d, suggest_ticket=%s",
            current_user.email if current_user else "anon",
            payload.message[:50],
            len(context_parts),
            suggest_ticket,
        )

        return ChatResponse(
            reply=reply,
            sources=sources,
            suggest_ticket=suggest_ticket,
        )

    except Exception as exc:
        logger.error("Ошибка AI chat: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка AI-помощника. Попробуйте позже.",
        )
