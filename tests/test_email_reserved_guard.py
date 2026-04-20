"""Юнит-тесты guard'а зарезервированных email-доменов (RFC 2606/6761)."""
from __future__ import annotations

import pytest

from backend.notifications.email import _is_reserved_address


@pytest.mark.parametrize("addr", [
    "test@example.com",
    "user@example.net",
    "agent@example.org",
    "USER@EXAMPLE.COM",
    "  user@example.com  ",
    "test-abc12345@example.com",
    "reset-fdba3dc9@example.com",
    "foo@bar.test",
    "foo@sub.example",
    "bob@invalid",
    "root@localhost",
    "root@my.localhost",
])
def test_reserved_addresses_detected(addr: str) -> None:
    assert _is_reserved_address(addr) is True, f"should be reserved: {addr!r}"


@pytest.mark.parametrize("addr", [
    "user@pass24online.ru",
    "support@pass24pro.ru",
    "john@gmail.com",
    "anna@yandex.ru",
    "admin@company.co",
    "user@examplecompany.com",  # не example.com, просто префикс
    "user@myexample.org",
])
def test_real_addresses_not_detected(addr: str) -> None:
    assert _is_reserved_address(addr) is False, f"should NOT be reserved: {addr!r}"


@pytest.mark.parametrize("addr", [
    "",
    "not-an-email",
    "@example.com",      # пустой локальный part — нерелевантно, но функция не должна падать
])
def test_malformed_does_not_crash(addr: str) -> None:
    # Не падает; точный bool-результат нас не интересует — главное, что не
    # кидает исключение при пустом/кривом вводе.
    result = _is_reserved_address(addr)
    assert isinstance(result, bool)
