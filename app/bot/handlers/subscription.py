import logging
from typing import Any, Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.builders import (
    build_subscription_status_keyboard,
    build_subscription_plans_keyboard,
    build_subscription_confirm_keyboard,
    build_start_over_keyboard,
    build_profile_keyboard,
)
from app.bot.keyboards.callbacks import SubscriptionCallback
from app.bot.states import SubscriptionStates
from app.services.subscription import SubscriptionService, get_subscription_plan

logger = logging.getLogger(__name__)

router = Router(name="subscription")

@router.message(Command("subscription"))
async def cmd_subscription(
    message: Message,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """
    Handle /subscription command - show premium choice screen.
    
    Requirements: 7.2
    """
    await state.clear()
    
    if not db_session or not user:
        await message.answer(_("errors.general"))
        return
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.button(text=_('subscription.subscription_option'), callback_data="subscription:show_plans")
    builder.button(text=_('subscription.packages_option'), callback_data="subscription:show_packages")
    builder.adjust(2)
    
    await message.answer(
        f"{_('subscription.title')}\n\n{_('subscription.choose_type')}",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(SubscriptionStates.viewing_status)

@router.callback_query(F.data == "subscription:from_profile")
async def subscription_from_profile(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Show choice between subscription and packages from profile."""
    await callback.answer()
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.button(text=_('subscription.subscription_option'), callback_data="subscription:show_plans")
    builder.button(text=_('subscription.packages_option'), callback_data="subscription:show_packages")
    builder.button(text=_('buttons.back_simple'), callback_data=SubscriptionCallback(action="back"))
    builder.adjust(2, 1)
    
    await callback.message.edit_text(
        f"{_('subscription.title')}\n\n{_('subscription.choose_type')}",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(SubscriptionStates.viewing_status)

@router.callback_query(F.data == "subscription:show_plans")
async def subscription_show_plans(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Show subscription plans."""
    await callback.answer()
    
    if not db_session:
        await callback.message.edit_text(_("errors.general"))
        return
    
    try:
        subscription_service = SubscriptionService(db_session)
        plans = await subscription_service.get_plans()
        
        lang = user.language.value if user and hasattr(user, 'language') else "en"
        
        plans_data = [
            {
                "id": plan.id,
                "name": plan.get_name(lang),
                "price": float(plan.price),
                "duration_days": plan.duration_days,
            }
            for plan in plans
        ]
        
        await callback.message.edit_text(
            f"{_('subscription.title')}\n\n{_('subscription.select_plan')}",
            reply_markup=build_subscription_plans_keyboard(plans_data, _, lang),
        )
        await state.set_state(SubscriptionStates.select_plan)
        
    except Exception as e:
        logger.error(f"Error viewing subscription plans: {e}")
        await callback.message.edit_text(_("errors.general"))

@router.callback_query(F.data == "subscription:show_packages")
async def subscription_show_packages(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Show extra packages (additional listings/requirements)."""
    await callback.answer()
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{_('subscription.extra_listings')} - 9.99 AZN", callback_data="package:listings")
    builder.button(text=f"{_('subscription.extra_requirements')} - 4.99 AZN", callback_data="package:requirements")
    builder.button(text=_('buttons.back_simple'), callback_data="subscription:back_to_choice")
    builder.adjust(1)
    
    await callback.message.edit_text(
        f"{_('subscription.packages_title')}\n\n{_('subscription.select_plan')}",
        reply_markup=builder.as_markup(),
    )

@router.callback_query(F.data == "subscription:back_to_choice")
async def subscription_back_to_choice(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Go back to subscription/packages choice screen."""
    await callback.answer()
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.button(text=_('subscription.subscription_option'), callback_data="subscription:show_plans")
    builder.button(text=_('subscription.packages_option'), callback_data="subscription:show_packages")
    builder.button(text=_('buttons.back_simple'), callback_data=SubscriptionCallback(action="back"))
    builder.adjust(2, 1)
    
    await callback.message.edit_text(
        f"{_('subscription.title')}\n\n{_('subscription.choose_type')}",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(SubscriptionStates.viewing_status)

@router.callback_query(F.data == "subscription:plans")
async def subscription_from_settings(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Show subscription plans from settings menu."""
    await callback.answer()
    
    if not db_session:
        await callback.message.edit_text(_("errors.general"))
        return
    
    try:
        subscription_service = SubscriptionService(db_session)
        plans = await subscription_service.get_plans()
        
        lang = user.language.value if user and hasattr(user, 'language') else "en"
        
        plans_data = [
            {
                "id": plan.id,
                "name": plan.get_name(lang),
                "price": float(plan.price),
                "duration_days": plan.duration_days,
            }
            for plan in plans
        ]
        
        await callback.message.edit_text(
            f"{_('subscription.title')}\n\n{_('subscription.select_plan')}",
            reply_markup=build_subscription_plans_keyboard(plans_data, _, lang),
        )
        await state.set_state(SubscriptionStates.select_plan)
        
    except Exception as e:
        logger.error(f"Error viewing subscription plans: {e}")
        await callback.message.edit_text(_("errors.general"))

@router.callback_query(SubscriptionCallback.filter(F.action == "plans"))
async def subscription_view_plans(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Show available subscription plans."""
    await callback.answer()
    
    if not db_session:
        await callback.message.edit_text(_("errors.general"))
        return
    
    try:
        subscription_service = SubscriptionService(db_session)
        plans = await subscription_service.get_plans()
        
        lang = user.language.value if user and hasattr(user, 'language') else "en"
        
        plans_data = [
            {
                "id": plan.id,
                "name": plan.get_name(lang),
                "price": float(plan.price),
                "duration_days": plan.duration_days,
            }
            for plan in plans
        ]
        
        await callback.message.edit_text(
            f"{_('subscription.title')}\n\n{_('subscription.select_plan')}",
            reply_markup=build_subscription_plans_keyboard(plans_data, _, lang),
        )
        await state.set_state(SubscriptionStates.select_plan)
        
    except Exception as e:
        logger.error(f"Error viewing subscription plans: {e}")
        await callback.message.edit_text(_("errors.general"))

@router.callback_query(SubscriptionCallback.filter(F.action == "select"), SubscriptionStates.select_plan)
async def subscription_plan_selected(
    callback: CallbackQuery,
    callback_data: SubscriptionCallback,
    state: FSMContext,
    _: Any,
    user: Any,
) -> None:
    """Handle subscription plan selection."""
    await callback.answer()
    
    plan_id = callback_data.plan_id
    plan = get_subscription_plan(plan_id)
    
    if not plan:
        await callback.message.edit_text(
            _("subscription.invalid_plan"),
            reply_markup=build_start_over_keyboard(_),
        )
        await state.clear()
        return
    
    lang = user.language.value if user and hasattr(user, 'language') else "en"
    
    await state.update_data(plan_id=plan_id)
    
    confirm_text = (
        f"{_('subscription.title')}\n\n"
        f"📦 {_('subscription.plan')}: {plan.get_name(lang)}\n"
        f"💰 {_('subscription.price')}: {plan.price} AZN\n"
        f"📅 {_('subscription.duration')}: {plan.duration_days} {_('subscription.days')}\n\n"
        f"{_('subscription.confirm_purchase')}"
    )
    
    await callback.message.edit_text(
        confirm_text,
        reply_markup=build_subscription_confirm_keyboard(plan_id, _),
    )
    await state.set_state(SubscriptionStates.confirm_purchase)

@router.callback_query(SubscriptionCallback.filter(F.action == "confirm"), SubscriptionStates.confirm_purchase)
async def subscription_confirm(
    callback: CallbackQuery,
    callback_data: SubscriptionCallback,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Handle subscription purchase confirmation - create Payriff payment."""
    await callback.answer()
    
    plan_id = callback_data.plan_id
    plan = get_subscription_plan(plan_id)
    
    if not plan:
        await callback.message.edit_text(_("errors.general"))
        await state.clear()
        return
    
    if not db_session:
        await callback.message.edit_text(_("errors.general"))
        await state.clear()
        return
    
    lang = user.language.value if user and hasattr(user, 'language') else "en"
    
    # Create Payriff payment
    from app.services.payriff import get_payriff_service
    from app.models.payment import Payment, PaymentStatusEnum, PaymentTypeEnum
    
    payriff = get_payriff_service()
    
    try:
        order = await payriff.create_order(
            amount=plan.price,
            currency="AZN",
            description=f"Subscription: {plan.name_en}",
            language=lang.upper(),
        )
        
        if order and order.payment_url:
            # Save payment to database
            payment = Payment(
                user_id=user.id,
                amount=plan.price,
                currency="AZN",
                payment_type=PaymentTypeEnum.SUBSCRIPTION,
                plan_id=plan_id,
                payriff_order_id=order.order_id,
                payriff_session_id=order.session_id,
                payment_url=order.payment_url,
                status=PaymentStatusEnum.PENDING,
            )
            db_session.add(payment)
            await db_session.commit()
            
            # Show payment link
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            builder.button(text="💳 Оплатить / Pay", url=order.payment_url)
            builder.button(text=_('buttons.back_simple'), callback_data=SubscriptionCallback(action="back"))
            builder.adjust(1)
            
            await callback.message.edit_text(
                f"💳 {_('subscription.payment_pending')}\n\n"
                f"📦 {_('subscription.plan')}: {plan.get_name(lang)}\n"
                f"💰 {_('subscription.price')}: {plan.price} AZN\n\n"
                f"👆 Нажмите кнопку для оплаты",
                reply_markup=builder.as_markup(),
            )
        else:
            # Fallback to manual payment
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            builder.button(text=_('buttons.back_simple'), callback_data=SubscriptionCallback(action="back"))
            
            await callback.message.edit_text(
                f"💳 {_('subscription.payment_pending')}\n\n"
                f"📦 {_('subscription.plan')}: {plan.get_name(lang)}\n"
                f"💰 {_('subscription.price')}: {plan.price} AZN\n\n"
                f"ℹ️ {_('subscription.payment_instructions')}",
                reply_markup=builder.as_markup(),
            )
    except Exception as e:
        logger.error(f"Payment creation error: {e}")
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text=_('buttons.back_simple'), callback_data=SubscriptionCallback(action="back"))
        
        await callback.message.edit_text(
            f"❌ Ошибка создания платежа. Попробуйте позже.\n\n"
            f"ℹ️ {_('subscription.payment_instructions')}",
            reply_markup=builder.as_markup(),
        )
    finally:
        await payriff.close()
    
    await state.clear()

@router.callback_query(SubscriptionCallback.filter(F.action == "back"))
async def subscription_back(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Go back to profile from subscription plans."""
    await callback.answer()
    
    if not db_session or not user:
        await callback.message.edit_text(_("errors.general"))
        await state.clear()
        return
    
    try:
        from app.services.user import UserService
        from app.models.user import SubscriptionTypeEnum
        from sqlalchemy import select
        from app.models.listing import Listing, ListingStatusEnum
        
        user_service = UserService(db_session)
        limits_info = await user_service.get_free_limits_info(user)
        
        # Build profile text
        text = f"<b>{_('profile.title')}</b>\n\n"
        
        is_premium = user.subscription_type != SubscriptionTypeEnum.FREE
        if is_premium:
            expires_str = user.subscription_expires_at.strftime("%Y-%m-%d") if user.subscription_expires_at else "-"
            text += f"✅ {_('subscription.status')}: <b>{_('subscription.premium')}</b>\n"
            text += f"📅 {_('subscription.expires')}: {expires_str}\n\n"
            text += f"🎁 {_('limits.unlimited')}\n\n"
        else:
            text += f"📋 {_('subscription.status')}: {_('subscription.free')}\n\n"
            text += f"📊 <b>{_('limits.title')}</b>\n"
            listings_used = limits_info["listings"]["used"]
            listings_max = limits_info["listings"]["max"]
            listings_remaining = limits_info["listings"]["remaining"]
            if listings_max == -1:
                text += f"🏷️ {_('limits.listings_label')}: {listings_used}/∞\n"
            else:
                text += f"🏷️ {_('limits.listings_label')}: {listings_used}/{listings_max} "
                text += f"({_('limits.remaining')}: {listings_remaining})\n"
            req_used = limits_info["requirements"]["used"]
            req_max = limits_info["requirements"]["max"]
            req_remaining = limits_info["requirements"]["remaining"]
            if req_max == -1:
                text += f"🔍 {_('limits.requirements_label')}: {req_used}/∞\n\n"
            else:
                text += f"🔍 {_('limits.requirements_label')}: {req_used}/{req_max} "
                text += f"({_('limits.remaining')}: {req_remaining})\n\n"
            text += f"💡 {_('subscription.upgrade_prompt')}\n\n"
        
        # Check for active listings
        result = await db_session.execute(
            select(Listing).where(
                Listing.user_id == user.id,
                Listing.status == ListingStatusEnum.ACTIVE,
            )
        )
        listings = result.scalars().all()
        
        if not listings:
            text += f"ℹ️ {_('vip.no_listings')}"
        
        await callback.message.edit_text(
            text,
            reply_markup=build_profile_keyboard(_, is_premium=is_premium),
            parse_mode="HTML",
        )
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error going back to profile: {e}")
        await callback.message.edit_text(_("errors.general"))
        await state.clear()

@router.callback_query(SubscriptionCallback.filter(F.action == "back_to_profile"))
async def subscription_back_to_profile(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Go back to profile/main menu."""
    await callback.answer()
    await state.clear()
    
    # Just delete the message and let user use /profile or other commands
    await callback.message.delete()

@router.callback_query(SubscriptionCallback.filter(F.action == "cancel"))
async def subscription_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Cancel subscription flow - go back to choice screen."""
    await callback.answer()
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.button(text=_('subscription.subscription_option'), callback_data="subscription:show_plans")
    builder.button(text=_('subscription.packages_option'), callback_data="subscription:show_packages")
    builder.button(text=_('buttons.back_simple'), callback_data=SubscriptionCallback(action="back"))
    builder.adjust(2, 1)
    
    await callback.message.edit_text(
        f"{_('subscription.title')}\n\n{_('subscription.choose_type')}",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(SubscriptionStates.viewing_status)


@router.callback_query(F.data == "package:listings")
async def package_listings_selected(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    user: Any,
) -> None:
    """Handle extra listings package selection."""
    await callback.answer()
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.button(text=f"✅ {_('buttons.confirm')}", callback_data="package:confirm_listings")
    builder.button(text=f"❌ {_('buttons.cancel')}", callback_data="subscription:show_packages")
    builder.adjust(2)
    
    await callback.message.edit_text(
        f"📦 {_('subscription.extra_listings')}\n\n"
        f"💰 {_('subscription.price')}: 9.99 AZN\n\n"
        f"{_('subscription.confirm_purchase')}",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data == "package:requirements")
async def package_requirements_selected(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    user: Any,
) -> None:
    """Handle extra requirements package selection."""
    await callback.answer()
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.button(text=f"✅ {_('buttons.confirm')}", callback_data="package:confirm_requirements")
    builder.button(text=f"❌ {_('buttons.cancel')}", callback_data="subscription:show_packages")
    builder.adjust(2)
    
    await callback.message.edit_text(
        f"📦 {_('subscription.extra_requirements')}\n\n"
        f"💰 {_('subscription.price')}: 4.99 AZN\n\n"
        f"{_('subscription.confirm_purchase')}",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data == "package:confirm_listings")
async def package_confirm_listings(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Confirm extra listings package purchase - create Payriff payment."""
    await callback.answer()
    
    if not db_session:
        await callback.message.edit_text(_("errors.general"))
        return
    
    from decimal import Decimal
    from app.services.payriff import get_payriff_service
    from app.models.payment import Payment, PaymentStatusEnum, PaymentTypeEnum
    
    lang = user.language.value if user and hasattr(user, 'language') else "en"
    payriff = get_payriff_service()
    
    try:
        order = await payriff.create_order(
            amount=Decimal("9.99"),
            currency="AZN",
            description="Extra listings package (+5)",
            language=lang.upper(),
        )
        
        if order and order.payment_url:
            payment = Payment(
                user_id=user.id,
                amount=Decimal("9.99"),
                currency="AZN",
                payment_type=PaymentTypeEnum.PACKAGE_LISTINGS,
                payriff_order_id=order.order_id,
                payriff_session_id=order.session_id,
                payment_url=order.payment_url,
                status=PaymentStatusEnum.PENDING,
            )
            db_session.add(payment)
            await db_session.commit()
            
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            builder.button(text="💳 Оплатить / Pay", url=order.payment_url)
            builder.button(text=_('buttons.back_simple'), callback_data="subscription:show_packages")
            builder.adjust(1)
            
            await callback.message.edit_text(
                f"💳 {_('subscription.payment_pending')}\n\n"
                f"📦 {_('subscription.extra_listings')}\n"
                f"💰 9.99 AZN\n\n"
                f"👆 Нажмите кнопку для оплаты",
                reply_markup=builder.as_markup(),
            )
        else:
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            builder.button(text=_('buttons.back_simple'), callback_data="subscription:show_packages")
            
            await callback.message.edit_text(
                f"💳 {_('subscription.payment_pending')}\n\n"
                f"📦 {_('subscription.extra_listings')}\n"
                f"💰 9.99 AZN\n\n"
                f"ℹ️ {_('subscription.payment_instructions')}",
                reply_markup=builder.as_markup(),
            )
    except Exception as e:
        logger.error(f"Payment creation error: {e}")
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text=_('buttons.back_simple'), callback_data="subscription:show_packages")
        await callback.message.edit_text(_("errors.general"), reply_markup=builder.as_markup())
    finally:
        await payriff.close()
    
    await state.clear()


@router.callback_query(F.data == "package:confirm_requirements")
async def package_confirm_requirements(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Confirm extra requirements package purchase - create Payriff payment."""
    await callback.answer()
    
    if not db_session:
        await callback.message.edit_text(_("errors.general"))
        return
    
    from decimal import Decimal
    from app.services.payriff import get_payriff_service
    from app.models.payment import Payment, PaymentStatusEnum, PaymentTypeEnum
    
    lang = user.language.value if user and hasattr(user, 'language') else "en"
    payriff = get_payriff_service()
    
    try:
        order = await payriff.create_order(
            amount=Decimal("4.99"),
            currency="AZN",
            description="Extra requirements package (+10)",
            language=lang.upper(),
        )
        
        if order and order.payment_url:
            payment = Payment(
                user_id=user.id,
                amount=Decimal("4.99"),
                currency="AZN",
                payment_type=PaymentTypeEnum.PACKAGE_REQUIREMENTS,
                payriff_order_id=order.order_id,
                payriff_session_id=order.session_id,
                payment_url=order.payment_url,
                status=PaymentStatusEnum.PENDING,
            )
            db_session.add(payment)
            await db_session.commit()
            
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            builder.button(text="💳 Оплатить / Pay", url=order.payment_url)
            builder.button(text=_('buttons.back_simple'), callback_data="subscription:show_packages")
            builder.adjust(1)
            
            await callback.message.edit_text(
                f"💳 {_('subscription.payment_pending')}\n\n"
                f"📦 {_('subscription.extra_requirements')}\n"
                f"💰 4.99 AZN\n\n"
                f"👆 Нажмите кнопку для оплаты",
                reply_markup=builder.as_markup(),
            )
        else:
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            builder.button(text=_('buttons.back_simple'), callback_data="subscription:show_packages")
            
            await callback.message.edit_text(
                f"💳 {_('subscription.payment_pending')}\n\n"
                f"📦 {_('subscription.extra_requirements')}\n"
                f"💰 4.99 AZN\n\n"
                f"ℹ️ {_('subscription.payment_instructions')}",
                reply_markup=builder.as_markup(),
            )
    except Exception as e:
        logger.error(f"Payment creation error: {e}")
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text=_('buttons.back_simple'), callback_data="subscription:show_packages")
        await callback.message.edit_text(_("errors.general"), reply_markup=builder.as_markup())
    finally:
        await payriff.close()
    
    await state.clear()
