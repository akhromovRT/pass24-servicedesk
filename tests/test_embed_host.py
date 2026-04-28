"""Unit-тесты на backend.utils.embed_host.extract_subdomain.

Чистая функция, БД не нужна. Запуск: `pytest tests/test_embed_host.py -v`.
"""
from __future__ import annotations

import pytest

from backend.utils.embed_host import extract_subdomain


class TestExtractSubdomain:
    def test_simple_subdomain(self):
        assert extract_subdomain("bristol.pass24online.ru") == "bristol"

    def test_uppercase_normalized(self):
        assert extract_subdomain("BRISTOL.Pass24Online.RU") == "bristol"

    def test_whitespace_stripped(self):
        assert extract_subdomain("  bristol.pass24online.ru  ") == "bristol"

    def test_with_dashes_and_digits(self):
        assert extract_subdomain("zhk-rassvet-2.pass24online.ru") == "zhk-rassvet-2"

    def test_root_domain_rejected(self):
        # сам pass24online.ru без поддомена — не клиентский сайт
        assert extract_subdomain("pass24online.ru") is None

    def test_other_domain(self):
        assert extract_subdomain("example.com") is None
        assert extract_subdomain("client-site.ru") is None

    def test_nested_subdomain_rejected(self):
        # foo.bar.pass24online.ru — два label'а перед корнем, не наш формат
        assert extract_subdomain("foo.bar.pass24online.ru") is None

    def test_empty(self):
        assert extract_subdomain("") is None
        assert extract_subdomain(None) is None

    def test_non_string(self):
        assert extract_subdomain(123) is None  # type: ignore[arg-type]

    def test_invalid_label_starting_with_dash(self):
        assert extract_subdomain("-bristol.pass24online.ru") is None

    def test_invalid_label_with_underscore(self):
        # underscore — не валидный DNS label
        assert extract_subdomain("zhk_rassvet.pass24online.ru") is None

    def test_label_too_long(self):
        long_label = "a" * 64  # лимит 63
        assert extract_subdomain(f"{long_label}.pass24online.ru") is None

    def test_pass24pro_domain_rejected(self):
        # Наш собственный support-домен — не клиентский сайт
        assert extract_subdomain("support.pass24pro.ru") is None
