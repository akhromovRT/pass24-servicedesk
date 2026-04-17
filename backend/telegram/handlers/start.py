from aiogram import Router
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.telegram.config import APP_BASE_URL
from backend.telegram.keyboards.main_menu import main_menu_kb
from backend.telegram.services.linking import link_account, verify_token

router = Router(name="start")


@router.message(CommandStart(deep_link=True))
async def cmd_start_with_token(
    message: Message,
    command: CommandObject,
    **data,
) -> None:
    token = (command.args or "").strip()
    if not token:
        await _send_welcome_unlinked(message, compat_mode=bool(data.get("compat_mode")))
        return
    result = await verify_token(token)
    if not result:
        await message.answer(
            "🔗 <b>Ссылка недействительна</b>\n\n"
            "Возможные причины:\n"
            "• срок действия истёк (10 минут)\n"
            "• ссылка уже использована\n\n"
            "Сгенерируйте новую в настройках портала.",
            parse_mode="HTML",
        )
        return
    try:
        user = await link_account(token, message.chat.id)
    except ValueError:
        await message.answer("Не удалось привязать аккаунт. Попробуйте ещё раз.")
        return
    await message.answer(
        f"✅ Аккаунт привязан!\n\nДобро пожаловать, <b>{user.full_name}</b>.",
        parse_mode="HTML",
        reply_markup=main_menu_kb(user),
    )


@router.message(CommandStart())
async def cmd_start_plain(message: Message, **data) -> None:
    user = data.get("user")
    is_linked = data.get("is_linked", False)
    if is_linked and user:
        await message.answer(
            f"Здравствуйте, <b>{user.full_name}</b>!",
            parse_mode="HTML",
            reply_markup=main_menu_kb(user),
        )
    else:
        await _send_welcome_unlinked(message, compat_mode=bool(data.get("compat_mode")))


async def _send_welcome_unlinked(message: Message, compat_mode: bool = False) -> None:
    """Welcome for unlinked users.

    Two variants:
    - ``compat_mode=True``  → mention the new linking flow but keep the legacy
      "just write a message" behaviour available (the compat router handles
      text/media and creates ghost tickets).
    - ``compat_mode=False`` → strict "please link your account" message; text
      from unlinked users is ignored by downstream handlers.
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="🔗 Привязать аккаунт", url=f"{APP_BASE_URL}/settings#telegram")
    kb.adjust(1)
    if compat_mode:
        text = (
            "👋 <b>Добро пожаловать в PASS24 Service Desk!</b>\n\n"
            "📝 Можно <b>прямо сейчас</b> описать проблему одним сообщением — "
            "я создам заявку, и менеджер ответит вам сюда же (фото и файлы тоже принимаются).\n\n"
            "💡 Для доступа к меню, истории заявок, базе знаний и AI-чату — "
            "привяжите аккаунт PASS24."
        )
    else:
        text = (
            "👋 Добро пожаловать в PASS24 Service Desk!\n\n"
            "Чтобы начать работу, привяжите свой аккаунт — нажмите кнопку ниже, "
            "сгенерируйте ссылку в настройках портала, и вернитесь сюда."
        )
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=kb.as_markup(),
    )
