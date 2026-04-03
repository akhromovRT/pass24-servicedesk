"""
AI-помощник PASS24 Service Desk.
Роль-ориентированный: адаптирует ответы под тип пользователя.
При рекомендации создать заявку — возвращает предзаполненные данные.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

import anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.auth.dependencies import get_current_user
from backend.auth.models import User
from backend.config import settings

from .rag import search_knowledge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant", tags=["assistant"])

# Роли пользователей → контекст для AI
ROLE_CONTEXTS = {
    "resident": {
        "name": "Пользователь мобильного приложения",
        "description": "Житель ЖК/БЦ, использует мобильное приложение PASS24 для заказа пропусков, QR-кодов, BLE-ключей.",
        "focus": "мобильное приложение, пропуска, QR-коды, регистрация, BLE-ключи PASS24.Key, гостевые пропуска",
        "product_default": "mobile_app",
    },
    "property_manager": {
        "name": "Администратор системы",
        "description": "Сотрудник УК или администратор объекта, управляет облаком PASS24.online через веб-интерфейс.",
        "focus": "веб-интерфейс pass24.online, модули (пропуска, пользователи, адреса, объекты, запросы), настройка объектов, отчёты, импорт, массовая рассылка",
        "product_default": "pass24_online",
    },
    "support_agent": {
        "name": "Агент поддержки / Монтажник",
        "description": "Специалист технической поддержки или монтажник, работает с оборудованием и интеграциями.",
        "focus": "настройка оборудования (контроллеры PASS24.control, камеры, считыватели), интеграции (Sigur, TRASSIR, ZKTeco), монтаж, диагностика",
        "product_default": "equipment",
    },
    "admin": {
        "name": "Системный администратор",
        "description": "Руководитель поддержки с полным доступом ко всем модулям.",
        "focus": "все продукты и модули PASS24, аналитика, управление пользователями, SLA",
        "product_default": "pass24_online",
    },
}

SYSTEM_PROMPT = """Ты — AI-помощник службы технической поддержки PASS24 Service Desk.

PASS24.online — облачная платформа для управления доступом на территорию ЖК, КП и БЦ.

Продукты платформы:
- **Мобильное приложение PASS24** — для жителей: заказ пропусков, QR-коды, приглашения
- **PASS24.Key** — мобильные BLE-ключи для открытия дверей смартфоном
- **PASS24.online (веб)** — для администраторов УК: управление пропусками, пользователями, объектами
- **PASS24.auto** — распознавание автомобильных номеров для шлагбаумов
- **PASS24.control** — СКУД-контроллер, оборудование, монтаж
- **PASS24.guard** — рабочее место охранника

РОЛЬ ПОЛЬЗОВАТЕЛЯ: {role_name}
{role_description}
Фокус ответов: {role_focus}

Правила:
- Отвечай на русском, кратко и конкретно
- Адаптируй ответ под роль пользователя
- Давай пошаговые инструкции
- Используй информацию из контекста базы знаний
- Если не можешь решить проблему — ОБЯЗАТЕЛЬНО предложи создать заявку
- Не выдумывай то, чего нет в контексте
- Будь дружелюбным

ВАЖНО: Когда предлагаешь создать заявку, в конце ответа добавь блок:
```ticket
{{"title": "краткое описание проблемы", "description": "подробное описание из контекста переписки", "product": "product_code", "category": "category_code"}}
```
product: pass24_online, mobile_app, pass24_key, pass24_control, pass24_auto, equipment, integration, other
category: registration, passes, recognition, app_issues, objects, trusted_persons, equipment_issues, consultation, feature_request, other"""


class ChatMessage(BaseModel):
    role: str
    content: str


class TicketData(BaseModel):
    """Предзаполненные данные для создания заявки."""
    title: str = ""
    description: str = ""
    product: str = "pass24_online"
    category: str = "other"
    ticket_type: str = "problem"


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    reply: str
    sources: list[str] = Field(default_factory=list)
    suggest_ticket: bool = False
    ticket_data: Optional[TicketData] = None


def _extract_ticket_data(text: str) -> tuple[str, Optional[TicketData]]:
    """Извлекает блок ```ticket из ответа AI и возвращает очищенный текст + данные."""
    match = re.search(r"```ticket\s*\n?(.*?)\n?```", text, re.DOTALL)
    if not match:
        return text, None

    clean_text = text[:match.start()].rstrip()
    try:
        data = json.loads(match.group(1).strip())
        return clean_text, TicketData(**data)
    except (json.JSONDecodeError, TypeError):
        return clean_text, None


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: Optional[User] = Depends(get_current_user),
) -> ChatResponse:
    """AI-помощник с учётом роли пользователя и автозаполнением заявки."""
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI-помощник временно недоступен",
        )

    # Определяем роль
    user_role = current_user.role if current_user else "resident"
    role_ctx = ROLE_CONTEXTS.get(user_role, ROLE_CONTEXTS["resident"])

    # RAG
    docs = search_knowledge(payload.message, limit=4)
    context_parts = []
    sources = []
    for doc in docs:
        if doc["score"] > 0.3:
            context_parts.append(doc["text"])
            src = doc["source_file"]
            if src not in sources:
                sources.append(src)

    context_text = "\n\n---\n\n".join(context_parts) if context_parts else "Релевантных документов не найдено."

    # История
    messages = []
    for msg in payload.history[-10:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": payload.message})

    # System prompt с ролью
    full_system = SYSTEM_PROMPT.format(
        role_name=role_ctx["name"],
        role_description=role_ctx["description"],
        role_focus=role_ctx["focus"],
    ) + f"""

--- КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ ---
{context_text}
--- КОНЕЦ КОНТЕКСТА ---

Пользователь: {current_user.full_name if current_user else 'Гость'} ({role_ctx['name']})"""

    try:
        client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_base_url,
        )

        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            system=full_system,
            messages=messages,
        )

        raw_reply = response.content[0].text

        # Извлекаем ticket_data из ответа
        reply, ticket_data = _extract_ticket_data(raw_reply)

        # Определяем suggest_ticket
        suggest_ticket = ticket_data is not None or any(phrase in reply.lower() for phrase in [
            "создайте заявку", "создать заявку", "обратитесь в поддержку",
            "обратиться к специалисту", "требуется помощь специалиста",
        ])

        # Если suggest но нет ticket_data — создаём из контекста переписки
        if suggest_ticket and not ticket_data:
            # Собираем контекст из переписки
            user_messages = [m.content for m in payload.history if m.role == "user"]
            user_messages.append(payload.message)
            context_summary = "; ".join(user_messages[-3:])

            ticket_data = TicketData(
                title=payload.message[:200],
                description=context_summary[:2000],
                product=role_ctx["product_default"],
                category="other",
            )

        logger.info(
            "AI chat: user=%s, role=%s, docs=%d, suggest=%s",
            current_user.email if current_user else "anon",
            user_role,
            len(context_parts),
            suggest_ticket,
        )

        return ChatResponse(
            reply=reply,
            sources=sources,
            suggest_ticket=suggest_ticket,
            ticket_data=ticket_data,
        )

    except Exception as exc:
        logger.error("Ошибка AI chat: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка AI-помощника. Попробуйте позже.",
        )
