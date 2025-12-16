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
    """Build keyboard with list of chats (supports both realty and auto)."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    
    builder = InlineKeyboardBuilder()
    
    for i, chat in enumerate(chats, 1):
        # Check if it's an auto chat (has auto_match_id) or realty chat (has match_id)
        is_auto = hasattr(chat, 'auto_match_id')
        emoji = "🚗" if is_auto else "🏠"
        chat_type = "auto" if is_auto else "realty"
        builder.button(
            text=f"{emoji} Чат #{i}",
            callback_data=ChatCallback(action="open", id=f"{chat.id}_{chat_type}"),
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
            text=_('chat.reveal'),
            callback_data=ChatCallback(action="reveal", id=chat_id),
        )
    
    builder.button(
        text=_('chat.close'),
        callback_data=ChatCallback(action="close", id=chat_id),
    )
    builder.button(
        text=_('buttons.back'),
        callback_data="chat:list",
    )
    
    builder.adjust(2, 1)
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
    Handle /my_chats command - show user's active chat sessions (both realty and auto).
    
    Requirements: 7.1
    """
    if not db_session or not user:
        await message.answer(_("chats.empty"))
        return
    
    chat_service = ChatService(db_session)
    chats = await chat_service.get_chats_for_user(user.id, status=ChatStatusEnum.ACTIVE)
    
    # Also get auto chats
    from sqlalchemy import select
    from app.models.auto import AutoChat
    
    auto_chats_result = await db_session.execute(
        select(AutoChat)
        .where(
            ((AutoChat.buyer_id == user.id) | (AutoChat.seller_id == user.id))
            & (AutoChat.status == "active")
        )
        .order_by(AutoChat.last_message_at.desc().nullslast())
    )
    auto_chats = auto_chats_result.scalars().all()
    
    all_chats = list(chats) + list(auto_chats)
    
    if not all_chats:
        await message.answer(_("chats.empty"))
        return
    
    text = f"<b>Мои чаты</b>\n\n"
    text += "Выберите чат для общения:"
    
    keyboard = build_chat_list_keyboard(all_chats, _, user.id)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "chat:list")
async def cb_chat_list(
    callback: CallbackQuery,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Handle back to chat list (includes both realty and auto chats)."""
    await callback.answer()
    
    if not db_session or not user:
        await callback.message.edit_text(_("chats.empty"))
        return
    
    chat_service = ChatService(db_session)
    chats = await chat_service.get_chats_for_user(user.id, status=ChatStatusEnum.ACTIVE)
    
    # Also get auto chats
    from sqlalchemy import select
    from app.models.auto import AutoChat
    
    auto_chats_result = await db_session.execute(
        select(AutoChat)
        .where(
            ((AutoChat.buyer_id == user.id) | (AutoChat.seller_id == user.id))
            & (AutoChat.status == "active")
        )
        .order_by(AutoChat.last_message_at.desc().nullslast())
    )
    auto_chats = auto_chats_result.scalars().all()
    
    all_chats = list(chats) + list(auto_chats)
    
    if not all_chats:
        await callback.message.edit_text(_("chats.empty"))
        return
    
    text = f"<b>Мои чаты</b>\n\n"
    text += "Выберите чат для общения:"
    
    keyboard = build_chat_list_keyboard(all_chats, _, user.id)
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
    Open a chat session for messaging (supports both realty and auto).
    
    Requirements: 7.3
    """
    await callback.answer()
    
    if not db_session or not user:
        await callback.message.edit_text(_("errors.general"))
        return
    
    # Parse chat_id and type from callback data (using _ as separator)
    parts = callback_data.id.split("_")
    chat_id_str = "_".join(parts[:-1]) if len(parts) > 1 and parts[-1] in ("realty", "auto") else callback_data.id
    chat_type = parts[-1] if len(parts) > 1 and parts[-1] in ("realty", "auto") else "realty"
    
    try:
        chat_id = uuid.UUID(chat_id_str)
    except ValueError:
        await callback.message.edit_text(_("errors.not_found"))
        return
    
    if chat_type == "auto":
        # Handle auto chat
        from sqlalchemy import select
        from app.models.auto import AutoChat
        
        result = await db_session.execute(
            select(AutoChat).where(AutoChat.id == chat_id)
        )
        chat = result.scalar_one_or_none()
        
        if not chat:
            await callback.message.edit_text(_("errors.not_found"))
            return
        
        # Check if user is participant
        if user.id not in (chat.buyer_id, chat.seller_id):
            await callback.message.edit_text(_("errors.not_found"))
            return
        
        if user.id == chat.buyer_id:
            user_alias = chat.buyer_alias
            other_alias = chat.seller_alias
        else:
            user_alias = chat.seller_alias
            other_alias = chat.buyer_alias
        
        text = f"<b>🚗 Чат</b>\n\n"
        text += f"Вы: {user_alias}\n"
        text += f"Собеседник: {other_alias}\n\n"
        
        if chat.both_revealed:
            # Get real contacts for auto chat
            from app.repositories.user import UserRepository
            user_repo = UserRepository(db_session)
            
            buyer_user = await user_repo.get(chat.buyer_id)
            seller_user = await user_repo.get(chat.seller_id)
            
            buyer_contact = f"@{buyer_user.telegram_username}" if buyer_user and buyer_user.telegram_username else f"ID: {buyer_user.telegram_id}" if buyer_user else "-"
            seller_contact = f"@{seller_user.telegram_username}" if seller_user and seller_user.telegram_username else f"ID: {seller_user.telegram_id}" if seller_user else "-"
            
            text += "✅ <b>Контакты раскрыты!</b>\n\n"
            text += f"👤 Покупатель: {buyer_contact}\n"
            text += f"🚗 Продавец: {seller_contact}\n\n"
        
        text += "Напишите сообщение для отправки"
        
        await state.set_state(ChatStates.chatting)
        await state.update_data(active_chat_id=str(chat_id), chat_type="auto")
        
        can_reveal = not (
            (user.id == chat.buyer_id and chat.buyer_revealed) or
            (user.id == chat.seller_id and chat.seller_revealed)
        )
        
        keyboard = build_chat_actions_keyboard(
            f"{chat_id}_auto", _, 
            can_reveal=can_reveal,
            both_revealed=chat.both_revealed
        )
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        # Handle realty chat
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
            is_buyer = True
        else:
            user_alias = chat.seller_alias
            other_alias = chat.buyer_alias
            is_buyer = False
        
        text = f"<b>🏠 Чат</b>\n\n"
        text += f"Вы: {user_alias}\n"
        text += f"Собеседник: {other_alias}\n\n"
        
        if chat.both_revealed:
            # Get real contacts
            from app.repositories.user import UserRepository
            user_repo = UserRepository(db_session)
            
            buyer_user = await user_repo.get(requirement.user_id)
            seller_user = await user_repo.get(listing.user_id)
            
            buyer_contact = f"@{buyer_user.telegram_username}" if buyer_user and buyer_user.telegram_username else f"ID: {buyer_user.telegram_id}" if buyer_user else "-"
            seller_contact = f"@{seller_user.telegram_username}" if seller_user and seller_user.telegram_username else f"ID: {seller_user.telegram_id}" if seller_user else "-"
            
            text += "✅ <b>Контакты раскрыты!</b>\n\n"
            text += f"👤 Покупатель: {buyer_contact}\n"
            text += f"🏠 Продавец: {seller_contact}\n\n"
        
        text += "Напишите сообщение для отправки"
        
        await state.set_state(ChatStates.chatting)
        await state.update_data(active_chat_id=str(chat_id), chat_type="realty")
        
        can_reveal = not (
            (user.id == requirement.user_id and chat.buyer_revealed) or
            (user.id == listing.user_id and chat.seller_revealed)
        )
        
        keyboard = build_chat_actions_keyboard(
            f"{chat_id}_realty", _, 
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
    
    Routes messages between buyer and seller - sends directly to recipient.
    Supports both realty and auto chats.
    """
    if not db_session or not user:
        await message.answer(_("errors.general"))
        return
    
    data = await state.get_data()
    chat_id_str = data.get("active_chat_id")
    chat_type = data.get("chat_type", "realty")
    
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
    
    from app.models.chat import MessageTypeEnum
    
    content = None
    message_type_str = "text"
    media_url = None
    
    if message.text:
        content = message.text[:4000]
        message_type_str = "text"
    elif message.photo:
        media_url = message.photo[-1].file_id
        message_type_str = "photo"
        content = message.caption[:4000] if message.caption else None
    elif message.location:
        content = f"{message.location.latitude},{message.location.longitude}"
        message_type_str = "location"
    else:
        await message.answer(_("errors.invalid_input"))
        return
    
    from app.repositories.user import UserRepository
    user_repo = UserRepository(db_session)
    
    if chat_type == "auto":
        # Handle auto chat message
        from sqlalchemy import select
        from app.models.auto import AutoChat, AutoChatMessage
        from datetime import datetime, timezone
        
        result = await db_session.execute(
            select(AutoChat).where(AutoChat.id == chat_id)
        )
        chat = result.scalar_one_or_none()
        
        if not chat or chat.status != "active":
            await message.answer(_("errors.general"))
            return
        
        # Determine sender alias and recipient
        if user.id == chat.buyer_id:
            sender_alias = chat.buyer_alias
            recipient_user_id = chat.seller_id
        elif user.id == chat.seller_id:
            sender_alias = chat.seller_alias
            recipient_user_id = chat.buyer_id
        else:
            await message.answer(_("errors.general"))
            return
        
        # Save message
        chat_message = AutoChatMessage(
            auto_chat_id=chat_id,
            sender_id=user.id,
            message_type=message_type_str,
            content=content,
            media_url=media_url,
        )
        db_session.add(chat_message)
        chat.last_message_at = datetime.now(timezone.utc)
        await db_session.commit()
        
        # Send to recipient
        recipient = await user_repo.get(recipient_user_id)
        if recipient and recipient.telegram_id:
            try:
                msg_text = f"🚗 {sender_alias}:\n{content}" if content else f"🚗 {sender_alias}: [медиа]"
                
                if message_type_str == "text":
                    await message.bot.send_message(
                        chat_id=recipient.telegram_id,
                        text=msg_text,
                    )
                elif message_type_str == "photo" and media_url:
                    await message.bot.send_photo(
                        chat_id=recipient.telegram_id,
                        photo=media_url,
                        caption=f"🚗 {sender_alias}:\n{content}" if content else f"🚗 {sender_alias}",
                    )
            except Exception as e:
                logger.error(f"Failed to send message to recipient: {e}")
    else:
        # Handle realty chat message
        chat_service = ChatService(db_session)
        
        result = await chat_service.send_message(
            chat_id=chat_id,
            sender_id=user.id,
            content=content,
            message_type=MessageTypeEnum(message_type_str) if message_type_str in ["text", "photo", "location"] else MessageTypeEnum.TEXT,
            media_url=media_url,
        )
        
        if not result:
            await message.answer(_("errors.general"))
            return
        
        # Send message to recipient directly
        recipient = await user_repo.get(result.recipient_user_id)
        
        if recipient and recipient.telegram_id:
            try:
                msg_text = f"🏠 {result.sender_alias}:\n{content}" if content else f"🏠 {result.sender_alias}: [медиа]"
                
                if message_type_str == "text":
                    await message.bot.send_message(
                        chat_id=recipient.telegram_id,
                        text=msg_text,
                    )
                elif message_type_str == "photo" and media_url:
                    await message.bot.send_photo(
                        chat_id=recipient.telegram_id,
                        photo=media_url,
                        caption=f"🏠 {result.sender_alias}:\n{content}" if content else result.sender_alias,
                    )
            except Exception as e:
                logger.error(f"Failed to send message to recipient: {e}")
    
    # Confirm to sender
    await message.answer("✓ Отправлено")
    
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
    """Handle close chat - archive and exit (supports both realty and auto)."""
    await callback.answer()
    
    if not db_session or not user:
        await callback.message.edit_text(_("errors.general"))
        return
    
    # Parse chat_id and type (using _ as separator)
    parts = callback_data.id.split("_")
    chat_id_str = "_".join(parts[:-1]) if len(parts) > 1 and parts[-1] in ("realty", "auto") else callback_data.id
    chat_type = parts[-1] if len(parts) > 1 and parts[-1] in ("realty", "auto") else "realty"
    
    try:
        chat_id = uuid.UUID(chat_id_str)
    except ValueError:
        await callback.message.edit_text(_("errors.not_found"))
        return
    
    if chat_type == "auto":
        # Handle auto chat
        from sqlalchemy import select
        from app.models.auto import AutoChat
        
        result = await db_session.execute(
            select(AutoChat).where(AutoChat.id == chat_id)
        )
        chat = result.scalar_one_or_none()
        
        if not chat:
            await callback.message.edit_text(_("errors.not_found"))
            return
        
        chat.status = "archived"
        await db_session.commit()
    else:
        # Handle realty chat
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
