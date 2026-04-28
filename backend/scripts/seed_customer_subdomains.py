"""Идемпотентный seed-скрипт для заполнения customers.subdomain из CSV.

Используется для bootstrap: после миграции 027 у всех Customer'ов поле
subdomain пустое. Этот скрипт получает CSV-файл с парами «subdomain → ИНН»
(или «subdomain → customer_id» при флаге --by-id) и проставляет значения
в БД. Повторный прогон с тем же CSV — no-op.

Формат CSV (header в первой строке):

    subdomain,inn
    bristol,7708123456
    zhk-rassvet,7706987654

Запуск:

    docker exec site-pass24-servicedesk python -m backend.scripts.seed_customer_subdomains \\
        --csv /tmp/subdomains.csv --dry-run
    docker exec site-pass24-servicedesk python -m backend.scripts.seed_customer_subdomains \\
        --csv /tmp/subdomains.csv

Валидация: subdomain ^[a-z0-9][a-z0-9-]{0,62}$ (lowercase + дефисы, не
начинается с дефиса). Не валиден — строка пропускается с warning'ом, отчёт
в конце прогонa.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import re
import sys
from datetime import datetime

from sqlmodel import select

from backend.customers.models import Customer
from backend.database import async_session_factory

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

SUBDOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


async def seed(csv_path: str, by_id: bool, dry_run: bool) -> dict[str, int]:
    """Применяет CSV к customers.subdomain. Возвращает summary."""
    summary = {"updated": 0, "unchanged": 0, "not_found": 0, "invalid": 0, "total": 0}

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    summary["total"] = len(rows)
    if not rows:
        logger.warning("CSV пустой: %s", csv_path)
        return summary

    key_field = "customer_id" if by_id else "inn"
    expected_headers = {"subdomain", key_field}
    actual_headers = set(reader.fieldnames or [])
    missing = expected_headers - actual_headers
    if missing:
        raise SystemExit(
            f"В CSV отсутствуют столбцы: {missing}. "
            f"Ожидается заголовок: subdomain,{key_field}"
        )

    async with async_session_factory() as session:
        for idx, row in enumerate(rows, start=2):  # idx учитывает header (1) + 1-based
            subdomain = (row.get("subdomain") or "").strip().lower()
            key_value = (row.get(key_field) or "").strip()
            if not subdomain or not key_value:
                logger.warning("Строка %d: пустые значения, пропуск", idx)
                summary["invalid"] += 1
                continue
            if not SUBDOMAIN_RE.match(subdomain):
                logger.warning(
                    "Строка %d: subdomain %r невалиден (regex %s), пропуск",
                    idx, subdomain, SUBDOMAIN_RE.pattern,
                )
                summary["invalid"] += 1
                continue

            if by_id:
                stmt = select(Customer).where(Customer.id == key_value)
            else:
                stmt = select(Customer).where(Customer.inn == key_value)
            result = await session.execute(stmt)
            customer = result.scalar_one_or_none()
            if not customer:
                logger.warning(
                    "Строка %d: Customer с %s=%r не найден, пропуск",
                    idx, key_field, key_value,
                )
                summary["not_found"] += 1
                continue

            if customer.subdomain == subdomain:
                logger.info(
                    "Строка %d: subdomain=%r у Customer.id=%s уже совпадает, no-op",
                    idx, subdomain, customer.id,
                )
                summary["unchanged"] += 1
                continue

            old = customer.subdomain
            if not dry_run:
                customer.subdomain = subdomain
                customer.updated_at = datetime.utcnow()
                session.add(customer)
            logger.info(
                "Строка %d: Customer.id=%s subdomain %r → %r%s",
                idx, customer.id, old, subdomain, " [dry-run]" if dry_run else "",
            )
            summary["updated"] += 1

        if not dry_run:
            await session.commit()

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--csv", required=True, help="Путь к CSV-файлу")
    parser.add_argument(
        "--by-id", action="store_true",
        help="В CSV ключ — Customer.id (по умолчанию ИНН)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Не коммитить изменения")
    args = parser.parse_args()

    summary = asyncio.run(seed(args.csv, args.by_id, args.dry_run))
    logger.info(
        "[summary] всего=%d, обновлено=%d, без_изменений=%d, не_найдено=%d, невалидных=%d%s",
        summary["total"], summary["updated"], summary["unchanged"],
        summary["not_found"], summary["invalid"],
        " (dry-run)" if args.dry_run else "",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
