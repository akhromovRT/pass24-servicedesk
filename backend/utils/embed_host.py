"""Парсинг hostname страницы, на которой встроен AI-виджет PASS24.

Виджет шлёт `embed_host` в payload /tickets/guest. Здесь извлекается subdomain
для матча с Customer.subdomain.

Поддерживается только зона `pass24online.ru` (формат сайтов клиентов PASS24).
Для произвольных доменов возвращаем None — связывания не будет.
"""
from __future__ import annotations

import re
from typing import Optional

ROOT_DOMAIN = "pass24online.ru"
# Те же требования, что в seed-скрипте (DNS label, lowercase + дефисы).
SUBDOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def extract_subdomain(host: Optional[str]) -> Optional[str]:
    """`bristol.pass24online.ru` → `'bristol'`.

    Возвращает None, если:
      - host пустой или не строка,
      - host не оканчивается на `.pass24online.ru`,
      - между корнем и началом не ровно один label (вложенные поддомены не
        поддерживаются — это всегда подозрительная история),
      - первый label не проходит regex-валидацию.
    """
    if not host or not isinstance(host, str):
        return None
    cleaned = host.strip().lower()
    if not cleaned.endswith("." + ROOT_DOMAIN):
        return None
    label = cleaned[: -len("." + ROOT_DOMAIN)]
    if not label or "." in label:
        return None
    if not SUBDOMAIN_RE.match(label):
        return None
    return label
