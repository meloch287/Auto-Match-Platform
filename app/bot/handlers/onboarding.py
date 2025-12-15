from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.builders import (
    build_language_keyboard,
    build_role_keyboard,
    build_market_type_keyboard,
    build_categories_keyboard,
)
from app.bot.keyboards.callbacks import LanguageCallback, RoleCallback
from app.bot.states import OnboardingStates, ListingStates, RequirementStates

router = Router(name="onboarding")

@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    user: Any,
    user_created: bool,
    _: Any,
) -> None:
    """
    Handle /start command.
    
    ALWAYS shows language selection first, regardless of new/returning user.
    """
    await state.clear()
    
    await message.answer(
        _("welcome.new_user"),
        reply_markup=build_language_keyboard(),
    )
    await state.set_state(OnboardingStates.language_select)

@router.callback_query(LanguageCallback.filter())
async def process_language_selection(
    callback: CallbackQuery,
    callback_data: LanguageCallback,
    state: FSMContext,
    user: Any,
    db_session: Any,
) -> None:
    """
    Handle language selection callback.
    
    Stores language preference and proceeds to role selection.
    """
    from app.bot.middlewares.i18n import get_translator
    from app.services.user import UserService
    from app.models.user import LanguageEnum
    
    lang_map = {
        "az": LanguageEnum.AZ,
        "ru": LanguageEnum.RU,
        "en": LanguageEnum.EN,
    }
    
    language = lang_map.get(callback_data.code, LanguageEnum.AZ)
    
    user_service = UserService(db_session)
    await user_service.update_language(user.telegram_id, language)
    
    _ = get_translator(callback_data.code)
    
    await callback.answer()
    
    await callback.message.edit_text(
        _("roles.select"),
        reply_markup=build_role_keyboard(_),
    )
    await state.set_state(OnboardingStates.role_select)

@router.message(Command("language"))
async def cmd_language(
    message: Message,
    state: FSMContext,
    _: Any,
) -> None:
    """Handle /language command to change language."""
    await message.answer(
        _("welcome.new_user"),
        reply_markup=build_language_keyboard(),
    )
    await state.set_state(OnboardingStates.language_select)

@router.callback_query(RoleCallback.filter())
async def process_role_selection(
    callback: CallbackQuery,
    callback_data: RoleCallback,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: Any,
) -> None:
    """
    Handle role selection callback.
    
    After role selection, shows market type selection (Real Estate / Auto).
    """
    role = callback_data.role
    
    await callback.answer()
    await state.update_data(current_role=role)
    
    # Show market type selection
    await callback.message.edit_text(
        _("market.select"),
        reply_markup=build_market_type_keyboard(_),
    )
    await state.set_state(OnboardingStates.market_type_select)


@router.callback_query(F.data.startswith("market:"), OnboardingStates.market_type_select)
async def process_market_type_selection(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: Any,
) -> None:
    """
    Handle market type selection callback.
    
    Real Estate -> continues to category selection
    Auto -> shows "in development" message
    """
    from app.services.user import UserService
    
    market_type = callback.data.split(":")[1]
    
    if market_type == "back":
        # Go back to role selection
        await callback.answer()
        await callback.message.edit_text(
            _("roles.select"),
            reply_markup=build_role_keyboard(_),
        )
        await state.set_state(OnboardingStates.role_select)
        return
    
    if market_type == "auto":
        # Show "in development" message
        await callback.answer(_("market.auto_in_development"), show_alert=True)
        return
    
    # Real estate flow - check limits and continue
    data = await state.get_data()
    role = data.get("current_role", "buyer")
    
    user_service = UserService(db_session)
    
    if role == "buyer":
        can_create, used, max_count = await user_service.can_create_free_requirement(user)
        if not can_create:
            await callback.answer(
                _("limits.requirements_exceeded").format(used=used, max=max_count),
                show_alert=True
            )
            return
        
        await callback.answer()
        await state.update_data(flow="requirement", market_type="real_estate")
        
        # Show remaining attempts
        remaining = max_count - used if max_count > 0 else "∞"
        await callback.message.edit_text(
            f"🔍 {_('roles.buyer_desc')}\n\n"
            f"📊 {_('limits.requirements_remaining').format(remaining=remaining)}\n\n"
            f"{_('categories.select')}",
            reply_markup=build_categories_keyboard(_),
        )
        await state.set_state(RequirementStates.category)
    else:
        can_create, used, max_count = await user_service.can_create_free_listing(user)
        if not can_create:
            await callback.answer(
                _("limits.listings_exceeded").format(used=used, max=max_count),
                show_alert=True
            )
            return
        
        await callback.answer()
        await state.update_data(flow="listing", market_type="real_estate")
        
        # Show remaining attempts
        remaining = max_count - used if max_count > 0 else "∞"
        await callback.message.edit_text(
            f"🏷️ {_('roles.seller_desc')}\n\n"
            f"📊 {_('limits.listings_remaining').format(remaining=remaining)}\n\n"
            f"{_('categories.select')}",
            reply_markup=build_categories_keyboard(_),
        )
        await state.set_state(ListingStates.category)

@router.message(Command("role"))
async def cmd_role(
    message: Message,
    state: FSMContext,
    _: Any,
) -> None:
    """Handle /role command to change role."""
    await message.answer(
        _("roles.select"),
        reply_markup=build_role_keyboard(_),
    )
    await state.set_state(OnboardingStates.role_select)
