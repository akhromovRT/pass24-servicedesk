"""
Переформатирование статей базы знаний по best practices.

Применяет трансформации к content существующих статей:
1. Удаляет дублирующий H1 в начале (title уже выводится на странице)
2. Конвертирует секции `## Важно`, `## Внимание`, `## Совет` в callout-блоки
3. В FAQ-статьях конвертирует `**Вопрос?**` → `### Вопрос?` (для TOC)
4. Нормализует whitespace (убирает лишние пустые строки)

Запуск:
  # Dry-run (показать diff, не менять)
  docker exec site-pass24-servicedesk python -m backend.scripts.reformat_articles

  # Применить
  docker exec site-pass24-servicedesk python -m backend.scripts.reformat_articles --apply
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re

from sqlmodel import select

from backend.database import async_session_factory
from backend.knowledge.models import Article

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)


# Маркеры для callout-блоков и соответствующие префиксы
CALLOUT_SECTIONS = {
    "Важно": "Важно",
    "Внимание": "Внимание",
    "Предупреждение": "Внимание",
    "Совет": "Совет",
    "Подсказка": "Совет",
    "Примечание": "Примечание",
    "Заметка": "Примечание",
}


def remove_duplicate_h1(content: str) -> str:
    """Удаляет первый H1 если он в самом начале (дублирует title)."""
    lines = content.split("\n")
    # Пропускаем ведущие пустые строки
    idx = 0
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx < len(lines) and lines[idx].startswith("# "):
        # Убираем H1 и последующие пустые строки
        idx += 1
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        return "\n".join(lines[idx:])
    return content


def convert_important_sections_to_callouts(content: str) -> str:
    """Конвертирует короткие `## Важно` секции в `> **Важно:** ...` callouts.

    Работает только если после `## Важно` идёт один короткий параграф (<250 символов)
    без списков и подзаголовков. Длинные секции оставляем как есть.
    """
    lines = content.split("\n")
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        match = re.match(r"^## (" + "|".join(CALLOUT_SECTIONS.keys()) + r")\s*$", line)
        if not match:
            result.append(line)
            i += 1
            continue

        section_name = match.group(1)
        callout_label = CALLOUT_SECTIONS[section_name]

        # Смотрим что после заголовка
        j = i + 1
        # Пропустим пустые строки
        while j < len(lines) and not lines[j].strip():
            j += 1

        # Собираем параграф до пустой строки / начала списка / начала подраздела
        paragraph_lines: list[str] = []
        k = j
        while k < len(lines):
            l = lines[k]
            s = l.strip()
            if not s:
                break
            if s.startswith(("- ", "* ", "#", ">")) or re.match(r"^\d+\. ", s):
                break
            paragraph_lines.append(l)
            k += 1

        paragraph = " ".join(ln.strip() for ln in paragraph_lines)
        # Конвертируем только короткие параграфы
        if paragraph and len(paragraph) < 250:
            result.append(f"> **{callout_label}:** {paragraph}")
            # Пропускаем обработанные строки
            i = k
            # Убедимся что после callout пустая строка
            if i < len(lines) and lines[i].strip():
                result.append("")
            continue

        # Длинный контент — оставляем секцию как H2 (не переформатируем)
        result.append(line)
        i += 1

    return "\n".join(result)


def convert_faq_bold_to_h3(content: str) -> str:
    """В FAQ статьях конвертирует `**Вопрос?**` в `### Вопрос?` для TOC.

    Срабатывает когда в параграфе только одна жирная строка заканчивающаяся на ?
    """
    lines = content.split("\n")
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        # Жирный вопрос на всю строку: **...?**
        match = re.match(r"^\*\*(.+\?)\*\*\s*$", stripped)
        if match:
            result.append(f"### {match.group(1)}")
        else:
            result.append(line)
        i += 1
    return "\n".join(result)


def normalize_whitespace(content: str) -> str:
    """Убирает лишние пустые строки (3+ подряд → 2)."""
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip() + "\n"


def reformat_content(content: str, is_faq: bool) -> str:
    """Применяет все трансформации."""
    content = remove_duplicate_h1(content)
    content = convert_important_sections_to_callouts(content)
    if is_faq:
        content = convert_faq_bold_to_h3(content)
    content = normalize_whitespace(content)
    return content


def show_diff(title: str, old: str, new: str, max_lines: int = 15) -> None:
    """Показывает короткое diff между старым и новым content."""
    print(f"\n{'=' * 70}")
    print(f"📄 {title}")
    print("=" * 70)

    # Показываем только первые N строк каждой версии, если они отличаются
    old_first = old.split("\n")[:max_lines]
    new_first = new.split("\n")[:max_lines]

    print("--- Было:")
    for ln in old_first:
        print(f"  | {ln}")
    if len(old.split("\n")) > max_lines:
        print(f"  | ... (+{len(old.split(chr(10))) - max_lines} строк)")

    print("+++ Стало:")
    for ln in new_first:
        print(f"  | {ln}")
    if len(new.split("\n")) > max_lines:
        print(f"  | ... (+{len(new.split(chr(10))) - max_lines} строк)")


async def run(apply: bool) -> None:
    mode = "APPLY" if apply else "DRY-RUN"
    logger.info("=== Reformat articles (%s) ===", mode)

    updated = 0
    skipped = 0
    total = 0

    async with async_session_factory() as session:
        result = await session.execute(select(Article))
        articles = result.scalars().all()
        total = len(articles)
        logger.info("Найдено статей: %d", total)

        for article in articles:
            is_faq_article = (
                article.article_type.value == "faq"
                if hasattr(article.article_type, "value")
                else str(article.article_type) == "faq"
            )
            new_content = reformat_content(article.content, is_faq=is_faq_article)

            if new_content.strip() == article.content.strip():
                skipped += 1
                continue

            show_diff(article.title, article.content, new_content)
            updated += 1

            if apply:
                article.content = new_content
                session.add(article)

        if apply:
            await session.commit()
            logger.info("✅ Обновлено: %d / %d, без изменений: %d", updated, total, skipped)
        else:
            logger.info(
                "DRY-RUN: будет обновлено %d / %d статей (без изменений: %d). Используйте --apply",
                updated, total, skipped,
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Переформатирование статей базы знаний")
    parser.add_argument("--apply", action="store_true", help="Сохранить изменения в БД (иначе dry-run)")
    args = parser.parse_args()
    asyncio.run(run(apply=args.apply))


if __name__ == "__main__":
    main()
