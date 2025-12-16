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
from app.bot.keyboards.callbacks import ListingCallback, RequirementCallback, AutoRequirementCallback, AutoListingCallback
from app.bot.states import OnboardingStates, ListingEditStates, RequirementEditStates, AutoRequirementEditStates, AutoListingEditStates
from app.models.requirement import Requirement
from app.models.listing import Listing
from app.models.auto import AutoListing, AutoRequirement

router = Router(name="common")


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    """Handle noop callback - do nothing."""
    await callback.answer()


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


@router.callback_query(F.data == "show_recommended")
async def cb_show_recommended(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Show recommended listings when no matches found."""
    await callback.answer()
    
    if not db_session:
        await callback.message.edit_text(_("errors.general"))
        return
    
    from app.models.recommended import RecommendedListing
    from app.models.listing import Listing, ListingMedia, ListingStatusEnum
    import random
    
    # Get recommended listings
    result = await db_session.execute(
        select(RecommendedListing, Listing)
        .join(Listing, RecommendedListing.listing_id == Listing.id)
        .where(Listing.status == ListingStatusEnum.ACTIVE)
        .order_by(RecommendedListing.order)
    )
    rows = result.all()
    
    # If no configured recommended, get random active listings
    if not rows:
        result = await db_session.execute(
            select(Listing)
            .where(Listing.status == ListingStatusEnum.ACTIVE)
            .limit(10)
        )
        all_listings = result.scalars().all()
        if all_listings:
            random_listings = random.sample(all_listings, min(5, len(all_listings)))
            rows = [(None, listing) for listing in random_listings]
    
    if not rows:
        await callback.message.edit_text(
            _("recommended.empty"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=_("buttons.start_over"), callback_data="start_over")]
            ])
        )
        return
    
    # Store for pagination
    listing_ids = [str(listing.id) for _, listing in rows]
    await state.update_data(recommended_listings=listing_ids, recommended_index=0)
    
    # Show first listing
    await _show_recommended_listing(callback.message, state, _, db_session, edit=True)


async def _show_recommended_listing(
    message: Any,
    state: FSMContext,
    _: Any,
    db_session: AsyncSession,
    edit: bool = True,
) -> None:
    """Show a single recommended listing with pagination."""
    from app.models.listing import Listing, ListingMedia
    from aiogram.types import InputMediaPhoto
    
    data = await state.get_data()
    listing_ids = data.get("recommended_listings", [])
    index = data.get("recommended_index", 0)
    
    if not listing_ids:
        return
    
    index = max(0, min(index, len(listing_ids) - 1))
    total = len(listing_ids)
    
    # Get listing
    listing_id = listing_ids[index]
    result = await db_session.execute(
        select(Listing).where(Listing.id == listing_id)
    )
    listing = result.scalar_one_or_none()
    
    if not listing:
        return
    
    # Get photo
    photo_result = await db_session.execute(
        select(ListingMedia)
        .where(ListingMedia.listing_id == listing.id)
        .order_by(ListingMedia.order)
        .limit(1)
    )
    media = photo_result.scalar_one_or_none()
    photo_url = media.url if media else None
    
    # Build text
    text = f"<b>⭐ {_('recommended.title')} {index + 1}/{total}</b>\n\n"
    text += f"💰 {_('listing.price')}: {float(listing.price):,.0f} AZN\n"
    if listing.rooms:
        text += f"🏠 {_('listing.rooms')}: {listing.rooms}\n"
    if listing.area:
        text += f"📐 {_('listing.area')}: {float(listing.area)} м²\n"
    if listing.floor:
        text += f"🏢 {_('listing.floor')}: {listing.floor}"
        if listing.building_floors:
            text += f"/{listing.building_floors}"
        text += "\n"
    
    # Build keyboard
    buttons = []
    
    # Navigation row
    if total > 1:
        nav_row = []
        if index > 0:
            nav_row.append(InlineKeyboardButton(text="⬅️", callback_data="recommended:prev"))
        else:
            nav_row.append(InlineKeyboardButton(text=" ", callback_data="noop"))
        nav_row.append(InlineKeyboardButton(text=f"{index + 1}/{total}", callback_data="noop"))
        if index < total - 1:
            nav_row.append(InlineKeyboardButton(text="➡️", callback_data="recommended:next"))
        else:
            nav_row.append(InlineKeyboardButton(text=" ", callback_data="noop"))
        buttons.append(nav_row)
    
    buttons.append([InlineKeyboardButton(text=_("buttons.start_over"), callback_data="start_over")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    # Send/edit message
    try:
        if photo_url:
            if edit:
                try:
                    await message.edit_media(
                        media=InputMediaPhoto(media=photo_url, caption=text, parse_mode="HTML"),
                        reply_markup=keyboard,
                    )
                except Exception:
                    await message.delete()
                    await message.answer_photo(photo=photo_url, caption=text, reply_markup=keyboard, parse_mode="HTML")
            else:
                await message.answer_photo(photo=photo_url, caption=text, reply_markup=keyboard, parse_mode="HTML")
        else:
            if edit:
                await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            else:
                await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "recommended:prev")
async def cb_recommended_prev(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Go to previous recommended listing."""
    await callback.answer()
    data = await state.get_data()
    index = data.get("recommended_index", 0)
    new_index = max(0, index - 1)
    await state.update_data(recommended_index=new_index)
    if db_session:
        await _show_recommended_listing(callback.message, state, _, db_session, edit=True)


@router.callback_query(F.data == "recommended:next")
async def cb_recommended_next(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Go to next recommended listing."""
    await callback.answer()
    data = await state.get_data()
    index = data.get("recommended_index", 0)
    listings = data.get("recommended_listings", [])
    new_index = min(len(listings) - 1, index + 1)
    await state.update_data(recommended_index=new_index)
    if db_session:
        await _show_recommended_listing(callback.message, state, _, db_session, edit=True)


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
    
    # Get real estate requirements (exclude deleted)
    from app.models.requirement import RequirementStatusEnum
    result = await db_session.execute(
        select(Requirement)
        .where(
            Requirement.user_id == user.id,
            Requirement.status != RequirementStatusEnum.DELETED
        )
        .options(selectinload(Requirement.category))
        .order_by(Requirement.created_at.desc())
        .limit(10)
    )
    requirements = result.scalars().all()
    
    # Get auto requirements (exclude deleted)
    auto_result = await db_session.execute(
        select(AutoRequirement)
        .where(
            AutoRequirement.user_id == user.id,
            AutoRequirement.status != "deleted"
        )
        .order_by(AutoRequirement.created_at.desc())
        .limit(10)
    )
    auto_requirements = auto_result.scalars().all()
    
    if not requirements and not auto_requirements:
        await message.answer(_("requirements.empty"))
        return
    
    text = f"<b>{_('requirements.my_requirements')}</b>\n\n"
    buttons = []
    counter = 1
    
    # Real estate requirements
    if requirements:
        text += f"🏠 <b>{_('market.real_estate')}</b>\n\n"
        for req in requirements:
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
            
            status_val = req.status.value if hasattr(req.status, 'value') else str(req.status)
            status_emoji = "✅" if status_val == "active" else "⏸"
            
            # Get deal type - for requirements (buyer), show "Покупка" not "Продажа"
            deal_type_val = req.deal_type.value if hasattr(req.deal_type, 'value') else str(req.deal_type) if req.deal_type else "sale"
            deal_type_label = _("deal_type.rent_buyer") if deal_type_val == "rent" else _("deal_type.sale_buyer")
            
            text += f"{status_emoji} <b>#{counter}</b> {category_name}\n"
            text += f"   {price_min:,.0f} - {price_max:,.0f} AZN | {deal_type_label}\n\n"
            
            buttons.append([
                InlineKeyboardButton(
                    text=f"✏️ {_('buttons.edit')} #{counter}",
                    callback_data=RequirementCallback(action="edit", id=str(req.id)).pack()
                )
            ])
            counter += 1
    
    # Auto requirements
    if auto_requirements:
        text += f"🚗 <b>{_('market.auto')}</b>\n\n"
        for req in auto_requirements:
            brands = ", ".join(req.brands[:3]) if req.brands else "-"
            if req.brands and len(req.brands) > 3:
                brands += "..."
            
            price_min = float(req.price_min) if req.price_min else 0
            price_max = float(req.price_max) if req.price_max else 0
            year_range = f"{req.year_min or '?'}-{req.year_max or '?'}"
            
            status_val = req.status.value if hasattr(req.status, 'value') else str(req.status)
            status_emoji = "✅" if status_val == "active" else "⏸"
            deal_type = _("deal_type.rent") if req.deal_type == "rent" else _("deal_type.sale")
            
            text += f"{status_emoji} <b>#{counter}</b> {brands}\n"
            text += f"   📅 {year_range} | 💰 {price_min:,.0f} - {price_max:,.0f} AZN\n"
            text += f"   {deal_type}\n\n"
            
            buttons.append([
                InlineKeyboardButton(
                    text=f"✏️ {_('buttons.edit')} #{counter} 🚗",
                    callback_data=AutoRequirementCallback(action="edit", id=str(req.id)).pack()
                )
            ])
            counter += 1
    
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
    
    # Get real estate listings (exclude deleted)
    from app.models.listing import ListingStatusEnum
    from app.models.auto import AutoStatusEnum
    result = await db_session.execute(
        select(Listing)
        .where(
            Listing.user_id == user.id,
            Listing.status != ListingStatusEnum.DELETED
        )
        .options(selectinload(Listing.category))
        .order_by(Listing.created_at.desc())
        .limit(10)
    )
    listings = result.scalars().all()
    
    # Get auto listings (exclude deleted)
    auto_result = await db_session.execute(
        select(AutoListing)
        .where(
            AutoListing.user_id == user.id,
            AutoListing.status != AutoStatusEnum.DELETED
        )
        .order_by(AutoListing.created_at.desc())
        .limit(10)
    )
    auto_listings = auto_result.scalars().all()
    
    if not listings and not auto_listings:
        await message.answer(_("listings.empty"))
        return
    
    text = f"<b>{_('listings.my_listings')}</b>\n\n"
    buttons = []
    counter = 1
    
    # Real estate listings
    if listings:
        text += f"🏠 <b>{_('market.real_estate')}</b>\n\n"
        for lst in listings:
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
            
            status_val = lst.status.value if hasattr(lst.status, 'value') else str(lst.status)
            status_emoji = "✅" if status_val == "active" else "⏳" if status_val == "pending_moderation" else "⏸"
            
            # Get deal type
            deal_type_val = lst.deal_type.value if hasattr(lst.deal_type, 'value') else str(lst.deal_type) if lst.deal_type else "sale"
            deal_type_label = _("deal_type.rent") if deal_type_val == "rent" else _("deal_type.sale")
            
            text += f"{status_emoji} <b>#{counter}</b> {category_name}\n"
            text += f"   {price:,.0f} AZN | {deal_type_label}"
            if lst.rooms:
                text += f" | {lst.rooms} комн."
            if lst.area:
                text += f" | {float(lst.area)} м²"
            text += "\n\n"
            
            buttons.append([
                InlineKeyboardButton(
                    text=f"✏️ {_('buttons.edit')} #{counter}",
                    callback_data=ListingCallback(action="edit", id=str(lst.id)).pack()
                )
            ])
            counter += 1
    
    # Auto listings
    if auto_listings:
        text += f"🚗 <b>{_('market.auto')}</b>\n\n"
        for lst in auto_listings:
            price = float(lst.price) if lst.price else 0
            
            status_val = lst.status.value if hasattr(lst.status, 'value') else str(lst.status)
            status_emoji = "✅" if status_val == "active" else "⏳" if status_val == "pending_moderation" else "⏸"
            deal_type = _("deal_type.rent") if lst.deal_type == "rent" else _("deal_type.sale")
            
            text += f"{status_emoji} <b>#{counter}</b> {lst.brand} {lst.model}\n"
            text += f"   📅 {lst.year} | 💰 {price:,.0f} AZN\n"
            text += f"   {deal_type}\n\n"
            
            buttons.append([
                InlineKeyboardButton(
                    text=f"✏️ {_('buttons.edit')} #{counter} 🚗",
                    callback_data=AutoListingCallback(action="edit", id=str(lst.id)).pack()
                )
            ])
            counter += 1
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

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
        [InlineKeyboardButton(text=f"🗑️ {_('buttons.delete')}", callback_data=f"delete_listing:{listing_id}")],
        [InlineKeyboardButton(text=f"❌ {_('buttons.cancel')}", callback_data="edit_listing_cancel")],
    ])
    
    await callback.message.edit_text(_("edit.select_field") + current_info, reply_markup=keyboard)
    await state.set_state(ListingEditStates.select_field)


@router.callback_query(F.data.startswith("delete_listing:"))
async def delete_listing_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Show delete confirmation for listing."""
    await callback.answer()
    listing_id = callback.data.split(":")[1]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"✅ {_('buttons.yes')}", callback_data=f"confirm_delete_listing:{listing_id}"),
            InlineKeyboardButton(text=f"❌ {_('buttons.no')}", callback_data=f"cancel_delete_listing:{listing_id}"),
        ]
    ])
    
    await callback.message.edit_text(
        _("delete.confirm_listing"),
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("confirm_delete_listing:"))
async def delete_listing_execute(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Execute listing deletion."""
    await callback.answer()
    listing_id = callback.data.split(":")[1]
    
    if db_session:
        from uuid import UUID
        from app.models.listing import ListingStatusEnum
        result = await db_session.execute(select(Listing).where(Listing.id == UUID(listing_id)))
        listing = result.scalar_one_or_none()
        if listing:
            listing.status = ListingStatusEnum.DELETED
            await db_session.commit()
    
    await state.clear()
    
    # Add "Done" button to return to my_listings
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ {_('buttons.done')}", callback_data="back_to_my_listings")]
    ])
    await callback.message.edit_text(_("listings.deleted"), reply_markup=keyboard)


@router.callback_query(F.data == "back_to_my_listings")
async def back_to_my_listings(
    callback: CallbackQuery,
    _: Any,
    user: Any,
    lang: str,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Return to my_listings list after deletion."""
    await callback.answer()
    await callback.message.delete()
    
    if db_session and user:
        from app.models.listing import ListingStatusEnum
        from app.models.auto import AutoStatusEnum
        result = await db_session.execute(
            select(Listing)
            .where(
                Listing.user_id == user.id,
                Listing.status != ListingStatusEnum.DELETED
            )
            .options(selectinload(Listing.category))
            .order_by(Listing.created_at.desc())
            .limit(10)
        )
        listings = result.scalars().all()
        
        auto_result = await db_session.execute(
            select(AutoListing)
            .where(
                AutoListing.user_id == user.id,
                AutoListing.status != AutoStatusEnum.DELETED
            )
            .order_by(AutoListing.created_at.desc())
            .limit(10)
        )
        auto_listings = auto_result.scalars().all()
        
        if not listings and not auto_listings:
            await callback.message.answer(_("listings.empty"))
            return
        
        text = f"<b>{_('listings.my_listings')}</b>\n\n"
        buttons = []
        counter = 1
        
        if listings:
            text += f"🏠 <b>{_('market.real_estate')}</b>\n\n"
            for lst in listings:
                category_name = "-"
                if lst.category:
                    if lang == "ru":
                        category_name = lst.category.name_ru
                    elif lang == "en":
                        category_name = lst.category.name_en
                    else:
                        category_name = lst.category.name_az
                
                price = float(lst.price) if lst.price else 0
                status_emoji = "✅" if str(lst.status.value) == "active" else "⏳" if str(lst.status.value) == "pending_moderation" else "⏸"
                deal_type_val = lst.deal_type.value if hasattr(lst.deal_type, 'value') else str(lst.deal_type) if lst.deal_type else "sale"
                deal_type_label = _("deal_type.rent") if deal_type_val == "rent" else _("deal_type.sale")
                
                text += f"{status_emoji} <b>#{counter}</b> {category_name}\n"
                text += f"   {price:,.0f} AZN | {deal_type_label}"
                if lst.rooms:
                    text += f" | {lst.rooms} комн."
                if lst.area:
                    text += f" | {float(lst.area)} м²"
                text += "\n\n"
                buttons.append([InlineKeyboardButton(text=f"✏️ {_('buttons.edit')} #{counter}", callback_data=ListingCallback(action="edit", id=str(lst.id)).pack())])
                counter += 1
        
        if auto_listings:
            text += f"🚗 <b>{_('market.auto')}</b>\n\n"
            for lst in auto_listings:
                price = float(lst.price) if lst.price else 0
                status_emoji = "✅" if str(lst.status.value) == "active" else "⏳" if str(lst.status.value) == "pending_moderation" else "⏸"
                deal_type = _("deal_type.rent") if lst.deal_type == "rent" else _("deal_type.sale")
                
                text += f"{status_emoji} <b>#{counter}</b> {lst.brand} {lst.model or ''}\n"
                text += f"   📅 {lst.year} | 💰 {price:,.0f} AZN | {deal_type}\n\n"
                buttons.append([InlineKeyboardButton(text=f"✏️ {_('buttons.edit')} #{counter} 🚗", callback_data=AutoListingCallback(action="edit", id=str(lst.id)).pack())])
                counter += 1
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await callback.message.answer(_("listings.empty"))


@router.callback_query(F.data.startswith("cancel_delete_listing:"))
async def delete_listing_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Cancel listing deletion - return to edit menu."""
    await callback.answer()
    listing_id = callback.data.split(":")[1]
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
        [InlineKeyboardButton(text=f"🗑️ {_('buttons.delete')}", callback_data=f"delete_listing:{listing_id}")],
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
        [InlineKeyboardButton(text=f"🗑️ {_('buttons.delete')}", callback_data=f"delete_requirement:{requirement_id}")],
        [InlineKeyboardButton(text=f"❌ {_('buttons.cancel')}", callback_data="edit_req_cancel")],
    ])
    
    await callback.message.edit_text(_("edit.select_field") + current_info, reply_markup=keyboard)
    await state.set_state(RequirementEditStates.select_field)


@router.callback_query(F.data.startswith("delete_requirement:"))
async def delete_requirement_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Show delete confirmation for requirement."""
    await callback.answer()
    requirement_id = callback.data.split(":")[1]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"✅ {_('buttons.yes')}", callback_data=f"confirm_delete_req:{requirement_id}"),
            InlineKeyboardButton(text=f"❌ {_('buttons.no')}", callback_data=f"cancel_delete_req:{requirement_id}"),
        ]
    ])
    
    await callback.message.edit_text(
        _("delete.confirm_requirement"),
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("confirm_delete_req:"))
async def delete_requirement_execute(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Execute requirement deletion."""
    await callback.answer()
    requirement_id = callback.data.split(":")[1]
    
    if db_session:
        from uuid import UUID
        from app.models.requirement import RequirementStatusEnum
        result = await db_session.execute(select(Requirement).where(Requirement.id == UUID(requirement_id)))
        req = result.scalar_one_or_none()
        if req:
            req.status = RequirementStatusEnum.DELETED
            await db_session.commit()
    
    await state.clear()
    
    # Add "Done" button to return to my_requests
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ {_('buttons.done')}", callback_data="back_to_my_requests")]
    ])
    await callback.message.edit_text(_("requirements.deleted"), reply_markup=keyboard)


@router.callback_query(F.data == "back_to_my_requests")
async def back_to_my_requests(
    callback: CallbackQuery,
    _: Any,
    user: Any,
    lang: str,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Return to my_requests list after deletion."""
    await callback.answer()
    await callback.message.delete()
    
    # Show my_requests list
    if db_session and user:
        from app.models.requirement import RequirementStatusEnum
        result = await db_session.execute(
            select(Requirement)
            .where(
                Requirement.user_id == user.id,
                Requirement.status != RequirementStatusEnum.DELETED
            )
            .options(selectinload(Requirement.category))
            .order_by(Requirement.created_at.desc())
            .limit(10)
        )
        requirements = result.scalars().all()
        
        auto_result = await db_session.execute(
            select(AutoRequirement)
            .where(
                AutoRequirement.user_id == user.id,
                AutoRequirement.status != "deleted"
            )
            .order_by(AutoRequirement.created_at.desc())
            .limit(10)
        )
        auto_requirements = auto_result.scalars().all()
        
        if not requirements and not auto_requirements:
            await callback.message.answer(_("requirements.empty"))
            return
        
        text = f"<b>{_('requirements.my_requirements')}</b>\n\n"
        buttons = []
        counter = 1
        
        if requirements:
            text += f"🏠 <b>{_('market.real_estate')}</b>\n\n"
            for req in requirements:
                category_name = "-"
                if req.category:
                    if lang == "ru":
                        category_name = req.category.name_ru
                    elif lang == "en":
                        category_name = req.category.name_en
                    else:
                        category_name = req.category.name_az
                
                price_min = float(req.price_min) if req.price_min else 0
                price_max = float(req.price_max) if req.price_max else 0
                status_emoji = "✅" if str(req.status.value) == "active" else "⏸"
                deal_type_val = req.deal_type.value if hasattr(req.deal_type, 'value') else str(req.deal_type) if req.deal_type else "sale"
                deal_type_label = _("deal_type.rent_buyer") if deal_type_val == "rent" else _("deal_type.sale_buyer")
                
                text += f"{status_emoji} <b>#{counter}</b> {category_name}\n"
                text += f"   {price_min:,.0f} - {price_max:,.0f} AZN | {deal_type_label}\n\n"
                buttons.append([InlineKeyboardButton(text=f"✏️ {_('buttons.edit')} #{counter}", callback_data=RequirementCallback(action="edit", id=str(req.id)).pack())])
                counter += 1
        
        if auto_requirements:
            text += f"🚗 <b>{_('market.auto')}</b>\n\n"
            for req in auto_requirements:
                brands = ", ".join(req.brands[:3]) if req.brands else "-"
                price_min = float(req.price_min) if req.price_min else 0
                price_max = float(req.price_max) if req.price_max else 0
                status_emoji = "✅" if str(req.status) == "active" else "⏸"
                deal_type = _("deal_type.rent_buyer") if req.deal_type == "rent" else _("deal_type.sale_buyer")
                
                text += f"{status_emoji} <b>#{counter}</b> {brands}\n"
                text += f"   💰 {price_min:,.0f} - {price_max:,.0f} AZN | {deal_type}\n\n"
                buttons.append([InlineKeyboardButton(text=f"✏️ {_('buttons.edit')} #{counter} 🚗", callback_data=AutoRequirementCallback(action="edit", id=str(req.id)).pack())])
                counter += 1
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await callback.message.answer(_("requirements.empty"))


@router.callback_query(F.data.startswith("cancel_delete_req:"))
async def delete_requirement_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Cancel requirement deletion - return to edit menu."""
    await callback.answer()
    requirement_id = callback.data.split(":")[1]
    await state.update_data(editing_requirement_id=requirement_id)
    
    # Get current requirement values
    current_info = ""
    if db_session:
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
        [InlineKeyboardButton(text=f"🗑️ {_('buttons.delete')}", callback_data=f"delete_requirement:{requirement_id}")],
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
        # Remove thousand separators (commas and spaces), keep decimal dots
        text = message.text.replace(" ", "").replace(",", "")
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


# ============ AUTO REQUIREMENT EDIT HANDLERS ============

@router.callback_query(AutoRequirementCallback.filter(F.action == "edit"))
async def edit_auto_requirement_start(
    callback: CallbackQuery,
    callback_data: AutoRequirementCallback,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Start editing an auto requirement - show field selection."""
    await callback.answer()
    
    requirement_id = callback_data.id
    await state.update_data(editing_auto_requirement_id=requirement_id)
    
    # Get current requirement values
    current_info = ""
    if db_session:
        result = await db_session.execute(select(AutoRequirement).where(AutoRequirement.id == requirement_id))
        req = result.scalar_one_or_none()
        if req:
            brands = ", ".join(req.brands[:3]) if req.brands else "-"
            if req.brands and len(req.brands) > 3:
                brands += "..."
            price_min = float(req.price_min) if req.price_min else 0
            price_max = float(req.price_max) if req.price_max else 0
            year_range = f"{req.year_min or '?'}-{req.year_max or '?'}"
            mileage = req.mileage_max or "-"
            
            current_info = f"\n\n📋 {_('edit.current_values')}:\n"
            current_info += f"🚗 {_('auto.brand')}: {brands}\n"
            current_info += f"📅 {_('auto.year')}: {year_range}\n"
            current_info += f"💰 {_('edit.price')}: {price_min:,.0f} - {price_max:,.0f} AZN\n"
            current_info += f"🛣️ {_('auto.mileage')}: {mileage} km\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📅 {_('auto.year')}", callback_data="edit_auto_req_field:year")],
        [InlineKeyboardButton(text=f"💰 {_('edit.price')}", callback_data="edit_auto_req_field:price")],
        [InlineKeyboardButton(text=f"🛣️ {_('auto.mileage')}", callback_data="edit_auto_req_field:mileage")],
        [InlineKeyboardButton(text=f"🗑️ {_('buttons.delete')}", callback_data=f"delete_auto_req:{requirement_id}")],
        [InlineKeyboardButton(text=f"❌ {_('buttons.cancel')}", callback_data="edit_auto_req_cancel")],
    ])
    
    await callback.message.edit_text(_("edit.select_field") + current_info, reply_markup=keyboard)
    await state.set_state(AutoRequirementEditStates.select_field)


@router.callback_query(F.data.startswith("delete_auto_req:"))
async def delete_auto_requirement_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Show delete confirmation for auto requirement."""
    await callback.answer()
    requirement_id = callback.data.split(":")[1]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"✅ {_('buttons.yes')}", callback_data=f"confirm_del_auto_req:{requirement_id}"),
            InlineKeyboardButton(text=f"❌ {_('buttons.no')}", callback_data=f"cancel_del_auto_req:{requirement_id}"),
        ]
    ])
    
    await callback.message.edit_text(
        _("delete.confirm_requirement"),
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("confirm_del_auto_req:"))
async def delete_auto_requirement_execute(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Execute auto requirement deletion."""
    await callback.answer()
    requirement_id = callback.data.split(":")[1]
    
    if db_session:
        from uuid import UUID
        result = await db_session.execute(select(AutoRequirement).where(AutoRequirement.id == UUID(requirement_id)))
        req = result.scalar_one_or_none()
        if req:
            req.status = "deleted"
            await db_session.commit()
    
    await state.clear()
    await callback.message.edit_text(_("requirements.deleted"))


@router.callback_query(F.data.startswith("cancel_del_auto_req:"))
async def delete_auto_requirement_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Cancel auto requirement deletion - return to edit menu."""
    await callback.answer()
    requirement_id = callback.data.split(":")[1]
    await state.update_data(editing_auto_requirement_id=requirement_id)
    
    # Get current requirement values
    current_info = ""
    if db_session:
        result = await db_session.execute(select(AutoRequirement).where(AutoRequirement.id == requirement_id))
        req = result.scalar_one_or_none()
        if req:
            brands = ", ".join(req.brands[:3]) if req.brands else "-"
            if req.brands and len(req.brands) > 3:
                brands += "..."
            price_min = float(req.price_min) if req.price_min else 0
            price_max = float(req.price_max) if req.price_max else 0
            year_range = f"{req.year_min or '?'}-{req.year_max or '?'}"
            mileage = req.mileage_max or "-"
            
            current_info = f"\n\n📋 {_('edit.current_values')}:\n"
            current_info += f"🚗 {_('auto.brand')}: {brands}\n"
            current_info += f"📅 {_('auto.year')}: {year_range}\n"
            current_info += f"💰 {_('edit.price')}: {price_min:,.0f} - {price_max:,.0f} AZN\n"
            current_info += f"🛣️ {_('auto.mileage')}: {mileage} km\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📅 {_('auto.year')}", callback_data="edit_auto_req_field:year")],
        [InlineKeyboardButton(text=f"💰 {_('edit.price')}", callback_data="edit_auto_req_field:price")],
        [InlineKeyboardButton(text=f"🛣️ {_('auto.mileage')}", callback_data="edit_auto_req_field:mileage")],
        [InlineKeyboardButton(text=f"🗑️ {_('buttons.delete')}", callback_data=f"delete_auto_req:{requirement_id}")],
        [InlineKeyboardButton(text=f"❌ {_('buttons.cancel')}", callback_data="edit_auto_req_cancel")],
    ])
    
    await callback.message.edit_text(_("edit.select_field") + current_info, reply_markup=keyboard)
    await state.set_state(AutoRequirementEditStates.select_field)


@router.callback_query(F.data.startswith("edit_auto_req_field:"), AutoRequirementEditStates.select_field)
async def edit_auto_requirement_field(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Handle field selection for auto requirement edit."""
    await callback.answer()
    
    field = callback.data.split(":")[1]
    await state.update_data(editing_field=field)
    
    data = await state.get_data()
    requirement_id = data.get("editing_auto_requirement_id")
    current_value = ""
    
    if db_session and requirement_id:
        result = await db_session.execute(select(AutoRequirement).where(AutoRequirement.id == requirement_id))
        req = result.scalar_one_or_none()
        if req:
            if field == "year":
                current_value = f"\n\n{_('edit.current')}: {req.year_min or '?'}-{req.year_max or '?'}"
            elif field == "price":
                price_min = float(req.price_min) if req.price_min else 0
                price_max = float(req.price_max) if req.price_max else 0
                current_value = f"\n\n{_('edit.current')}: {price_min:,.0f} - {price_max:,.0f} AZN"
            elif field == "mileage":
                current_value = f"\n\n{_('edit.current')}: {req.mileage_max or '-'} km"
    
    prompts = {
        "year": _("edit.enter_year_range"),
        "price": _("edit.enter_price_range"),
        "mileage": _("edit.enter_mileage_max"),
    }
    
    states = {
        "year": AutoRequirementEditStates.edit_year,
        "price": AutoRequirementEditStates.edit_price,
        "mileage": AutoRequirementEditStates.edit_mileage,
    }
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⬅️ {_('buttons.back_simple')}", callback_data="edit_auto_req_back")]
    ])
    
    await callback.message.edit_text(prompts.get(field, _("edit.enter_value")) + current_value, reply_markup=keyboard)
    await state.set_state(states.get(field, AutoRequirementEditStates.select_field))


@router.message(AutoRequirementEditStates.edit_year)
async def save_auto_requirement_year(message: Message, state: FSMContext, _: Any, db_session: Optional[AsyncSession] = None) -> None:
    """Save year range for auto requirement."""
    import re
    try:
        text = message.text.replace(" ", "")
        match = re.match(r"^(\d{4})-(\d{4})$", text)
        if not match:
            raise ValueError("Invalid format")
        
        year_min = int(match.group(1))
        year_max = int(match.group(2))
        
        if year_min < 1950 or year_max > 2030 or year_min > year_max:
            raise ValueError("Invalid range")
        
        data = await state.get_data()
        requirement_id = data.get("editing_auto_requirement_id")
        
        if db_session and requirement_id:
            result = await db_session.execute(select(AutoRequirement).where(AutoRequirement.id == requirement_id))
            req = result.scalar_one_or_none()
            if req:
                req.year_min = year_min
                req.year_max = year_max
                await db_session.commit()
                await message.answer(_("edit.saved"))
            else:
                await message.answer(_("errors.not_found"))
        
        await state.clear()
    except ValueError:
        await message.answer(_("edit.invalid_range"))


@router.message(AutoRequirementEditStates.edit_price)
async def save_auto_requirement_price(message: Message, state: FSMContext, _: Any, db_session: Optional[AsyncSession] = None) -> None:
    """Save price range for auto requirement."""
    import re
    try:
        text = message.text.replace(",", ".").replace(" ", "")
        match = re.match(r"^(\d+\.?\d*)-(\d+\.?\d*)$", text)
        if not match:
            raise ValueError("Invalid format")
        
        from decimal import Decimal
        price_min = Decimal(match.group(1))
        price_max = Decimal(match.group(2))
        
        if price_min < 0 or price_max < 0 or price_min > price_max:
            raise ValueError("Invalid range")
        
        data = await state.get_data()
        requirement_id = data.get("editing_auto_requirement_id")
        
        if db_session and requirement_id:
            result = await db_session.execute(select(AutoRequirement).where(AutoRequirement.id == requirement_id))
            req = result.scalar_one_or_none()
            if req:
                req.price_min = price_min
                req.price_max = price_max
                await db_session.commit()
                await message.answer(_("edit.saved"))
            else:
                await message.answer(_("errors.not_found"))
        
        await state.clear()
    except ValueError:
        await message.answer(_("edit.invalid_range"))


@router.message(AutoRequirementEditStates.edit_mileage)
async def save_auto_requirement_mileage(message: Message, state: FSMContext, _: Any, db_session: Optional[AsyncSession] = None) -> None:
    """Save max mileage for auto requirement."""
    try:
        mileage = int(message.text.replace(" ", "").replace(",", ""))
        if mileage < 0 or mileage > 1000000:
            raise ValueError()
        
        data = await state.get_data()
        requirement_id = data.get("editing_auto_requirement_id")
        
        if db_session and requirement_id:
            result = await db_session.execute(select(AutoRequirement).where(AutoRequirement.id == requirement_id))
            req = result.scalar_one_or_none()
            if req:
                req.mileage_max = mileage
                await db_session.commit()
                await message.answer(_("edit.saved"))
            else:
                await message.answer(_("errors.not_found"))
        
        await state.clear()
    except ValueError:
        await message.answer(_("auto.invalid_mileage"))


@router.callback_query(F.data == "edit_auto_req_cancel")
async def cancel_auto_requirement_edit(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    """Cancel auto requirement edit."""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(_("buttons.cancelled"))


@router.callback_query(F.data == "edit_auto_req_back")
async def back_to_auto_requirement_field_select(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Go back to field selection for auto requirement edit."""
    await callback.answer()
    
    data = await state.get_data()
    requirement_id = data.get("editing_auto_requirement_id")
    
    current_info = ""
    if db_session and requirement_id:
        result = await db_session.execute(select(AutoRequirement).where(AutoRequirement.id == requirement_id))
        req = result.scalar_one_or_none()
        if req:
            brands = ", ".join(req.brands[:3]) if req.brands else "-"
            if req.brands and len(req.brands) > 3:
                brands += "..."
            price_min = float(req.price_min) if req.price_min else 0
            price_max = float(req.price_max) if req.price_max else 0
            year_range = f"{req.year_min or '?'}-{req.year_max or '?'}"
            mileage = req.mileage_max or "-"
            
            current_info = f"\n\n📋 {_('edit.current_values')}:\n"
            current_info += f"🚗 {_('auto.brand')}: {brands}\n"
            current_info += f"📅 {_('auto.year')}: {year_range}\n"
            current_info += f"💰 {_('edit.price')}: {price_min:,.0f} - {price_max:,.0f} AZN\n"
            current_info += f"🛣️ {_('auto.mileage')}: {mileage} km\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📅 {_('auto.year')}", callback_data="edit_auto_req_field:year")],
        [InlineKeyboardButton(text=f"💰 {_('edit.price')}", callback_data="edit_auto_req_field:price")],
        [InlineKeyboardButton(text=f"🛣️ {_('auto.mileage')}", callback_data="edit_auto_req_field:mileage")],
        [InlineKeyboardButton(text=f"❌ {_('buttons.cancel')}", callback_data="edit_auto_req_cancel")],
    ])
    
    await callback.message.edit_text(_("edit.select_field") + current_info, reply_markup=keyboard)
    await state.set_state(AutoRequirementEditStates.select_field)


# ============ AUTO LISTING EDIT HANDLERS ============

@router.callback_query(AutoListingCallback.filter(F.action == "edit"))
async def edit_auto_listing_start(
    callback: CallbackQuery,
    callback_data: AutoListingCallback,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Start editing an auto listing - show field selection."""
    await callback.answer()
    
    listing_id = callback_data.id
    await state.update_data(editing_auto_listing_id=listing_id)
    
    current_info = ""
    if db_session:
        result = await db_session.execute(select(AutoListing).where(AutoListing.id == listing_id))
        lst = result.scalar_one_or_none()
        if lst:
            price = float(lst.price) if lst.price else 0
            mileage = lst.mileage or "-"
            desc = lst.description[:50] + "..." if lst.description and len(lst.description) > 50 else (lst.description or "-")
            
            current_info = f"\n\n📋 {_('edit.current_values')}:\n"
            current_info += f"🚗 {lst.brand} {lst.model} ({lst.year})\n"
            current_info += f"💰 {_('edit.price')}: {price:,.0f} AZN\n"
            current_info += f"🛣️ {_('auto.mileage')}: {mileage} km\n"
            current_info += f"📝 {_('edit.description')}: {desc}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💰 {_('edit.price')}", callback_data="edit_auto_lst_field:price")],
        [InlineKeyboardButton(text=f"🛣️ {_('auto.mileage')}", callback_data="edit_auto_lst_field:mileage")],
        [InlineKeyboardButton(text=f"📝 {_('edit.description')}", callback_data="edit_auto_lst_field:description")],
        [InlineKeyboardButton(text=f"🗑️ {_('buttons.delete')}", callback_data=f"delete_auto_lst:{listing_id}")],
        [InlineKeyboardButton(text=f"❌ {_('buttons.cancel')}", callback_data="edit_auto_lst_cancel")],
    ])
    
    await callback.message.edit_text(_("edit.select_field") + current_info, reply_markup=keyboard)
    await state.set_state(AutoListingEditStates.select_field)


@router.callback_query(F.data.startswith("delete_auto_lst:"))
async def delete_auto_listing_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Show delete confirmation for auto listing."""
    await callback.answer()
    listing_id = callback.data.split(":")[1]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"✅ {_('buttons.yes')}", callback_data=f"confirm_del_auto_lst:{listing_id}"),
            InlineKeyboardButton(text=f"❌ {_('buttons.no')}", callback_data=f"cancel_del_auto_lst:{listing_id}"),
        ]
    ])
    
    await callback.message.edit_text(
        _("delete.confirm_listing"),
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("confirm_del_auto_lst:"))
async def delete_auto_listing_execute(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Execute auto listing deletion."""
    await callback.answer()
    listing_id = callback.data.split(":")[1]
    
    if db_session:
        result = await db_session.execute(select(AutoListing).where(AutoListing.id == listing_id))
        lst = result.scalar_one_or_none()
        if lst:
            await db_session.delete(lst)
            await db_session.commit()
    
    await state.clear()
    await callback.message.edit_text(_("listings.deleted"))


@router.callback_query(F.data.startswith("cancel_del_auto_lst:"))
async def delete_auto_listing_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Cancel auto listing deletion - return to edit menu."""
    await callback.answer()
    listing_id = callback.data.split(":")[1]
    await state.update_data(editing_auto_listing_id=listing_id)
    
    current_info = ""
    if db_session:
        result = await db_session.execute(select(AutoListing).where(AutoListing.id == listing_id))
        lst = result.scalar_one_or_none()
        if lst:
            price = float(lst.price) if lst.price else 0
            mileage = lst.mileage or "-"
            desc = lst.description[:50] + "..." if lst.description and len(lst.description) > 50 else (lst.description or "-")
            
            current_info = f"\n\n📋 {_('edit.current_values')}:\n"
            current_info += f"🚗 {lst.brand} {lst.model} ({lst.year})\n"
            current_info += f"💰 {_('edit.price')}: {price:,.0f} AZN\n"
            current_info += f"🛣️ {_('auto.mileage')}: {mileage} km\n"
            current_info += f"📝 {_('edit.description')}: {desc}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💰 {_('edit.price')}", callback_data="edit_auto_lst_field:price")],
        [InlineKeyboardButton(text=f"🛣️ {_('auto.mileage')}", callback_data="edit_auto_lst_field:mileage")],
        [InlineKeyboardButton(text=f"📝 {_('edit.description')}", callback_data="edit_auto_lst_field:description")],
        [InlineKeyboardButton(text=f"🗑️ {_('buttons.delete')}", callback_data=f"delete_auto_lst:{listing_id}")],
        [InlineKeyboardButton(text=f"❌ {_('buttons.cancel')}", callback_data="edit_auto_lst_cancel")],
    ])
    
    await callback.message.edit_text(_("edit.select_field") + current_info, reply_markup=keyboard)
    await state.set_state(AutoListingEditStates.select_field)


@router.callback_query(F.data.startswith("edit_auto_lst_field:"), AutoListingEditStates.select_field)
async def edit_auto_listing_field(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Handle field selection for auto listing edit."""
    await callback.answer()
    
    field = callback.data.split(":")[1]
    await state.update_data(editing_field=field)
    
    data = await state.get_data()
    listing_id = data.get("editing_auto_listing_id")
    current_value = ""
    
    if db_session and listing_id:
        result = await db_session.execute(select(AutoListing).where(AutoListing.id == listing_id))
        lst = result.scalar_one_or_none()
        if lst:
            if field == "price":
                price = float(lst.price) if lst.price else 0
                current_value = f"\n\n{_('edit.current')}: {price:,.0f} AZN"
            elif field == "mileage":
                current_value = f"\n\n{_('edit.current')}: {lst.mileage or '-'} km"
            elif field == "description":
                desc = lst.description[:100] + "..." if lst.description and len(lst.description) > 100 else (lst.description or "-")
                current_value = f"\n\n{_('edit.current')}: {desc}"
    
    prompts = {
        "price": _("edit.enter_price"),
        "mileage": _("edit.enter_mileage"),
        "description": _("edit.enter_description"),
    }
    
    states = {
        "price": AutoListingEditStates.edit_price,
        "mileage": AutoListingEditStates.edit_mileage,
        "description": AutoListingEditStates.edit_description,
    }
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⬅️ {_('buttons.back_simple')}", callback_data="edit_auto_lst_back")]
    ])
    
    await callback.message.edit_text(prompts.get(field, _("edit.enter_value")) + current_value, reply_markup=keyboard)
    await state.set_state(states.get(field, AutoListingEditStates.select_field))


@router.message(AutoListingEditStates.edit_price)
async def save_auto_listing_price(message: Message, state: FSMContext, _: Any, db_session: Optional[AsyncSession] = None) -> None:
    """Save price for auto listing."""
    try:
        from decimal import Decimal
        price = Decimal(message.text.replace(",", ".").replace(" ", ""))
        if price <= 0:
            raise ValueError()
        
        data = await state.get_data()
        listing_id = data.get("editing_auto_listing_id")
        
        if db_session and listing_id:
            result = await db_session.execute(select(AutoListing).where(AutoListing.id == listing_id))
            lst = result.scalar_one_or_none()
            if lst:
                lst.price = price
                await db_session.commit()
                await message.answer(_("edit.saved"))
            else:
                await message.answer(_("errors.not_found"))
        
        await state.clear()
    except (ValueError, Exception):
        await message.answer(_("form.price.invalid"))


@router.message(AutoListingEditStates.edit_mileage)
async def save_auto_listing_mileage(message: Message, state: FSMContext, _: Any, db_session: Optional[AsyncSession] = None) -> None:
    """Save mileage for auto listing."""
    try:
        mileage = int(message.text.replace(" ", "").replace(",", ""))
        if mileage < 0 or mileage > 1000000:
            raise ValueError()
        
        data = await state.get_data()
        listing_id = data.get("editing_auto_listing_id")
        
        if db_session and listing_id:
            result = await db_session.execute(select(AutoListing).where(AutoListing.id == listing_id))
            lst = result.scalar_one_or_none()
            if lst:
                lst.mileage = mileage
                await db_session.commit()
                await message.answer(_("edit.saved"))
            else:
                await message.answer(_("errors.not_found"))
        
        await state.clear()
    except ValueError:
        await message.answer(_("auto.invalid_mileage"))


@router.message(AutoListingEditStates.edit_description)
async def save_auto_listing_description(message: Message, state: FSMContext, _: Any, db_session: Optional[AsyncSession] = None) -> None:
    """Save description for auto listing."""
    data = await state.get_data()
    listing_id = data.get("editing_auto_listing_id")
    
    if db_session and listing_id:
        result = await db_session.execute(select(AutoListing).where(AutoListing.id == listing_id))
        lst = result.scalar_one_or_none()
        if lst:
            lst.description = message.text[:1000]
            await db_session.commit()
            await message.answer(_("edit.saved"))
        else:
            await message.answer(_("errors.not_found"))
    
    await state.clear()


@router.callback_query(F.data == "edit_auto_lst_cancel")
async def cancel_auto_listing_edit(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    """Cancel auto listing edit."""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(_("buttons.cancelled"))


@router.callback_query(F.data == "edit_auto_lst_back")
async def back_to_auto_listing_field_select(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Go back to field selection for auto listing edit."""
    await callback.answer()
    
    data = await state.get_data()
    listing_id = data.get("editing_auto_listing_id")
    
    current_info = ""
    if db_session and listing_id:
        result = await db_session.execute(select(AutoListing).where(AutoListing.id == listing_id))
        lst = result.scalar_one_or_none()
        if lst:
            price = float(lst.price) if lst.price else 0
            mileage = lst.mileage or "-"
            desc = lst.description[:50] + "..." if lst.description and len(lst.description) > 50 else (lst.description or "-")
            
            current_info = f"\n\n📋 {_('edit.current_values')}:\n"
            current_info += f"🚗 {lst.brand} {lst.model} ({lst.year})\n"
            current_info += f"💰 {_('edit.price')}: {price:,.0f} AZN\n"
            current_info += f"🛣️ {_('auto.mileage')}: {mileage} km\n"
            current_info += f"📝 {_('edit.description')}: {desc}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💰 {_('edit.price')}", callback_data="edit_auto_lst_field:price")],
        [InlineKeyboardButton(text=f"🛣️ {_('auto.mileage')}", callback_data="edit_auto_lst_field:mileage")],
        [InlineKeyboardButton(text=f"📝 {_('edit.description')}", callback_data="edit_auto_lst_field:description")],
        [InlineKeyboardButton(text=f"❌ {_('buttons.cancel')}", callback_data="edit_auto_lst_cancel")],
    ])
    
    await callback.message.edit_text(_("edit.select_field") + current_info, reply_markup=keyboard)
    await state.set_state(AutoListingEditStates.select_field)


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


# ============ MATCHES HANDLERS ============

async def _get_user_matches(db_session: AsyncSession, user: Any) -> list:
    """Get all matches for user (as buyer or seller) - both real estate and auto."""
    from app.models.match import Match, MatchStatusEnum
    from app.models.listing import Listing
    from app.models.requirement import Requirement
    from app.models.auto import AutoMatch, AutoListing, AutoRequirement
    
    all_matches = []
    
    # ============ REAL ESTATE MATCHES ============
    # Get matches where user is buyer (has requirement)
    buyer_matches_query = (
        select(Match, Listing, Requirement)
        .join(Requirement, Match.requirement_id == Requirement.id)
        .join(Listing, Match.listing_id == Listing.id)
        .where(Requirement.user_id == user.id)
        .where(Match.status.in_([MatchStatusEnum.NEW, MatchStatusEnum.VIEWED, MatchStatusEnum.CONTACTED]))
        .order_by(Match.score.desc())
    )
    buyer_result = await db_session.execute(buyer_matches_query)
    for row in buyer_result.all():
        all_matches.append({"match": row[0], "listing": row[1], "requirement": row[2], "is_buyer": True, "type": "realty"})
    
    # Get matches where user is seller (has listing)
    seller_matches_query = (
        select(Match, Listing, Requirement)
        .join(Listing, Match.listing_id == Listing.id)
        .join(Requirement, Match.requirement_id == Requirement.id)
        .where(Listing.user_id == user.id)
        .where(Match.status.in_([MatchStatusEnum.NEW, MatchStatusEnum.VIEWED, MatchStatusEnum.CONTACTED]))
        .order_by(Match.score.desc())
    )
    seller_result = await db_session.execute(seller_matches_query)
    for row in seller_result.all():
        all_matches.append({"match": row[0], "listing": row[1], "requirement": row[2], "is_buyer": False, "type": "realty"})
    
    # ============ AUTO MATCHES ============
    # Get auto matches where user is buyer (has requirement)
    auto_buyer_query = (
        select(AutoMatch, AutoListing, AutoRequirement)
        .join(AutoRequirement, AutoMatch.auto_requirement_id == AutoRequirement.id)
        .join(AutoListing, AutoMatch.auto_listing_id == AutoListing.id)
        .where(AutoRequirement.user_id == user.id)
        .where(AutoMatch.status.in_(["pending", "viewed", "contacted"]))
        .order_by(AutoMatch.score.desc())
    )
    auto_buyer_result = await db_session.execute(auto_buyer_query)
    for row in auto_buyer_result.all():
        all_matches.append({"match": row[0], "listing": row[1], "requirement": row[2], "is_buyer": True, "type": "auto"})
    
    # Get auto matches where user is seller (has listing)
    auto_seller_query = (
        select(AutoMatch, AutoListing, AutoRequirement)
        .join(AutoListing, AutoMatch.auto_listing_id == AutoListing.id)
        .join(AutoRequirement, AutoMatch.auto_requirement_id == AutoRequirement.id)
        .where(AutoListing.user_id == user.id)
        .where(AutoMatch.status.in_(["pending", "viewed", "contacted"]))
        .order_by(AutoMatch.score.desc())
    )
    auto_seller_result = await db_session.execute(auto_seller_query)
    for row in auto_seller_result.all():
        all_matches.append({"match": row[0], "listing": row[1], "requirement": row[2], "is_buyer": False, "type": "auto"})
    
    # Sort by score descending
    all_matches.sort(key=lambda x: x["match"].score, reverse=True)
    return all_matches


async def _show_match_page(
    message_or_callback: Any,
    _: Any,
    user: Any,
    db_session: AsyncSession,
    page: int = 0,
    edit: bool = False,
) -> None:
    """Show a single match with pagination and photo - supports both real estate and auto."""
    from app.models.match import MatchStatusEnum
    
    matches = await _get_user_matches(db_session, user)
    total = len(matches)
    
    if total == 0:
        text = _("matches.empty")
        if edit and hasattr(message_or_callback, "message"):
            await message_or_callback.message.edit_text(text)
        else:
            target = message_or_callback.message if hasattr(message_or_callback, "message") else message_or_callback
            await target.answer(text)
        return
    
    # Ensure page is in bounds
    page = max(0, min(page, total - 1))
    
    match_data = matches[page]
    match = match_data["match"]
    listing = match_data["listing"]
    req = match_data["requirement"]
    is_buyer = match_data["is_buyer"]
    match_type = match_data.get("type", "realty")
    
    # Mark as viewed
    if match_type == "realty":
        if match.status == MatchStatusEnum.NEW:
            match.status = MatchStatusEnum.VIEWED
            await db_session.commit()
    else:
        if match.status == "pending":
            match.status = "viewed"
            await db_session.commit()
    
    # Get photo URL
    photo_url = None
    if is_buyer:
        if match_type == "realty":
            from app.models.listing import ListingMedia
            media_result = await db_session.execute(
                select(ListingMedia)
                .where(ListingMedia.listing_id == listing.id)
                .order_by(ListingMedia.order)
                .limit(1)
            )
            media = media_result.scalar_one_or_none()
            if media:
                photo_url = media.url
        else:
            from app.models.auto import AutoMedia
            media_result = await db_session.execute(
                select(AutoMedia)
                .where(AutoMedia.auto_listing_id == listing.id)
                .order_by(AutoMedia.order)
                .limit(1)
            )
            media = media_result.scalar_one_or_none()
            if media:
                photo_url = media.url
    
    # Build text
    type_emoji = "🏠" if match_type == "realty" else "🚗"
    text = f"<b>📊 Совпадение {page + 1}/{total}</b> {type_emoji}\n\n"
    text += f"🎯 Совпадение: <b>{match.score}%</b>\n\n"
    
    if match_type == "auto":
        if is_buyer:
            text += f"<b>🚗 {_('auto.title')}:</b>\n"
            text += f"🏷️ {listing.brand} {listing.model}\n"
            text += f"📅 {_('auto.year')}: {listing.year}\n"
            text += f"💰 {_('auto.price')}: {float(listing.price):,.0f} AZN\n"
            if listing.mileage:
                text += f"🛣️ {_('auto.mileage')}: {listing.mileage:,} km\n"
            if listing.fuel_type:
                text += f"⛽ {_(f'auto.fuel.{listing.fuel_type}')}\n"
            if listing.transmission:
                text += f"⚙️ {_(f'auto.transmission.{listing.transmission}')}\n"
            if listing.description:
                desc = listing.description[:150] + "..." if len(listing.description) > 150 else listing.description
                text += f"\n📝 {desc}\n"
        else:
            text += f"<b>🔍 {_('auto.title')}:</b>\n"
            brands = ", ".join(req.brands[:3]) if req.brands else "-"
            if req.brands and len(req.brands) > 3:
                brands += "..."
            text += f"🏷️ {_('auto.brand')}: {brands}\n"
            text += f"📅 {_('auto.year')}: {req.year_min or '?'} - {req.year_max or '?'}\n"
            price_min = float(req.price_min) if req.price_min else 0
            price_max = float(req.price_max) if req.price_max else 0
            text += f"💰 {_('auto.price')}: {price_min:,.0f} - {price_max:,.0f} AZN\n"
            if req.mileage_max:
                text += f"🛣️ {_('auto.mileage')}: {req.mileage_max:,} km\n"
    else:
        if is_buyer:
            text += f"<b>📋 Объявление:</b>\n"
            text += f"💰 Цена: {float(listing.price):,.0f} AZN\n"
            if listing.rooms:
                text += f"🏠 Комнат: {listing.rooms}\n"
            if listing.area:
                text += f"📐 Площадь: {float(listing.area)} м²\n"
            if listing.floor:
                text += f"🏢 Этаж: {listing.floor}"
                if listing.building_floors:
                    text += f"/{listing.building_floors}"
                text += "\n"
            if listing.description:
                desc = listing.description[:150] + "..." if len(listing.description) > 150 else listing.description
                text += f"\n📝 {desc}\n"
        else:
            text += f"<b>🔍 Запрос покупателя:</b>\n"
            price_min = float(req.price_min) if req.price_min else 0
            price_max = float(req.price_max) if req.price_max else 0
            text += f"💰 Бюджет: {price_min:,.0f} - {price_max:,.0f} AZN\n"
            if req.rooms_min or req.rooms_max:
                text += f"🏠 Комнат: {req.rooms_min or '?'} - {req.rooms_max or '?'}\n"
            if req.area_min or req.area_max:
                area_min = float(req.area_min) if req.area_min else 0
                area_max = float(req.area_max) if req.area_max else 0
                text += f"📐 Площадь: {area_min} - {area_max} м²\n"
    
    # Build keyboard
    buttons = []
    
    # Navigation row - always show if more than 1 match
    if total > 1:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"matches:page:{page - 1}"))
        else:
            nav_row.append(InlineKeyboardButton(text=" ", callback_data="noop"))
        if page < total - 1:
            nav_row.append(InlineKeyboardButton(text="Далее ➡️", callback_data=f"matches:page:{page + 1}"))
        else:
            nav_row.append(InlineKeyboardButton(text=" ", callback_data="noop"))
        buttons.append(nav_row)
    
    # Contact button
    buttons.append([
        InlineKeyboardButton(text=f"💬 {_('match.contact')}", callback_data=f"match:contact:{match.id}:{page}:{match_type}")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    # Send with photo if available
    target = message_or_callback.message if hasattr(message_or_callback, "message") else message_or_callback
    bot = target.bot if hasattr(target, "bot") else message_or_callback.bot
    chat_id = target.chat.id
    
    if edit and hasattr(message_or_callback, "message"):
        # Delete old message and send new one with photo
        try:
            await message_or_callback.message.delete()
        except Exception:
            pass
    
    if photo_url:
        try:
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo_url,
                caption=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        except Exception:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=keyboard)


@router.message(Command("matches"))
async def cmd_matches(
    message: Message,
    _: Any,
    user: Any,
    lang: str,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Handle /matches command - show user's matches with pagination."""
    if not db_session or not user:
        await message.answer(_("matches.empty"))
        return
    
    await _show_match_page(message, _, user, db_session, page=0, edit=False)


@router.callback_query(F.data.startswith("matches:page:"))
async def cb_matches_page(
    callback: CallbackQuery,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Handle pagination for matches."""
    await callback.answer()
    
    if not db_session:
        return
    
    page = int(callback.data.split(":")[2])
    await _show_match_page(callback, _, user, db_session, page=page, edit=True)


@router.callback_query(F.data.startswith("match:contact:"))
async def cb_match_contact(
    callback: CallbackQuery,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Send contact request for a match - requires confirmation from other party."""
    await callback.answer()
    
    parts = callback.data.split(":")
    match_id = parts[2]
    page = int(parts[3]) if len(parts) > 3 else 0
    match_type = parts[4] if len(parts) > 4 else "realty"
    
    if not db_session:
        await callback.message.answer(_("errors.general"))
        return
    
    from app.models.user import User
    
    if match_type == "auto":
        # Handle auto match
        from app.models.auto import AutoMatch, AutoListing, AutoRequirement, AutoChat
        
        result = await db_session.execute(
            select(AutoMatch, AutoListing, AutoRequirement)
            .join(AutoListing, AutoMatch.auto_listing_id == AutoListing.id)
            .join(AutoRequirement, AutoMatch.auto_requirement_id == AutoRequirement.id)
            .where(AutoMatch.id == match_id)
        )
        row = result.first()
        
        if not row:
            await callback.message.answer(_("errors.not_found"))
            return
        
        match, listing, req = row
        
        # Check if chat already exists
        existing_chat = await db_session.execute(
            select(AutoChat).where(AutoChat.auto_match_id == match.id)
        )
        chat = existing_chat.scalar_one_or_none()
        
        buyer_id = req.user_id
        seller_id = listing.user_id
        is_buyer = req.user_id == user.id
        
        if chat and chat.status == "active":
            await callback.message.answer(_("chat.already_exists"))
            return
        
        # Check if request already pending
        if match.status == "pending_contact":
            await callback.message.answer(_("chat.request_pending"))
            return
        
        # Set match to pending_contact status
        match.status = "pending_contact"
        await db_session.commit()
        
        await callback.message.answer(_("chat.request_sent"))
        
        # Notify other party with accept/decline buttons
        other_user_id = seller_id if is_buyer else buyer_id
        other_result = await db_session.execute(select(User).where(User.id == other_user_id))
        other_user = other_result.scalar_one_or_none()
        
        if other_user and other_user.telegram_id:
            try:
                requester_role = _("chat.buyer") if is_buyer else _("chat.seller")
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text=f"✅ {_('buttons.accept')}", callback_data=f"chat_accept:{match.id}:{match_type}"),
                        InlineKeyboardButton(text=f"❌ {_('buttons.decline')}", callback_data=f"chat_decline:{match.id}:{match_type}"),
                    ]
                ])
                await callback.bot.send_message(
                    chat_id=other_user.telegram_id,
                    text=f"💬 {_('chat.contact_request')}\n\n"
                         f"🚗 {listing.brand} {listing.model} ({listing.year})\n"
                         f"💰 {float(listing.price):,.0f} AZN\n"
                         f"🎯 {_('match.score')}: {match.score}%\n\n"
                         f"{_('chat.from')}: {requester_role}",
                    reply_markup=keyboard,
                )
            except Exception:
                pass
        return
    
    # Handle real estate match (same logic)
    from app.models.match import Match, MatchStatusEnum
    from app.models.listing import Listing
    from app.models.requirement import Requirement
    from app.models.chat import Chat, ChatStatusEnum
    
    result = await db_session.execute(
        select(Match, Listing, Requirement)
        .join(Listing, Match.listing_id == Listing.id)
        .join(Requirement, Match.requirement_id == Requirement.id)
        .where(Match.id == match_id)
    )
    row = result.first()
    
    if not row:
        await callback.message.answer(_("errors.not_found"))
        return
    
    match, listing, req = row
    
    # Check if chat already exists
    existing_chat = await db_session.execute(
        select(Chat).where(Chat.match_id == match.id)
    )
    chat = existing_chat.scalar_one_or_none()
    
    buyer_id = req.user_id
    seller_id = listing.user_id
    is_buyer = req.user_id == user.id
    
    if chat and chat.status == ChatStatusEnum.ACTIVE:
        await callback.message.answer(_("chat.already_exists"))
        return
    
    # Check if request already pending
    if match.status == MatchStatusEnum.PENDING_CONTACT:
        await callback.message.answer(_("chat.request_pending"))
        return
    
    # Set match to pending_contact status
    match.status = MatchStatusEnum.PENDING_CONTACT
    await db_session.commit()
    
    await callback.message.answer(_("chat.request_sent"))
    
    # Notify other party with accept/decline buttons
    other_user_id = seller_id if is_buyer else buyer_id
    other_result = await db_session.execute(select(User).where(User.id == other_user_id))
    other_user = other_result.scalar_one_or_none()
    
    if other_user and other_user.telegram_id:
        try:
            requester_role = _("chat.buyer") if is_buyer else _("chat.seller")
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text=f"✅ {_('buttons.accept')}", callback_data=f"chat_accept:{match.id}:{match_type}"),
                    InlineKeyboardButton(text=f"❌ {_('buttons.decline')}", callback_data=f"chat_decline:{match.id}:{match_type}"),
                ]
            ])
            
            price = float(listing.price) if listing.price else 0
            await callback.bot.send_message(
                chat_id=other_user.telegram_id,
                text=f"💬 {_('chat.contact_request')}\n\n"
                     f"🏠 {price:,.0f} AZN\n"
                     f"🎯 {_('match.score')}: {match.score}%\n\n"
                     f"{_('chat.from')}: {requester_role}",
                reply_markup=keyboard,
            )
        except Exception:
            pass


# ============ CHAT REQUEST ACCEPT/DECLINE HANDLERS ============

@router.callback_query(F.data.startswith("chat_accept:"))
async def cb_chat_accept(
    callback: CallbackQuery,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Accept chat request and create chat."""
    await callback.answer()
    
    parts = callback.data.split(":")
    match_id = parts[1]
    match_type = parts[2] if len(parts) > 2 else "realty"
    
    if not db_session:
        await callback.message.answer(_("errors.general"))
        return
    
    from app.models.user import User
    
    if match_type == "auto":
        from app.models.auto import AutoMatch, AutoListing, AutoRequirement, AutoChat
        
        result = await db_session.execute(
            select(AutoMatch, AutoListing, AutoRequirement)
            .join(AutoListing, AutoMatch.auto_listing_id == AutoListing.id)
            .join(AutoRequirement, AutoMatch.auto_requirement_id == AutoRequirement.id)
            .where(AutoMatch.id == match_id)
        )
        row = result.first()
        
        if not row:
            await callback.message.edit_text(_("errors.not_found"))
            return
        
        match, listing, req = row
        buyer_id = req.user_id
        seller_id = listing.user_id
        
        # Create chat
        chat = AutoChat(
            auto_match_id=match.id,
            buyer_id=buyer_id,
            seller_id=seller_id,
            buyer_alias=_("chat.buyer"),
            seller_alias=_("chat.seller"),
            status="active",
        )
        db_session.add(chat)
        match.status = "contacted"
        await db_session.commit()
        
        await callback.message.edit_text(
            f"✅ {_('chat.request_accepted')}\n\n"
            f"🚗 {listing.brand} {listing.model}\n"
            f"{_('chat.use_my_chats')}"
        )
        
        # Notify requester
        requester_id = buyer_id if seller_id == user.id else seller_id
        requester_result = await db_session.execute(select(User).where(User.id == requester_id))
        requester = requester_result.scalar_one_or_none()
        
        if requester and requester.telegram_id:
            try:
                await callback.bot.send_message(
                    chat_id=requester.telegram_id,
                    text=f"✅ {_('chat.your_request_accepted')}\n\n"
                         f"🚗 {listing.brand} {listing.model}\n"
                         f"{_('chat.use_my_chats')}",
                )
            except Exception:
                pass
    else:
        from app.models.match import Match, MatchStatusEnum
        from app.models.listing import Listing
        from app.models.requirement import Requirement
        from app.models.chat import Chat, ChatStatusEnum
        
        result = await db_session.execute(
            select(Match, Listing, Requirement)
            .join(Listing, Match.listing_id == Listing.id)
            .join(Requirement, Match.requirement_id == Requirement.id)
            .where(Match.id == match_id)
        )
        row = result.first()
        
        if not row:
            await callback.message.edit_text(_("errors.not_found"))
            return
        
        match, listing, req = row
        buyer_id = req.user_id
        seller_id = listing.user_id
        
        # Create chat
        chat = Chat(
            match_id=match.id,
            buyer_alias=_("chat.buyer"),
            seller_alias=_("chat.seller"),
            status=ChatStatusEnum.ACTIVE,
        )
        db_session.add(chat)
        match.status = MatchStatusEnum.CONTACTED
        await db_session.commit()
        
        price = float(listing.price) if listing.price else 0
        await callback.message.edit_text(
            f"✅ {_('chat.request_accepted')}\n\n"
            f"🏠 {price:,.0f} AZN\n"
            f"{_('chat.use_my_chats')}"
        )
        
        # Notify requester
        requester_id = buyer_id if seller_id == user.id else seller_id
        requester_result = await db_session.execute(select(User).where(User.id == requester_id))
        requester = requester_result.scalar_one_or_none()
        
        if requester and requester.telegram_id:
            try:
                await callback.bot.send_message(
                    chat_id=requester.telegram_id,
                    text=f"✅ {_('chat.your_request_accepted')}\n\n"
                         f"🏠 {price:,.0f} AZN\n"
                         f"{_('chat.use_my_chats')}",
                )
            except Exception:
                pass


@router.callback_query(F.data.startswith("chat_decline:"))
async def cb_chat_decline(
    callback: CallbackQuery,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Decline chat request."""
    await callback.answer()
    
    parts = callback.data.split(":")
    match_id = parts[1]
    match_type = parts[2] if len(parts) > 2 else "realty"
    
    if not db_session:
        await callback.message.answer(_("errors.general"))
        return
    
    from app.models.user import User
    
    if match_type == "auto":
        from app.models.auto import AutoMatch
        
        result = await db_session.execute(select(AutoMatch).where(AutoMatch.id == match_id))
        match = result.scalar_one_or_none()
        
        if match:
            match.status = "viewed"  # Reset to viewed
            await db_session.commit()
    else:
        from app.models.match import Match, MatchStatusEnum
        
        result = await db_session.execute(select(Match).where(Match.id == match_id))
        match = result.scalar_one_or_none()
        
        if match:
            match.status = MatchStatusEnum.VIEWED  # Reset to viewed
            await db_session.commit()
    
    await callback.message.edit_text(_("chat.request_declined"))


# ============ UNKNOWN COMMAND HANDLER ============
# This MUST be at the end of the file to not catch valid commands

@router.message(F.text.startswith("/"))
async def unknown_command(
    message: Message,
    _: Any,
) -> None:
    """Handle unknown commands."""
    await message.answer(_("errors.unknown_command"))
