"""Unit-тесты для _strip_quoted_reply.

Проверяет, что функция корректно отрезает цитируемые предыдущие письма
от свежего ответа клиента для популярных почтовых клиентов (Gmail, Outlook,
Apple Mail, Яндекс), в русском и английском формате.
"""
from backend.notifications.inbound import _strip_quoted_reply


def test_empty_body_passthrough():
    assert _strip_quoted_reply("") == ""
    # Строка из одних пробелов — вся обрезается как trailing blank
    assert _strip_quoted_reply("   ") == ""


def test_plain_text_without_quote_unchanged():
    body = "Здравствуйте! У меня не работает пропуск в ЖК Рассвет.\nПомогите разобраться."
    assert _strip_quoted_reply(body) == body


def test_gmail_english_quote_stripped():
    body = (
        "Спасибо, теперь всё работает!\n"
        "\n"
        "On Mon, Apr 13, 2026 at 10:30 AM, Support <support@pass24online.ru> wrote:\n"
        "> Здравствуйте! Попробуйте переустановить приложение.\n"
        "> С уважением, поддержка PASS24"
    )
    result = _strip_quoted_reply(body)
    assert result == "Спасибо, теперь всё работает!"


def test_gmail_russian_quote_stripped():
    body = (
        "Да, проблема ушла.\n"
        "\n"
        "В понедельник, 13 апреля 2026 г., Support <support@pass24online.ru> пишет:\n"
        "> Попробуйте следующее..."
    )
    assert _strip_quoted_reply(body) == "Да, проблема ушла."


def test_apple_mail_russian_quote_stripped():
    body = (
        "Отлично, решено, спасибо!\n"
        "\n"
        "13 апреля 2026 г., 10:30, Иван Петров <ivan@example.com> написал(а):\n"
        "\n"
        "Предыдущий текст письма, который должен быть обрезан."
    )
    assert _strip_quoted_reply(body) == "Отлично, решено, спасибо!"


def test_classic_gt_quoting_stripped():
    body = (
        "Короткий ответ клиента.\n"
        "\n"
        "> Предыдущий текст поддержки\n"
        "> ещё одна строка цитаты\n"
        ">\n"
        "> подпись в цитате"
    )
    assert _strip_quoted_reply(body) == "Короткий ответ клиента."


def test_outlook_original_message_separator_en():
    body = (
        "Перепроверил, всё ок.\n"
        "\n"
        "-----Original Message-----\n"
        "From: Support <support@pass24online.ru>\n"
        "Sent: Monday, April 13, 2026 10:30 AM\n"
        "To: Ivan Petrov <ivan@example.com>\n"
        "Subject: Re: [PASS24-a1b2c3d4] Не работает пропуск\n"
        "\n"
        "Здравствуйте..."
    )
    assert _strip_quoted_reply(body) == "Перепроверил, всё ок."


def test_outlook_original_message_separator_ru():
    body = (
        "Сделал как вы сказали.\n"
        "\n"
        "-----Исходное сообщение-----\n"
        "От: Support\n"
        "Отправлено: понедельник, 13 апреля 2026 г. 10:30\n"
        "Кому: ivan@example.com\n"
        "Тема: Re: [PASS24-a1b2c3d4] Не работает пропуск"
    )
    assert _strip_quoted_reply(body) == "Сделал как вы сказали."


def test_outlook_header_block_without_separator():
    """Outlook forward без явного separator, только блок из From:/Sent:/To:/Subject:"""
    body = (
        "Привет, перенаправляю вам письмо.\n"
        "\n"
        "From: Support <support@pass24online.ru>\n"
        "Sent: Monday, April 13, 2026 10:30 AM\n"
        "To: Ivan Petrov <ivan@example.com>\n"
        "Subject: Re: Не работает пропуск\n"
        "\n"
        "Здравствуйте..."
    )
    assert _strip_quoted_reply(body) == "Привет, перенаправляю вам письмо."


def test_outlook_russian_header_block():
    body = (
        "Пересылаю вам свежий ответ.\n"
        "\n"
        "От: Поддержка <support@pass24online.ru>\n"
        "Отправлено: 13 апреля 2026 г., 10:30\n"
        "Кому: ivan@example.com\n"
        "Тема: Re: [PASS24-a1b2c3d4]"
    )
    assert _strip_quoted_reply(body) == "Пересылаю вам свежий ответ."


def test_underscore_separator():
    body = (
        "Новое сообщение от меня.\n"
        "\n"
        "________________________________\n"
        "From: Support\n"
        "Здравствуйте, Иван!"
    )
    assert _strip_quoted_reply(body) == "Новое сообщение от меня."


def test_forwarded_message_separator():
    body = (
        "Передаю заявку.\n"
        "\n"
        "---------- Forwarded message ----------\n"
        "From: client@example.com\n"
        "Дата: ..."
    )
    assert _strip_quoted_reply(body) == "Передаю заявку."


def test_nested_thread_cuts_at_first_marker():
    """Трёхуровневая переписка — режется на самом первом маркере."""
    body = (
        "Третье сообщение клиента.\n"
        "\n"
        "On Tue, Apr 14, 2026 at 11:00 AM, Support wrote:\n"
        "> Второе сообщение поддержки\n"
        ">\n"
        "> В понедельник, 13 апреля 2026 г., Client пишет:\n"
        "> > Первое сообщение клиента"
    )
    assert _strip_quoted_reply(body) == "Третье сообщение клиента."


def test_single_header_line_not_enough_to_strip():
    """Одна строка 'From:' в середине текста — не Outlook-блок, не режем."""
    body = (
        "Видел объявление в стиле 'From: admin' — это явно подделка.\n"
        "Прошу проверить."
    )
    # Одинокая 'From:' без других заголовков рядом — не срабатывает
    assert _strip_quoted_reply(body) == body


def test_body_starting_with_quote_becomes_empty():
    """Если письмо начинается сразу с цитаты — тело пустое."""
    body = "> Всё что написано, это цитата\n> и тут тоже"
    assert _strip_quoted_reply(body) == ""


def test_trailing_blank_lines_before_marker_trimmed():
    body = (
        "Ответ клиента\n"
        "\n"
        "\n"
        "On Mon, Apr 13, 2026 at 10:30 AM, Support wrote:\n"
        "> цитата"
    )
    assert _strip_quoted_reply(body) == "Ответ клиента"
