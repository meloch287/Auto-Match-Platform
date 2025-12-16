import logging
from typing import Any, Optional
from uuid import UUID

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.builders import (
    build_vip_listings_keyboard,
    build_vip_duration_keyboard,
    build_vip_confirm_keyboard,
    build_start_over_keyboard,
    build_profile_keyboard,
)
from app.bot.keyboards.callbacks import VIPCallback
from app.bot.states import VIPStates
from app.models.listing import Listing, ListingStatusEnum

logger = logging.getLogger(__name__)

router = Router(name="vip")

@router.message(Command("profile"))
async def cmd_profile(
    message: Message,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """
    Handle /profile command - show personal cabinet with subscription status and VIP options.
    
    Requirements: 3.1
    """
    await state.clear()
    
    if not db_session or not user:
        logger.error(f"Profile: db_session={db_session}, user={user}")
        await message.answer(_("errors.general"))
        return
    
    try:
        from app.services.user import UserService
        from app.models.user import SubscriptionTypeEnum
        
        user_service = UserService(db_session)
        # Get fresh user from current session to avoid detached instance issues
        fresh_user = await user_service.get_by_telegram_id(user.telegram_id)
        if not fresh_user:
            await message.answer(_("errors.general"))
            return
        
        limits_info = await user_service.get_free_limits_info(fresh_user)
        
        # Build status text
        text = f"<b>{_('profile.title')}</b>\n\n"
        
        # Subscription status
        is_premium = fresh_user.subscription_type != SubscriptionTypeEnum.FREE
        if is_premium:
            expires_str = fresh_user.subscription_expires_at.strftime("%Y-%m-%d") if fresh_user.subscription_expires_at else "-"
            text += f"✅ {_('subscription.status')}: <b>{_('subscription.premium')}</b>\n"
            text += f"📅 {_('subscription.expires')}: {expires_str}\n\n"
            text += f"🎁 {_('limits.unlimited')}\n\n"
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
                text += f"🔍 {_('limits.requirements_label')}: {req_used}/∞\n\n"
            else:
                text += f"🔍 {_('limits.requirements_label')}: {req_used}/{req_max} "
                text += f"({_('limits.remaining')}: {req_remaining})\n\n"
            
            text += f"💡 {_('subscription.upgrade_prompt')}\n\n"
        
        # Show profile with Premium button
        await message.answer(
            text,
            reply_markup=build_profile_keyboard(_, is_premium=is_premium),
            parse_mode="HTML",
        )
        
    except Exception as e:
        logger.exception(f"Error in /profile command: {e}")
        await message.answer(_("errors.general"))

@router.callback_query(VIPCallback.filter(F.action == "select"), VIPStates.select_listing)
async def vip_listing_selected(
    callback: CallbackQuery,
    callback_data: VIPCallback,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Handle listing selection for VIP upgrade."""
    await callback.answer()
    
    listing_id = callback_data.id
    
    if db_session:
        result = await db_session.execute(
            select(Listing).where(Listing.id == UUID(listing_id))
        )
        listing = result.scalar_one_or_none()
        
        if listing and listing.is_vip and listing.vip_expires_at:
            expires_str = listing.vip_expires_at.strftime("%Y-%m-%d %H:%M")
            await callback.message.edit_text(
                _("vip.already_vip").format(expires_at=expires_str),
                reply_markup=build_start_over_keyboard(_),
            )
            await state.clear()
            return
    
    await state.update_data(listing_id=listing_id)
    
    await callback.message.edit_text(
        f"{_('vip.title')}\n\n{_('vip.select_duration')}",
        reply_markup=build_vip_duration_keyboard(listing_id, _),
    )
    await state.set_state(VIPStates.select_duration)

@router.callback_query(VIPCallback.filter(F.action == "duration"), VIPStates.select_duration)
async def vip_duration_selected(
    callback: CallbackQuery,
    callback_data: VIPCallback,
    state: FSMContext,
    _: Any,
) -> None:
    """Handle VIP duration selection."""
    await callback.answer()
    
    listing_id = callback_data.id
    days = callback_data.days
    
    await state.update_data(days=days)
    
    await callback.message.edit_text(
        f"{_('vip.title')}\n\n{_('vip.confirm').format(days=days)}",
        reply_markup=build_vip_confirm_keyboard(listing_id, days, _),
    )
    await state.set_state(VIPStates.confirm_upgrade)

@router.callback_query(VIPCallback.filter(F.action == "confirm"), VIPStates.confirm_upgrade)
async def vip_confirm(
    callback: CallbackQuery,
    callback_data: VIPCallback,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Handle VIP upgrade confirmation."""
    await callback.answer()
    
    listing_id = callback_data.id
    days = callback_data.days
    
    if not db_session:
        await callback.message.edit_text(_("errors.general"))
        await state.clear()
        return
    
    try:
        from app.services.listing import ListingService
        
        listing_service = ListingService(db_session)
        upgraded_listing = await listing_service.upgrade_to_vip(
            UUID(listing_id),
            days=days,
        )
        
        if upgraded_listing and upgraded_listing.vip_expires_at:
            expires_str = upgraded_listing.vip_expires_at.strftime("%Y-%m-%d %H:%M")
            await callback.message.edit_text(
                _("vip.success").format(expires_at=expires_str),
                reply_markup=build_start_over_keyboard(_),
            )
        else:
            await callback.message.edit_text(
                _("errors.general"),
                reply_markup=build_start_over_keyboard(_),
            )
        
    except Exception as e:
        logger.error(f"Error upgrading to VIP: {e}")
        await callback.message.edit_text(
            _("errors.general"),
            reply_markup=build_start_over_keyboard(_),
        )
    
    await state.clear()

@router.callback_query(VIPCallback.filter(F.action == "back"), VIPStates.select_duration)
async def vip_back_to_listings(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Go back to listing selection."""
    await callback.answer()
    
    if not db_session or not user:
        await callback.message.edit_text(_("errors.general"))
        await state.clear()
        return
    
    try:
        result = await db_session.execute(
            select(Listing).where(
                Listing.user_id == user.id,
                Listing.status == ListingStatusEnum.ACTIVE,
            ).order_by(Listing.created_at.desc())
        )
        listings = result.scalars().all()
        
        listings_data = [
            {
                "id": str(listing.id),
                "price": float(listing.price),
                "rooms": listing.rooms,
                "area": float(listing.area),
                "is_vip": listing.is_vip,
            }
            for listing in listings
        ]
        
        await callback.message.edit_text(
            f"{_('vip.title')}\n\n{_('vip.select_listing')}",
            reply_markup=build_vip_listings_keyboard(listings_data, _),
        )
        await state.set_state(VIPStates.select_listing)
        
    except Exception as e:
        logger.error(f"Error going back to listings: {e}")
        await callback.message.edit_text(_("errors.general"))
        await state.clear()

@router.callback_query(VIPCallback.filter(F.action == "cancel"))
async def vip_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Cancel VIP upgrade flow."""
    await callback.answer()
    await state.clear()
    
    await callback.message.edit_text(
        _("vip.cancelled"),
        reply_markup=build_start_over_keyboard(_),
    )
