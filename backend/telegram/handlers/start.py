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
        await _send_welcome_unlinked(message)
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
        await _send_welcome_unlinked(message)


async def _send_welcome_unlinked(message: Message) -> None:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔗 Привязать аккаунт", url=f"{APP_BASE_URL}/settings#telegram")
    kb.adjust(1)
    await message.answer(
        "👋 Добро пожаловать в PASS24 Service Desk!\n\n"
        "Чтобы начать работу, привяжите свой аккаунт — нажмите кнопку ниже, "
        "сгенерируйте ссылку в настройках портала, и вернитесь сюда.",
        reply_markup=kb.as_markup(),
    )
