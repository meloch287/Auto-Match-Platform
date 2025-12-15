import logging
import uuid
from typing import Any, Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.callbacks import ChatCallback, MatchCallback
from app.bot.states import ChatStates
from app.models.chat import ChatStatusEnum
from app.services.chat import ChatService

logger = logging.getLogger(__name__)

router = Router(name="chat")

def build_chat_list_keyboard(
    chats: list,
    _: Any,
    user_id: uuid.UUID,
) -> Any:
    """Build keyboard with list of chats."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    
    builder = InlineKeyboardBuilder()
    
    for chat in chats:
        status_emoji = "💬" if chat.status == ChatStatusEnum.ACTIVE else "📁"
        
        builder.button(
            text=f"{status_emoji} Chat #{str(chat.id)[:8]}",
            callback_data=ChatCallback(action="open", id=str(chat.id)),
        )
    
    builder.adjust(1)
    return builder.as_markup()

def build_chat_actions_keyboard(
    chat_id: str,
    _: Any,
    can_reveal: bool = True,
    both_revealed: bool = False,
) -> Any:
    """Build chat action buttons keyboard."""
    builder = InlineKeyboardBuilder()
    
    if can_reveal and not both_revealed:
        builder.button(
            text=f"🔓 {_('chat.reveal')}",
            callback_data=ChatCallback(action="reveal", id=chat_id),
        )
    
    builder.button(
        text=f"🚫 {_('chat.report')}",
        callback_data=ChatCallback(action="report", id=chat_id),
    )
    builder.button(
        text=f"🚪 {_('chat.close')}",
        callback_data=ChatCallback(action="close", id=chat_id),
    )
    builder.button(
        text=_('buttons.back'),
        callback_data="chat:list",
    )
    
    builder.adjust(3, 1)
    return builder.as_markup()

def build_reveal_confirm_keyboard(chat_id: str, _: Any) -> Any:

    builder = InlineKeyboardBuilder()
    
    builder.button(
        text=f"✅ {_('buttons.yes')}",
        callback_data=ChatCallback(action="reveal_confirm", id=chat_id),
    )
    builder.button(
        text=f"❌ {_('buttons.no')}",
        callback_data=ChatCallback(action="reveal_decline", id=chat_id),
    )
    
    builder.adjust(2)
    return builder.as_markup()

def build_report_confirm_keyboard(chat_id: str, _: Any) -> Any:

    builder = InlineKeyboardBuilder()
    
    builder.button(
        text=f"✅ {_('buttons.confirm')}",
        callback_data=ChatCallback(action="report_confirm", id=chat_id),
    )
    builder.button(
        text=f"❌ {_('buttons.cancel')}",
        callback_data=ChatCallback(action="open", id=chat_id),
    )
    
    builder.adjust(2)
    return builder.as_markup()

@router.message(Command("my_chats"))
async def cmd_my_chats(
    message: Message,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """
    Handle /my_chats command - show user's active chat sessions.
    
    Requirements: 7.1
    """
    if not db_session or not user:
        await message.answer(_("chats.empty"))
        return
    
    chat_service = ChatService(db_session)
    chats = await chat_service.get_chats_for_user(user.id, status=ChatStatusEnum.ACTIVE)
    
    if not chats:
        await message.answer(_("chats.empty"))
        return
    
    text = f"<b>{_('chats.my_chats')}</b>\n\n"
    
    for i, chat in enumerate(chats, 1):
        status_emoji = "💬" if chat.status == ChatStatusEnum.ACTIVE else "📁"
        last_msg = ""
        if chat.last_message_at:
            last_msg = f" | {chat.last_message_at.strftime('%d.%m %H:%M')}"
        
        text += f"{status_emoji} <b>#{i}</b> Chat{last_msg}\n"
    
    text += f"\n{_('chats.anonymous_notice')}"
    
    keyboard = build_chat_list_keyboard(list(chats), _, user.id)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "chat:list")
async def cb_chat_list(
    callback: CallbackQuery,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Handle back to chat list."""
    await callback.answer()
    
    if not db_session or not user:
        await callback.message.edit_text(_("chats.empty"))
        return
    
    chat_service = ChatService(db_session)
    chats = await chat_service.get_chats_for_user(user.id, status=ChatStatusEnum.ACTIVE)
    
    if not chats:
        await callback.message.edit_text(_("chats.empty"))
        return
    
    text = f"<b>{_('chats.my_chats')}</b>\n\n"
    
    for i, chat in enumerate(chats, 1):
        status_emoji = "💬" if chat.status == ChatStatusEnum.ACTIVE else "📁"
        last_msg = ""
        if chat.last_message_at:
            last_msg = f" | {chat.last_message_at.strftime('%d.%m %H:%M')}"
        
        text += f"{status_emoji} <b>#{i}</b> Chat{last_msg}\n"
    
    text += f"\n{_('chats.anonymous_notice')}"
    
    keyboard = build_chat_list_keyboard(list(chats), _, user.id)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(ChatCallback.filter(F.action == "open"))
async def cb_open_chat(
    callback: CallbackQuery,
    callback_data: ChatCallback,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """
    Open a chat session for messaging.
    
    Requirements: 7.3
    """
    await callback.answer()
    
    if not db_session or not user:
        await callback.message.edit_text(_("errors.general"))
        return
    
    try:
        chat_id = uuid.UUID(callback_data.id)
    except ValueError:
        await callback.message.edit_text(_("errors.not_found"))
        return
    
    chat_service = ChatService(db_session)
    
    is_participant = await chat_service.is_user_in_chat(chat_id, user.id)
    if not is_participant:
        await callback.message.edit_text(_("errors.not_found"))
        return
    
    chat = await chat_service.get_chat_with_messages(chat_id, message_limit=10)
    if not chat:
        await callback.message.edit_text(_("errors.not_found"))
        return
    
    from app.repositories.match import MatchRepository
    from app.repositories.listing import ListingRepository
    from app.repositories.requirement import RequirementRepository
    
    match_repo = MatchRepository(db_session)
    listing_repo = ListingRepository(db_session)
    req_repo = RequirementRepository(db_session)
    
    match = await match_repo.get(chat.match_id)
    if not match:
        await callback.message.edit_text(_("errors.not_found"))
        return
    
    listing = await listing_repo.get(match.listing_id)
    requirement = await req_repo.get(match.requirement_id)
    
    if not listing or not requirement:
        await callback.message.edit_text(_("errors.not_found"))
        return
    
    if user.id == requirement.user_id:
        user_alias = chat.buyer_alias
        other_alias = chat.seller_alias
    else:
        user_alias = chat.seller_alias
        other_alias = chat.buyer_alias
    
    text = f"<b>💬 {_('chats.my_chats')}</b>\n\n"
    text += f"👤 {_('chat.started').format(alias=user_alias)}\n"
    text += f"🗣️ {other_alias}\n\n"
    
    if chat.both_revealed:
        text += f"✅ {_('chat.reveal_confirmed').format(contact='@...')}\n\n"
    
    if chat.messages:
        text += "<b>Recent messages:</b>\n"
        for msg in chat.messages[-5:]:
            if msg.sender_id == user.id:
                sender = "You"
            else:
                sender = other_alias
            content = msg.content[:50] if msg.content else "[media]"
            text += f"• <b>{sender}:</b> {content}\n"
    
    text += f"\n💡 Send a message to reply"
    
    await state.set_state(ChatStates.chatting)
    await state.update_data(active_chat_id=str(chat_id))
    
    can_reveal = not (
        (user.id == requirement.user_id and chat.buyer_revealed) or
        (user.id == listing.user_id and chat.seller_revealed)
    )
    
    keyboard = build_chat_actions_keyboard(
        str(chat_id), _, 
        can_reveal=can_reveal,
        both_revealed=chat.both_revealed
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(MatchCallback.filter(F.action == "contact"))
async def cb_contact_from_match(
    callback: CallbackQuery,
    callback_data: MatchCallback,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """
    Initiate chat from a match when buyer clicks "Contact".
    
    Creates anonymous chat with generated aliases.
    
    Requirements: 1.1
    """
    await callback.answer()
    
    if not db_session or not user:
        await callback.message.edit_text(_("errors.general"))
        return
    
    try:
        match_id = uuid.UUID(callback_data.id)
    except ValueError:
        await callback.message.edit_text(_("errors.not_found"))
        return
    
    chat_service = ChatService(db_session)
    
    chat = await chat_service.create_chat_from_match(match_id)
    
    if not chat:
        await callback.message.edit_text(_("errors.not_found"))
        return
    
    from app.repositories.match import MatchRepository
    from app.repositories.listing import ListingRepository
    from app.repositories.requirement import RequirementRepository
    
    match_repo = MatchRepository(db_session)
    listing_repo = ListingRepository(db_session)
    req_repo = RequirementRepository(db_session)
    
    match = await match_repo.get(match_id)
    if not match:
        await callback.message.edit_text(_("errors.not_found"))
        return
    
    listing = await listing_repo.get(match.listing_id)
    requirement = await req_repo.get(match.requirement_id)
    
    if not listing or not requirement:
        await callback.message.edit_text(_("errors.not_found"))
        return
    
    if user.id == requirement.user_id:
        user_alias = chat.buyer_alias
        other_alias = chat.seller_alias
    else:
        user_alias = chat.seller_alias
        other_alias = chat.buyer_alias
    
    text = f"<b>{_('chats.created')}</b>\n\n"
    text += f"{_('chat.started').format(alias=user_alias)}\n"
    text += f"🗣️ {other_alias}\n\n"
    text += f"{_('chats.anonymous_notice')}\n\n"
    text += f"💡 Send a message to start the conversation"
    
    await state.set_state(ChatStates.chatting)
    await state.update_data(active_chat_id=str(chat.id))
    
    keyboard = build_chat_actions_keyboard(str(chat.id), _, can_reveal=True)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    
    logger.info(f"Chat {chat.id} created between users for match {match_id}")

@router.message(ChatStates.chatting)
async def process_chat_message(
    message: Message,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """
    Handle incoming messages in chat state.
    
    Routes messages between buyer and seller.
    
    Requirements: 1.2
    """
    if not db_session or not user:
        await message.answer(_("errors.general"))
        return
    
    data = await state.get_data()
    chat_id_str = data.get("active_chat_id")
    
    if not chat_id_str:
        await message.answer(_("errors.session_expired"))
        await state.clear()
        return
    
    try:
        chat_id = uuid.UUID(chat_id_str)
    except ValueError:
        await message.answer(_("errors.session_expired"))
        await state.clear()
        return
    
    chat_service = ChatService(db_session)
    
    from app.models.chat import MessageTypeEnum
    
    content = None
    message_type = MessageTypeEnum.TEXT
    media_url = None
    
    if message.text:
        content = message.text[:4000]
        message_type = MessageTypeEnum.TEXT
    elif message.photo:
        media_url = message.photo[-1].file_id
        message_type = MessageTypeEnum.PHOTO
        content = message.caption[:4000] if message.caption else None
    elif message.location:
        content = f"{message.location.latitude},{message.location.longitude}"
        message_type = MessageTypeEnum.LOCATION
    else:
        await message.answer(_("errors.invalid_input"))
        return
    
    result = await chat_service.send_message(
        chat_id=chat_id,
        sender_id=user.id,
        content=content,
        message_type=message_type,
        media_url=media_url,
    )
    
    if not result:
        await message.answer(_("errors.general"))
        return
    
    await message.answer(_("chats.message_sent"))
    
    logger.info(f"Message sent in chat {chat_id} by user {user.id}")

@router.callback_query(ChatCallback.filter(F.action == "reveal"))
async def cb_reveal_request(
    callback: CallbackQuery,
    callback_data: ChatCallback,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """
    Handle reveal contact request.
    
    Requirements: 1.3
    """
    await callback.answer()
    
    if not db_session or not user:
        await callback.message.edit_text(_("errors.general"))
        return
    
    chat_id = callback_data.id
    
    text = f"🔓 <b>{_('chat.reveal')}</b>\n\n"
    text += "Are you sure you want to reveal your contact information?\n"
    text += "The other party will also need to agree."
    
    keyboard = build_reveal_confirm_keyboard(chat_id, _)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(ChatCallback.filter(F.action == "reveal_confirm"))
async def cb_reveal_confirm(
    callback: CallbackQuery,
    callback_data: ChatCallback,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """
    Confirm contact reveal request.
    
    Requirements: 1.4
    """
    await callback.answer()
    
    if not db_session or not user:
        await callback.message.edit_text(_("errors.general"))
        return
    
    try:
        chat_id = uuid.UUID(callback_data.id)
    except ValueError:
        await callback.message.edit_text(_("errors.not_found"))
        return
    
    chat_service = ChatService(db_session)
    
    result = await chat_service.request_reveal(chat_id, user.id)
    
    if not result.success:
        await callback.message.edit_text(_("errors.general"))
        return
    
    if result.both_revealed:
        text = f"✅ <b>{_('chat.reveal_confirmed').format(contact='')}</b>\n\n"
        
        if result.buyer_contact:
            text += f"👤 Buyer: @{result.buyer_contact}\n"
        if result.seller_contact:
            text += f"🏠 Seller: @{result.seller_contact}\n"
        
        keyboard = build_chat_actions_keyboard(
            callback_data.id, _, 
            can_reveal=False, 
            both_revealed=True
        )
    else:
        text = f"⏳ {_('chat.reveal_pending')}\n\n"
        text += _('chats.reveal_requested')
        
        keyboard = build_chat_actions_keyboard(
            callback_data.id, _, 
            can_reveal=False
        )
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    
    logger.info(f"Reveal requested in chat {chat_id} by user {user.id}")

@router.callback_query(ChatCallback.filter(F.action == "reveal_decline"))
async def cb_reveal_decline(
    callback: CallbackQuery,
    callback_data: ChatCallback,
    _: Any,
) -> None:
    """Handle reveal decline - go back to chat."""
    await callback.answer()
    
    callback_data_new = ChatCallback(action="open", id=callback_data.id)
    await callback.message.edit_text(
        _("chats.reveal_declined"),
        reply_markup=build_chat_actions_keyboard(callback_data.id, _, can_reveal=True)
    )

@router.callback_query(ChatCallback.filter(F.action == "report"))
async def cb_report_chat(
    callback: CallbackQuery,
    callback_data: ChatCallback,
    _: Any,
) -> None:
    """
    Handle report chat button.
    
    Requirements: 1.5
    """
    await callback.answer()
    
    chat_id = callback_data.id
    
    text = f"🚫 <b>{_('chat.report')}</b>\n\n"
    text += "Are you sure you want to report this chat?\n"
    text += "The chat will be flagged for admin review."
    
    keyboard = build_report_confirm_keyboard(chat_id, _)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(ChatCallback.filter(F.action == "report_confirm"))
async def cb_report_confirm(
    callback: CallbackQuery,
    callback_data: ChatCallback,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """
    Confirm chat report.
    
    Requirements: 1.5
    """
    await callback.answer()
    
    if not db_session or not user:
        await callback.message.edit_text(_("errors.general"))
        return
    
    try:
        chat_id = uuid.UUID(callback_data.id)
    except ValueError:
        await callback.message.edit_text(_("errors.not_found"))
        return
    
    chat_service = ChatService(db_session)
    
    chat = await chat_service.report_chat(
        chat_id,
        reported_by=user.id,
        reason="Reported via bot",
    )
    
    if not chat:
        await callback.message.edit_text(_("errors.not_found"))
        return
    
    text = f"✅ {_('chat.reported')}\n\n"
    text += "Thank you for your report. Our moderators will review this chat."
    
    from app.bot.keyboards.builders import build_start_over_keyboard
    keyboard = build_start_over_keyboard(_)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    
    logger.info(f"Chat {chat_id} reported by user {user.id}")

@router.callback_query(ChatCallback.filter(F.action == "close"))
async def cb_close_chat(
    callback: CallbackQuery,
    callback_data: ChatCallback,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Handle close chat - archive and exit."""
    await callback.answer()
    
    if not db_session or not user:
        await callback.message.edit_text(_("errors.general"))
        return
    
    try:
        chat_id = uuid.UUID(callback_data.id)
    except ValueError:
        await callback.message.edit_text(_("errors.not_found"))
        return
    
    chat_service = ChatService(db_session)
    
    chat = await chat_service.archive_chat(chat_id)
    
    if not chat:
        await callback.message.edit_text(_("errors.not_found"))
        return
    
    await state.clear()
    
    text = f"✅ {_('chat.closed')}"
    
    from app.bot.keyboards.builders import build_start_over_keyboard
    keyboard = build_start_over_keyboard(_)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    
    logger.info(f"Chat {chat_id} closed by user {user.id}")
