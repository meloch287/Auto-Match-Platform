from typing import Any, Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.bot.keyboards.builders import (
    build_language_keyboard,
    build_help_keyboard,
    build_settings_keyboard,
    build_cancel_operation_keyboard,
)
from app.bot.keyboards.callbacks import ListingCallback, RequirementCallback
from app.bot.states import OnboardingStates, ListingEditStates, RequirementEditStates
from app.models.requirement import Requirement
from app.models.listing import Listing

router = Router(name="common")

@router.message(Command("help"))
async def cmd_help(
    message: Message,
    _: Any,
) -> None:
    """Handle /help command."""
    help_text = _(
        "help.simple"
    )
    await message.answer(help_text, reply_markup=build_help_keyboard(_))

@router.message(Command("cancel"))
async def cmd_cancel(
    message: Message,
    state: FSMContext,
    _: Any,
) -> None:
    """Handle /cancel command - cancels current operation."""
    await state.clear()
    await message.answer(
        _("buttons.cancelled"),
        reply_markup=build_cancel_operation_keyboard(_),
    )

@router.message(Command("settings"))
async def cmd_settings(
    message: Message,
    _: Any,
    lang: str,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Handle /settings command - show settings with subscription status."""
    from app.services.user import UserService
    from app.models.user import SubscriptionTypeEnum
    
    lang_names = {
        "az": "Azərbaycan",
        "ru": "Русский",
        "en": "English",
    }
    lang_display = lang_names.get(lang, lang)
    
    # Build settings text with subscription info
    text = f" <b>{_('settings.title')}</b>\n\n"
    text += f" {_('settings.current_language')}: {lang_display}\n\n"
    
    if user and db_session:
        user_service = UserService(db_session)
        limits_info = await user_service.get_free_limits_info(user)
        
        # Subscription status
        is_premium = user.subscription_type != SubscriptionTypeEnum.FREE
        if is_premium:
            expires_str = user.subscription_expires_at.strftime("%Y-%m-%d") if user.subscription_expires_at else "-"
            text += f"⭐ {_('subscription.status')}: <b>{_('subscription.premium')}</b>\n"
            text += f"📅 {_('subscription.expires')}: {expires_str}\n\n"
        else:
            text += f"📋 {_('subscription.status')}: {_('subscription.free')}\n\n"
            
            # Show limits for free users
            text += f"📊 <b>{_('limits.title')}</b>\n"
            
            # Listings (seller)
            listings_used = limits_info["listings"]["used"]
            listings_max = limits_info["listings"]["max"]
            listings_remaining = limits_info["listings"]["remaining"]
            if listings_max == -1:
                text += f"🏷️ {_('limits.listings_label')}: {listings_used}/∞\n"
            else:
                text += f"🏷️ {_('limits.listings_label')}: {listings_used}/{listings_max} "
                text += f"({_('limits.remaining')}: {listings_remaining})\n"
            
            # Requirements (buyer)
            req_used = limits_info["requirements"]["used"]
            req_max = limits_info["requirements"]["max"]
            req_remaining = limits_info["requirements"]["remaining"]
            if req_max == -1:
                text += f"🔍 {_('limits.requirements_label')}: {req_used}/∞\n"
            else:
                text += f"🔍 {_('limits.requirements_label')}: {req_used}/{req_max} "
                text += f"({_('limits.remaining')}: {req_remaining})\n"
    
    is_premium = user and user.subscription_type != SubscriptionTypeEnum.FREE
    await message.answer(
        text,
        reply_markup=build_settings_keyboard(_, is_premium=is_premium),
        parse_mode="HTML",
    )

@router.callback_query(F.data == "menu:start_over")
async def cb_start_over(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Restart the flow from language selection."""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        _("welcome.new_user"),
        reply_markup=build_language_keyboard(),
    )
    await state.set_state(OnboardingStates.language_select)

@router.callback_query(F.data == "menu:change_language")
async def cb_change_language(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Handle change language button."""
    await callback.answer()
    await callback.message.edit_text(
        _("welcome.new_user"),
        reply_markup=build_language_keyboard(),
    )
    await state.set_state(OnboardingStates.language_select)

@router.callback_query(F.data == "menu:back_from_profile")
async def cb_back_from_profile(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Handle back button from profile - just delete the message."""
    await callback.answer()
    await state.clear()
    await callback.message.delete()

@router.message(Command("my_requests"))
async def cmd_my_requests(
    message: Message,
    _: Any,
    user: Any,
    lang: str,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Handle /my_requests command - show user's requirement requests from database."""
    if not db_session or not user:
        await message.answer(_("requirements.empty"))
        return
    
    result = await db_session.execute(
        select(Requirement)
        .where(Requirement.user_id == user.id)
        .options(selectinload(Requirement.category))
        .order_by(Requirement.created_at.desc())
        .limit(10)
    )
    requirements = result.scalars().all()
    
    if not requirements:
        await message.answer(_("requirements.empty"))
        return
    
    text = f"<b>{_('requirements.my_requirements')}</b>\n\n"
    
    buttons = []
    for i, req in enumerate(requirements, 1):
        if req.category:
            if lang == "ru":
                category_name = req.category.name_ru
            elif lang == "en":
                category_name = req.category.name_en
            else:
                category_name = req.category.name_az
        else:
            category_name = "-"
        
        price_min = float(req.price_min) if req.price_min else 0
        price_max = float(req.price_max) if req.price_max else 0
        
        status_emoji = "✅" if req.status == "active" else "⏸"
        
        text += f"{status_emoji} <b>#{i}</b> {category_name}\n"
        text += f"   {price_min:,.0f} - {price_max:,.0f} AZN\n\n"
        
        buttons.append([
            InlineKeyboardButton(
                text=f"✏️ {_('buttons.edit')} #{i}",
                callback_data=RequirementCallback(action="edit", id=str(req.id)).pack()
            )
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

@router.message(Command("my_listings"))
async def cmd_my_listings(
    message: Message,
    _: Any,
    user: Any,
    lang: str,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Handle /my_listings command - show user's listings from database."""
    if not db_session or not user:
        await message.answer(_("listings.empty"))
        return
    
    result = await db_session.execute(
        select(Listing)
        .where(Listing.user_id == user.id)
        .options(selectinload(Listing.category))
        .order_by(Listing.created_at.desc())
        .limit(10)
    )
    listings = result.scalars().all()
    
    if not listings:
        await message.answer(_("listings.empty"))
        return
    
    text = f"<b>{_('listings.my_listings')}</b>\n\n"
    
    buttons = []
    for i, lst in enumerate(listings, 1):
        if lst.category:
            if lang == "ru":
                category_name = lst.category.name_ru
            elif lang == "en":
                category_name = lst.category.name_en
            else:
                category_name = lst.category.name_az
        else:
            category_name = "-"
        
        price = float(lst.price) if lst.price else 0
        
        status_emoji = "✅" if lst.status == "active" else "⏳" if lst.status == "pending_moderation" else "⏸"
        
        text += f"{status_emoji} <b>#{i}</b> {category_name}\n"
        text += f"   {price:,.0f} AZN"
        if lst.rooms:
            text += f" | {lst.rooms} комн."
        if lst.area:
            text += f" | {float(lst.area)} м²"
        text += "\n\n"
        
        buttons.append([
            InlineKeyboardButton(
                text=f"✏️ {_('buttons.edit')} #{i}",
                callback_data=ListingCallback(action="edit", id=str(lst.id)).pack()
            )
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

@router.message(F.text.startswith("/"))
async def unknown_command(
    message: Message,
    _: Any,
) -> None:
    """Handle unknown commands."""
    await message.answer(_("errors.unknown_command"))


# ============ LISTING EDIT HANDLERS ============

@router.callback_query(ListingCallback.filter(F.action == "edit"))
async def edit_listing_start(
    callback: CallbackQuery,
    callback_data: ListingCallback,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Start editing a listing - show field selection."""
    await callback.answer()
    
    listing_id = callback_data.id
    await state.update_data(editing_listing_id=listing_id)
    
    # Get current listing values
    current_info = ""
    if db_session:
        result = await db_session.execute(select(Listing).where(Listing.id == listing_id))
        listing = result.scalar_one_or_none()
        if listing:
            current_info = f"\n\n📋 {_('edit.current_values')}:\n"
            current_info += f"💰 {_('edit.price')}: {float(listing.price):,.0f} AZN\n"
            current_info += f"🏠 {_('edit.rooms')}: {listing.rooms or '-'}\n"
            current_info += f"📐 {_('edit.area')}: {float(listing.area) if listing.area else '-'} м²\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💰 {_('edit.price')}", callback_data=f"edit_listing_field:price")],
        [InlineKeyboardButton(text=f"🏠 {_('edit.rooms')}", callback_data=f"edit_listing_field:rooms")],
        [InlineKeyboardButton(text=f"📐 {_('edit.area')}", callback_data=f"edit_listing_field:area")],
        [InlineKeyboardButton(text=f"📝 {_('edit.description')}", callback_data=f"edit_listing_field:description")],
        [InlineKeyboardButton(text=f"❌ {_('buttons.cancel')}", callback_data="edit_listing_cancel")],
    ])
    
    await callback.message.edit_text(_("edit.select_field") + current_info, reply_markup=keyboard)
    await state.set_state(ListingEditStates.select_field)


@router.callback_query(F.data.startswith("edit_listing_field:"), ListingEditStates.select_field)
async def edit_listing_field(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Handle field selection for listing edit."""
    await callback.answer()
    
    field = callback.data.split(":")[1]
    await state.update_data(editing_field=field)
    
    # Get current value
    data = await state.get_data()
    listing_id = data.get("editing_listing_id")
    current_value = ""
    
    if db_session and listing_id:
        result = await db_session.execute(select(Listing).where(Listing.id == listing_id))
        listing = result.scalar_one_or_none()
        if listing:
            if field == "price":
                current_value = f"\n\n{_('edit.current')}: {float(listing.price):,.0f} AZN"
            elif field == "rooms":
                current_value = f"\n\n{_('edit.current')}: {listing.rooms or '-'}"
            elif field == "area":
                current_value = f"\n\n{_('edit.current')}: {float(listing.area) if listing.area else '-'} м²"
            elif field == "description":
                desc = listing.description[:100] + "..." if listing.description and len(listing.description) > 100 else (listing.description or "-")
                current_value = f"\n\n{_('edit.current')}: {desc}"
    
    prompts = {
        "price": _("edit.enter_price"),
        "rooms": _("edit.enter_rooms"),
        "area": _("edit.enter_area"),
        "description": _("edit.enter_description"),
    }
    
    states = {
        "price": ListingEditStates.edit_price,
        "rooms": ListingEditStates.edit_rooms,
        "area": ListingEditStates.edit_area,
        "description": ListingEditStates.edit_description,
    }
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⬅️ {_('buttons.back_simple')}", callback_data=f"edit_listing_back")]
    ])
    
    await callback.message.edit_text(prompts.get(field, _("edit.enter_value")) + current_value, reply_markup=keyboard)
    await state.set_state(states.get(field, ListingEditStates.select_field))


@router.message(ListingEditStates.edit_price)
async def save_listing_price(
    message: Message,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Save new price for listing."""
    try:
        price = float(message.text.replace(",", ".").replace(" ", ""))
        if price <= 0:
            raise ValueError()
        
        data = await state.get_data()
        listing_id = data.get("editing_listing_id")
        
        if db_session and listing_id:
            from decimal import Decimal
            result = await db_session.execute(select(Listing).where(Listing.id == listing_id))
            listing = result.scalar_one_or_none()
            if listing:
                listing.price = Decimal(str(price))
                await db_session.commit()
                await message.answer(_("edit.saved"))
            else:
                await message.answer(_("errors.not_found"))
        
        await state.clear()
    except ValueError:
        await message.answer(_("form.price.invalid"))


@router.message(ListingEditStates.edit_rooms)
async def save_listing_rooms(
    message: Message,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Save new rooms count for listing."""
    try:
        rooms = int(message.text)
        if not 1 <= rooms <= 50:
            raise ValueError()
        
        data = await state.get_data()
        listing_id = data.get("editing_listing_id")
        
        if db_session and listing_id:
            result = await db_session.execute(select(Listing).where(Listing.id == listing_id))
            listing = result.scalar_one_or_none()
            if listing:
                listing.rooms = rooms
                await db_session.commit()
                await message.answer(_("edit.saved"))
            else:
                await message.answer(_("errors.not_found"))
        
        await state.clear()
    except ValueError:
        await message.answer(_("form.rooms.invalid"))


@router.message(ListingEditStates.edit_area)
async def save_listing_area(
    message: Message,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Save new area for listing."""
    try:
        area = float(message.text.replace(",", ".").replace(" ", ""))
        if area <= 0:
            raise ValueError()
        
        data = await state.get_data()
        listing_id = data.get("editing_listing_id")
        
        if db_session and listing_id:
            from decimal import Decimal
            result = await db_session.execute(select(Listing).where(Listing.id == listing_id))
            listing = result.scalar_one_or_none()
            if listing:
                listing.area = Decimal(str(area))
                await db_session.commit()
                await message.answer(_("edit.saved"))
            else:
                await message.answer(_("errors.not_found"))
        
        await state.clear()
    except ValueError:
        await message.answer(_("form.area.invalid"))


@router.message(ListingEditStates.edit_description)
async def save_listing_description(
    message: Message,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Save new description for listing."""
    data = await state.get_data()
    listing_id = data.get("editing_listing_id")
    
    if db_session and listing_id:
        result = await db_session.execute(select(Listing).where(Listing.id == listing_id))
        listing = result.scalar_one_or_none()
        if listing:
            listing.description = message.text[:1000]
            await db_session.commit()
            await message.answer(_("edit.saved"))
        else:
            await message.answer(_("errors.not_found"))
    
    await state.clear()


@router.callback_query(F.data == "edit_listing_cancel")
async def cancel_listing_edit(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Cancel listing edit."""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(_("buttons.cancelled"))


@router.callback_query(F.data == "edit_listing_back")
async def back_to_listing_field_select(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Go back to field selection for listing edit."""
    await callback.answer()
    
    data = await state.get_data()
    listing_id = data.get("editing_listing_id")
    
    # Get current listing values
    current_info = ""
    if db_session and listing_id:
        result = await db_session.execute(select(Listing).where(Listing.id == listing_id))
        listing = result.scalar_one_or_none()
        if listing:
            current_info = f"\n\n📋 {_('edit.current_values')}:\n"
            current_info += f"💰 {_('edit.price')}: {float(listing.price):,.0f} AZN\n"
            current_info += f"🏠 {_('edit.rooms')}: {listing.rooms or '-'}\n"
            current_info += f"📐 {_('edit.area')}: {float(listing.area) if listing.area else '-'} м²\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💰 {_('edit.price')}", callback_data=f"edit_listing_field:price")],
        [InlineKeyboardButton(text=f"🏠 {_('edit.rooms')}", callback_data=f"edit_listing_field:rooms")],
        [InlineKeyboardButton(text=f"📐 {_('edit.area')}", callback_data=f"edit_listing_field:area")],
        [InlineKeyboardButton(text=f"📝 {_('edit.description')}", callback_data=f"edit_listing_field:description")],
        [InlineKeyboardButton(text=f"❌ {_('buttons.cancel')}", callback_data="edit_listing_cancel")],
    ])
    
    await callback.message.edit_text(_("edit.select_field") + current_info, reply_markup=keyboard)
    await state.set_state(ListingEditStates.select_field)


# ============ REQUIREMENT EDIT HANDLERS ============

@router.callback_query(RequirementCallback.filter(F.action == "edit"))
async def edit_requirement_start(
    callback: CallbackQuery,
    callback_data: RequirementCallback,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Start editing a requirement - show field selection."""
    await callback.answer()
    
    requirement_id = callback_data.id
    await state.update_data(editing_requirement_id=requirement_id)
    
    # Get current requirement values
    current_info = ""
    if db_session:
        result = await db_session.execute(select(Requirement).where(Requirement.id == requirement_id))
        req = result.scalar_one_or_none()
        if req:
            current_info = f"\n\n� {_('edit.current_values')}:\n"
            price_min = float(req.price_min) if req.price_min else 0
            price_max = float(req.price_max) if req.price_max else 0
            current_info += f"💰 {_('edit.price')}: {price_min:,.0f} - {price_max:,.0f} AZN\n"
            current_info += f"🏠 {_('edit.rooms')}: {req.rooms_min or '-'} - {req.rooms_max or '-'}\n"
            area_min = float(req.area_min) if req.area_min else 0
            area_max = float(req.area_max) if req.area_max else 0
            current_info += f"📐 {_('edit.area')}: {area_min} - {area_max} м²\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💰 {_('edit.price')}", callback_data=f"edit_req_field:price")],
        [InlineKeyboardButton(text=f"🏠 {_('edit.rooms')}", callback_data=f"edit_req_field:rooms")],
        [InlineKeyboardButton(text=f"📐 {_('edit.area')}", callback_data=f"edit_req_field:area")],
        [InlineKeyboardButton(text=f"❌ {_('buttons.cancel')}", callback_data="edit_req_cancel")],
    ])
    
    await callback.message.edit_text(_("edit.select_field") + current_info, reply_markup=keyboard)
    await state.set_state(RequirementEditStates.select_field)


@router.callback_query(F.data.startswith("edit_req_field:"), RequirementEditStates.select_field)
async def edit_requirement_field(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Handle field selection for requirement edit - now with combined range input."""
    await callback.answer()
    
    field = callback.data.split(":")[1]
    await state.update_data(editing_field=field)
    
    # Get current value
    data = await state.get_data()
    requirement_id = data.get("editing_requirement_id")
    current_value = ""
    
    if db_session and requirement_id:
        result = await db_session.execute(select(Requirement).where(Requirement.id == requirement_id))
        req = result.scalar_one_or_none()
        if req:
            if field == "price":
                price_min = float(req.price_min) if req.price_min else 0
                price_max = float(req.price_max) if req.price_max else 0
                current_value = f"\n\n{_('edit.current')}: {price_min:,.0f} - {price_max:,.0f} AZN"
            elif field == "rooms":
                current_value = f"\n\n{_('edit.current')}: {req.rooms_min or 0} - {req.rooms_max or 0}"
            elif field == "area":
                area_min = float(req.area_min) if req.area_min else 0
                area_max = float(req.area_max) if req.area_max else 0
                current_value = f"\n\n{_('edit.current')}: {area_min} - {area_max} м²"
    
    prompts = {
        "price": _("edit.enter_price_range"),
        "rooms": _("edit.enter_rooms_range"),
        "area": _("edit.enter_area_range"),
    }
    
    states = {
        "price": RequirementEditStates.edit_price,
        "rooms": RequirementEditStates.edit_rooms,
        "area": RequirementEditStates.edit_area,
    }
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⬅️ {_('buttons.back_simple')}", callback_data=f"edit_req_back")]
    ])
    
    await callback.message.edit_text(prompts.get(field, _("edit.enter_value")) + current_value, reply_markup=keyboard)
    await state.set_state(states.get(field, RequirementEditStates.select_field))


# New combined range handlers
@router.message(RequirementEditStates.edit_price)
async def save_requirement_price_range(message: Message, state: FSMContext, _: Any, db_session: Optional[AsyncSession] = None) -> None:
    """Save price range (min-max) for requirement."""
    await _save_requirement_range_field(message, state, _, db_session, "price", is_decimal=True)


@router.message(RequirementEditStates.edit_rooms)
async def save_requirement_rooms_range(message: Message, state: FSMContext, _: Any, db_session: Optional[AsyncSession] = None) -> None:
    """Save rooms range (min-max) for requirement."""
    await _save_requirement_range_field(message, state, _, db_session, "rooms", is_decimal=False)


@router.message(RequirementEditStates.edit_area)
async def save_requirement_area_range(message: Message, state: FSMContext, _: Any, db_session: Optional[AsyncSession] = None) -> None:
    """Save area range (min-max) for requirement."""
    await _save_requirement_range_field(message, state, _, db_session, "area", is_decimal=True)


async def _save_requirement_range_field(message: Message, state: FSMContext, _: Any, db_session: Optional[AsyncSession], field: str, is_decimal: bool = True) -> None:
    """Helper to save range field (min-max) for requirement."""
    import re
    try:
        # Parse "min-max" or "min - max" format
        text = message.text.replace(",", ".").replace(" ", "")
        match = re.match(r"^(\d+\.?\d*)-(\d+\.?\d*)$", text)
        if not match:
            raise ValueError("Invalid format")
        
        if is_decimal:
            min_val = float(match.group(1))
            max_val = float(match.group(2))
        else:
            min_val = int(float(match.group(1)))
            max_val = int(float(match.group(2)))
        
        if min_val < 0 or max_val < 0 or min_val > max_val:
            raise ValueError("Invalid range")
        
        data = await state.get_data()
        requirement_id = data.get("editing_requirement_id")
        
        if db_session and requirement_id:
            from decimal import Decimal
            result = await db_session.execute(select(Requirement).where(Requirement.id == requirement_id))
            req = result.scalar_one_or_none()
            if req:
                if is_decimal:
                    setattr(req, f"{field}_min", Decimal(str(min_val)))
                    setattr(req, f"{field}_max", Decimal(str(max_val)))
                else:
                    setattr(req, f"{field}_min", min_val)
                    setattr(req, f"{field}_max", max_val)
                await db_session.commit()
                await message.answer(_("edit.saved"))
            else:
                await message.answer(_("errors.not_found"))
        
        await state.clear()
    except ValueError:
        await message.answer(_("edit.invalid_range"))


# Legacy single field handlers (kept for compatibility)
@router.message(RequirementEditStates.edit_price_min)
async def save_requirement_price_min(message: Message, state: FSMContext, _: Any, db_session: Optional[AsyncSession] = None) -> None:
    await _save_requirement_decimal_field(message, state, _, db_session, "price_min")


@router.message(RequirementEditStates.edit_price_max)
async def save_requirement_price_max(message: Message, state: FSMContext, _: Any, db_session: Optional[AsyncSession] = None) -> None:
    await _save_requirement_decimal_field(message, state, _, db_session, "price_max")


@router.message(RequirementEditStates.edit_rooms_min)
async def save_requirement_rooms_min(message: Message, state: FSMContext, _: Any, db_session: Optional[AsyncSession] = None) -> None:
    await _save_requirement_int_field(message, state, _, db_session, "rooms_min")


@router.message(RequirementEditStates.edit_rooms_max)
async def save_requirement_rooms_max(message: Message, state: FSMContext, _: Any, db_session: Optional[AsyncSession] = None) -> None:
    await _save_requirement_int_field(message, state, _, db_session, "rooms_max")


@router.message(RequirementEditStates.edit_area_min)
async def save_requirement_area_min(message: Message, state: FSMContext, _: Any, db_session: Optional[AsyncSession] = None) -> None:
    await _save_requirement_decimal_field(message, state, _, db_session, "area_min")


@router.message(RequirementEditStates.edit_area_max)
async def save_requirement_area_max(message: Message, state: FSMContext, _: Any, db_session: Optional[AsyncSession] = None) -> None:
    await _save_requirement_decimal_field(message, state, _, db_session, "area_max")


async def _save_requirement_decimal_field(message: Message, state: FSMContext, _: Any, db_session: Optional[AsyncSession], field: str) -> None:
    """Helper to save decimal field for requirement."""
    try:
        value = float(message.text.replace(",", ".").replace(" ", ""))
        if value < 0:
            raise ValueError()
        
        data = await state.get_data()
        requirement_id = data.get("editing_requirement_id")
        
        if db_session and requirement_id:
            from decimal import Decimal
            result = await db_session.execute(select(Requirement).where(Requirement.id == requirement_id))
            req = result.scalar_one_or_none()
            if req:
                setattr(req, field, Decimal(str(value)))
                await db_session.commit()
                await message.answer(_("edit.saved"))
            else:
                await message.answer(_("errors.not_found"))
        
        await state.clear()
    except ValueError:
        await message.answer(_("form.price.invalid"))


async def _save_requirement_int_field(message: Message, state: FSMContext, _: Any, db_session: Optional[AsyncSession], field: str) -> None:
    """Helper to save int field for requirement."""
    try:
        value = int(message.text)
        if value < 0:
            raise ValueError()
        
        data = await state.get_data()
        requirement_id = data.get("editing_requirement_id")
        
        if db_session and requirement_id:
            result = await db_session.execute(select(Requirement).where(Requirement.id == requirement_id))
            req = result.scalar_one_or_none()
            if req:
                setattr(req, field, value)
                await db_session.commit()
                await message.answer(_("edit.saved"))
            else:
                await message.answer(_("errors.not_found"))
        
        await state.clear()
    except ValueError:
        await message.answer(_("form.rooms.invalid"))


@router.callback_query(F.data == "edit_req_cancel")
async def cancel_requirement_edit(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Cancel requirement edit."""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(_("buttons.cancelled"))


@router.callback_query(F.data == "edit_req_back")
async def back_to_requirement_field_select(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Go back to field selection for requirement edit."""
    await callback.answer()
    
    data = await state.get_data()
    requirement_id = data.get("editing_requirement_id")
    
    # Get current requirement values
    current_info = ""
    if db_session and requirement_id:
        result = await db_session.execute(select(Requirement).where(Requirement.id == requirement_id))
        req = result.scalar_one_or_none()
        if req:
            current_info = f"\n\n📋 {_('edit.current_values')}:\n"
            price_min = float(req.price_min) if req.price_min else 0
            price_max = float(req.price_max) if req.price_max else 0
            current_info += f"💰 {_('edit.price')}: {price_min:,.0f} - {price_max:,.0f} AZN\n"
            current_info += f"🏠 {_('edit.rooms')}: {req.rooms_min or '-'} - {req.rooms_max or '-'}\n"
            area_min = float(req.area_min) if req.area_min else 0
            area_max = float(req.area_max) if req.area_max else 0
            current_info += f"📐 {_('edit.area')}: {area_min} - {area_max} м²\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💰 {_('edit.price')}", callback_data=f"edit_req_field:price")],
        [InlineKeyboardButton(text=f"🏠 {_('edit.rooms')}", callback_data=f"edit_req_field:rooms")],
        [InlineKeyboardButton(text=f"📐 {_('edit.area')}", callback_data=f"edit_req_field:area")],
        [InlineKeyboardButton(text=f"❌ {_('buttons.cancel')}", callback_data="edit_req_cancel")],
    ])
    
    await callback.message.edit_text(_("edit.select_field") + current_info, reply_markup=keyboard)
    await state.set_state(RequirementEditStates.select_field)


async def error_handler(
    event: Any,
    exception: Exception,
) -> bool:
    """Global error handler for the bot."""
    import logging
    
    logger = logging.getLogger(__name__)
    logger.exception(f"Error handling update: {exception}")
    
    try:
        if hasattr(event, "message") and event.message:
            await event.message.answer("⚠️ Произошла ошибка. Попробуйте /start")
        elif hasattr(event, "callback_query") and event.callback_query:
            await event.callback_query.answer("⚠️ Ошибка", show_alert=True)
    except Exception:
        pass
    
    return True
