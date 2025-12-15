"""Handlers for auto marketplace."""
import logging
import uuid
from decimal import Decimal
from typing import Any, Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.states import (
    AutoListingStates,
    AutoRequirementStates,
    MatchBrowseStates,
    BotChatStates,
)
from app.models.auto import AutoStatusEnum, FuelTypeEnum, TransmissionEnum, BodyTypeEnum
from app.services.auto import (
    AutoListingService,
    AutoRequirementService,
    AutoMatchService,
    AutoChatService,
)

logger = logging.getLogger(__name__)
router = Router(name="auto")


# ============ KEYBOARDS ============

def build_fuel_type_keyboard(_: Any) -> Any:
    """Build fuel type selection keyboard."""
    builder = InlineKeyboardBuilder()
    options = [
        ("petrol", "⛽", "auto.fuel.petrol"),
        ("diesel", "🛢️", "auto.fuel.diesel"),
        ("gas", "💨", "auto.fuel.gas"),
        ("hybrid", "🔋", "auto.fuel.hybrid"),
        ("electric", "⚡", "auto.fuel.electric"),
    ]
    for value, icon, key in options:
        builder.button(text=f"{icon} {_(key)}", callback_data=f"auto_fuel:{value}")
    builder.adjust(2)
    builder.row()
    builder.button(text=_("buttons.back"), callback_data="auto:back")
    return builder.as_markup()


def build_transmission_keyboard(_: Any) -> Any:
    """Build transmission selection keyboard."""
    builder = InlineKeyboardBuilder()
    options = [
        ("manual", "🔧", "auto.transmission.manual"),
        ("automatic", "🅰️", "auto.transmission.automatic"),
        ("robot", "🤖", "auto.transmission.robot"),
        ("cvt", "♾️", "auto.transmission.cvt"),
    ]
    for value, icon, key in options:
        builder.button(text=f"{icon} {_(key)}", callback_data=f"auto_trans:{value}")
    builder.adjust(2)
    builder.row()
    builder.button(text=_("buttons.back"), callback_data="auto:back")
    return builder.as_markup()


def build_body_type_keyboard(_: Any) -> Any:
    """Build body type selection keyboard."""
    builder = InlineKeyboardBuilder()
    options = [
        ("sedan", "🚗", "auto.body.sedan"),
        ("hatchback", "🚙", "auto.body.hatchback"),
        ("suv", "🚜", "auto.body.suv"),
        ("crossover", "🚐", "auto.body.crossover"),
        ("wagon", "🚃", "auto.body.wagon"),
        ("coupe", "🏎️", "auto.body.coupe"),
    ]
    for value, icon, key in options:
        builder.button(text=f"{icon} {_(key)}", callback_data=f"auto_body:{value}")
    builder.adjust(2)
    builder.row()
    builder.button(text=_("buttons.back"), callback_data="auto:back")
    return builder.as_markup()


def build_skip_keyboard(_: Any) -> Any:
    """Build skip keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text=f"⏭️ {_('buttons.skip')}", callback_data="auto:skip")
    builder.button(text=_("buttons.back"), callback_data="auto:back")
    builder.adjust(1)
    return builder.as_markup()


def build_confirm_keyboard(_: Any) -> Any:
    """Build confirmation keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text=f"✅ {_('buttons.confirm')}", callback_data="auto:confirm")
    builder.button(text=f"❌ {_('buttons.cancel')}", callback_data="auto:cancel")
    builder.adjust(2)
    return builder.as_markup()


def build_match_browse_keyboard(
    match_id: str,
    current: int,
    total: int,
    _: Any,
) -> Any:
    """Build match browsing keyboard with navigation."""
    builder = InlineKeyboardBuilder()
    # Navigation row
    builder.button(text="⬅️", callback_data=f"auto_match:prev:{match_id}")
    builder.button(text=f"📩 {_('auto.respond')}", callback_data=f"auto_match:respond:{match_id}")
    builder.button(text="➡️", callback_data=f"auto_match:next:{match_id}")
    builder.adjust(3)
    # Counter
    builder.row()
    builder.button(text=f"{current}/{total}", callback_data="auto_match:counter")
    # Back to profile
    builder.row()
    builder.button(text=_("buttons.back_simple"), callback_data="auto:back_to_profile")
    return builder.as_markup()


def build_respond_choice_keyboard(match_id: str, _: Any) -> Any:
    """Build response choice keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"📞 {_('auto.show_contacts')}",
        callback_data=f"auto_respond:contacts:{match_id}"
    )
    builder.button(
        text=f"💬 {_('auto.write_via_bot')}",
        callback_data=f"auto_respond:chat:{match_id}"
    )
    builder.adjust(1)
    builder.row()
    builder.button(text=_("buttons.back_simple"), callback_data=f"auto_respond:back:{match_id}")
    return builder.as_markup()


def build_chat_keyboard(chat_id: str, _: Any, can_reveal: bool = True) -> Any:
    """Build chat actions keyboard."""
    builder = InlineKeyboardBuilder()
    if can_reveal:
        builder.button(text=f"🔓 {_('chat.reveal')}", callback_data=f"auto_chat:reveal:{chat_id}")
    builder.button(text=f"🚪 {_('chat.close')}", callback_data=f"auto_chat:close:{chat_id}")
    builder.adjust(2)
    builder.row()
    builder.button(text=_("buttons.back_simple"), callback_data="auto:back_to_profile")
    return builder.as_markup()


def build_rental_class_keyboard(_: Any) -> Any:
    """Build rental class selection keyboard."""
    builder = InlineKeyboardBuilder()
    options = [
        ("economy", "💵", "auto.rental_class.economy"),
        ("business", "💼", "auto.rental_class.business"),
        ("premium", "👑", "auto.rental_class.premium"),
        ("crossover", "🚙", "auto.rental_class.crossover"),
        ("suv", "🚜", "auto.rental_class.suv"),
        ("minivan", "🚐", "auto.rental_class.minivan"),
    ]
    for value, icon, key in options:
        builder.button(text=f"{icon} {_(key)}", callback_data=f"auto_rental_class:{value}")
    builder.adjust(2)
    builder.row()
    builder.button(text=_("buttons.back"), callback_data="auto:back")
    return builder.as_markup()


# ============ AUTO LISTING HANDLERS (SELLER) ============

@router.message(AutoListingStates.brand)
async def process_auto_brand(
    message: Message,
    state: FSMContext,
    _: Any,
) -> None:
    """Process auto brand input."""
    brand = message.text.strip()
    if len(brand) < 2 or len(brand) > 50:
        await message.answer(_("errors.invalid_input"))
        return
    
    await state.update_data(brand=brand)
    await message.answer(_("auto.enter_model"))
    await state.set_state(AutoListingStates.model)


@router.message(AutoListingStates.model)
async def process_auto_model(
    message: Message,
    state: FSMContext,
    _: Any,
) -> None:
    """Process auto model input."""
    model = message.text.strip()
    if len(model) < 1 or len(model) > 50:
        await message.answer(_("errors.invalid_input"))
        return
    
    await state.update_data(model=model)
    await message.answer(_("auto.enter_year"))
    await state.set_state(AutoListingStates.year)


@router.message(AutoListingStates.year)
async def process_auto_year(
    message: Message,
    state: FSMContext,
    _: Any,
) -> None:
    """Process auto year input."""
    try:
        year = int(message.text.strip())
        if year < 1950 or year > 2025:
            raise ValueError()
    except ValueError:
        await message.answer(_("errors.invalid_input"))
        return
    
    await state.update_data(year=year)
    
    data = await state.get_data()
    deal_type = data.get("deal_type", "sale")
    
    if deal_type == "rent":
        # For rental, skip mileage and go to rental class
        await message.answer(
            _("auto.select_rental_class"),
            reply_markup=build_rental_class_keyboard(_),
        )
        await state.set_state(AutoListingStates.body_type)  # reuse for rental class
    else:
        await message.answer(_("auto.enter_mileage"))
        await state.set_state(AutoListingStates.mileage)


@router.message(AutoListingStates.mileage)
async def process_auto_mileage(
    message: Message,
    state: FSMContext,
    _: Any,
) -> None:
    """Process auto mileage input."""
    try:
        mileage = int(message.text.strip().replace(" ", "").replace(",", ""))
        if mileage < 0 or mileage > 2000000:
            raise ValueError()
    except ValueError:
        await message.answer(_("errors.invalid_input"))
        return
    
    await state.update_data(mileage=mileage)
    await message.answer(
        _("auto.select_transmission"),
        reply_markup=build_transmission_keyboard(_),
    )
    await state.set_state(AutoListingStates.transmission)


@router.callback_query(F.data.startswith("auto_trans:"), AutoListingStates.transmission)
async def process_auto_transmission(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Process transmission selection."""
    transmission = callback.data.split(":")[1]
    await callback.answer()
    await state.update_data(transmission=transmission)
    
    await callback.message.edit_text(
        _("auto.select_fuel"),
        reply_markup=build_fuel_type_keyboard(_),
    )
    await state.set_state(AutoListingStates.fuel_type)


@router.callback_query(F.data.startswith("auto_fuel:"), AutoListingStates.fuel_type)
async def process_auto_fuel(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Process fuel type selection."""
    fuel_type = callback.data.split(":")[1]
    await callback.answer()
    await state.update_data(fuel_type=fuel_type)
    
    await callback.message.edit_text(_("auto.enter_price"))
    await state.set_state(AutoListingStates.price)


@router.callback_query(F.data.startswith("auto_rental_class:"))
async def process_rental_class(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Process rental class selection."""
    rental_class = callback.data.split(":")[1]
    await callback.answer()
    await state.update_data(rental_class=rental_class)
    
    await callback.message.edit_text(_("auto.enter_price_per_day"))
    await state.set_state(AutoListingStates.price)


@router.message(AutoListingStates.price)
async def process_auto_price(
    message: Message,
    state: FSMContext,
    _: Any,
) -> None:
    """Process auto price input."""
    try:
        price = Decimal(message.text.strip().replace(" ", "").replace(",", ""))
        if price <= 0:
            raise ValueError()
    except (ValueError, Exception):
        await message.answer(_("form.price.invalid"))
        return
    
    await state.update_data(price=str(price))
    await message.answer(_("auto.enter_city"))
    await state.set_state(AutoListingStates.city)


@router.message(AutoListingStates.city)
async def process_auto_city(
    message: Message,
    state: FSMContext,
    _: Any,
) -> None:
    """Process city input."""
    city = message.text.strip()
    if len(city) < 2 or len(city) > 100:
        await message.answer(_("errors.invalid_input"))
        return
    
    await state.update_data(city=city)
    await message.answer(
        _("auto.enter_description"),
        reply_markup=build_skip_keyboard(_),
    )
    await state.set_state(AutoListingStates.description)


@router.message(AutoListingStates.description)
async def process_auto_description(
    message: Message,
    state: FSMContext,
    _: Any,
) -> None:
    """Process description input."""
    description = message.text.strip()[:1000] if message.text else None
    await state.update_data(description=description)
    
    # Show confirmation
    await _show_auto_listing_confirmation(message, state, _)


@router.callback_query(F.data == "auto:skip", AutoListingStates.description)
async def skip_auto_description(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Skip description."""
    await callback.answer()
    await state.update_data(description=None)
    await _show_auto_listing_confirmation(callback.message, state, _, edit=True)


async def _show_auto_listing_confirmation(
    message: Message,
    state: FSMContext,
    _: Any,
    edit: bool = False,
) -> None:
    """Show auto listing confirmation."""
    data = await state.get_data()
    
    deal_type = data.get("deal_type", "sale")
    brand = data.get("brand", "")
    model = data.get("model", "")
    year = data.get("year", "")
    price = data.get("price", "0")
    city = data.get("city", "")
    
    if deal_type == "rent":
        rental_class = data.get("rental_class", "")
        text = (
            f"🚗 <b>{_('auto.rent')}</b>\n\n"
            f"<b>{_('auto.brand')}:</b> {brand}\n"
            f"<b>{_('auto.model')}:</b> {model}\n"
            f"<b>{_('auto.year')}:</b> {year}\n"
            f"<b>{_('auto.rental_class.'+rental_class)}:</b> {_(f'auto.rental_class.{rental_class}')}\n"
            f"<b>💰 {_('auto.price')}:</b> {price} AZN/день\n"
            f"<b>🏙️:</b> {city}\n\n"
            f"{_('buttons.confirm')}?"
        )
    else:
        mileage = data.get("mileage", 0)
        transmission = data.get("transmission", "")
        fuel_type = data.get("fuel_type", "")
        text = (
            f"🚗 <b>{_('auto.sale')}</b>\n\n"
            f"<b>{_('auto.brand')}:</b> {brand}\n"
            f"<b>{_('auto.model')}:</b> {model}\n"
            f"<b>{_('auto.year')}:</b> {year}\n"
            f"<b>{_('auto.mileage')}:</b> {mileage:,} км\n"
            f"<b>⚙️:</b> {_(f'auto.transmission.{transmission}')}\n"
            f"<b>⛽:</b> {_(f'auto.fuel.{fuel_type}')}\n"
            f"<b>💰 {_('auto.price')}:</b> {price} AZN\n"
            f"<b>🏙️:</b> {city}\n\n"
            f"{_('buttons.confirm')}?"
        )
    
    if edit:
        await message.edit_text(text, reply_markup=build_confirm_keyboard(_), parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=build_confirm_keyboard(_), parse_mode="HTML")
    
    await state.set_state(AutoListingStates.confirmation)


@router.callback_query(F.data == "auto:confirm", AutoListingStates.confirmation)
async def confirm_auto_listing(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: AsyncSession,
) -> None:
    """Confirm and create auto listing."""
    await callback.answer()
    
    data = await state.get_data()
    deal_type = data.get("deal_type", "sale")
    
    service = AutoListingService(db_session)
    
    listing = await service.create_listing(
        user_id=user.id,
        brand=data.get("brand"),
        model=data.get("model"),
        year=data.get("year"),
        mileage=data.get("mileage") if deal_type == "sale" else None,
        fuel_type=data.get("fuel_type") if deal_type == "sale" else None,
        transmission=data.get("transmission") if deal_type == "sale" else None,
        body_type=None,
        price=Decimal(data.get("price", "0")),
        city=data.get("city"),
        description=data.get("description"),
    )
    
    # Update deal_type
    listing.deal_type = deal_type
    if deal_type == "rent":
        listing.rental_class = data.get("rental_class")
        listing.price_per_day = Decimal(data.get("price", "0"))
    
    await db_session.commit()
    
    await state.clear()
    await callback.message.edit_text(_("auto.listing_created"))
    
    logger.info(f"Auto listing {listing.id} created by user {user.id}")


@router.callback_query(F.data == "auto:cancel")
async def cancel_auto_flow(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Cancel auto flow."""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(_("buttons.cancelled"))


# ============ AUTO REQUIREMENT HANDLERS (BUYER) ============

@router.message(AutoRequirementStates.brands)
async def process_auto_req_brands(
    message: Message,
    state: FSMContext,
    _: Any,
) -> None:
    """Process brand input for requirement."""
    brands_text = message.text.strip()
    # Allow comma-separated brands or single brand
    brands = [b.strip() for b in brands_text.split(",") if b.strip()]
    
    if not brands:
        await message.answer(_("errors.invalid_input"))
        return
    
    await state.update_data(brands=brands)
    await message.answer(_("auto.enter_year_range"))
    await state.set_state(AutoRequirementStates.year_range)


@router.message(AutoRequirementStates.year_range)
async def process_auto_req_year_range(
    message: Message,
    state: FSMContext,
    _: Any,
) -> None:
    """Process year range input."""
    try:
        text = message.text.strip().replace(" ", "")
        if "-" in text:
            parts = text.split("-")
            year_min = int(parts[0])
            year_max = int(parts[1])
        else:
            year_min = int(text)
            year_max = 2025
        
        if year_min < 1950 or year_max > 2025 or year_min > year_max:
            raise ValueError()
    except (ValueError, IndexError):
        await message.answer(_("edit.invalid_range"))
        return
    
    await state.update_data(year_min=year_min, year_max=year_max)
    await message.answer(_("auto.enter_price_range"))
    await state.set_state(AutoRequirementStates.price_range)


@router.message(AutoRequirementStates.price_range)
async def process_auto_req_price_range(
    message: Message,
    state: FSMContext,
    _: Any,
) -> None:
    """Process price range input."""
    try:
        text = message.text.strip().replace(" ", "").replace(",", "")
        if "-" in text:
            parts = text.split("-")
            price_min = Decimal(parts[0])
            price_max = Decimal(parts[1])
        else:
            price_min = Decimal("0")
            price_max = Decimal(text)
        
        if price_min < 0 or price_max <= 0 or price_min > price_max:
            raise ValueError()
    except (ValueError, IndexError):
        await message.answer(_("edit.invalid_range"))
        return
    
    await state.update_data(price_min=str(price_min), price_max=str(price_max))
    
    data = await state.get_data()
    deal_type = data.get("deal_type", "sale")
    
    if deal_type == "rent":
        # For rental, go to rental class selection
        await message.answer(
            _("auto.select_rental_class"),
            reply_markup=build_rental_class_keyboard(_),
        )
        await state.set_state(AutoRequirementStates.body_type)  # reuse
    else:
        await message.answer(_("auto.enter_mileage_range"))
        await state.set_state(AutoRequirementStates.mileage_max)


@router.message(AutoRequirementStates.mileage_max)
async def process_auto_req_mileage(
    message: Message,
    state: FSMContext,
    _: Any,
) -> None:
    """Process mileage max input."""
    try:
        text = message.text.strip().replace(" ", "").replace(",", "")
        if "-" in text:
            parts = text.split("-")
            mileage_max = int(parts[1])
        else:
            mileage_max = int(text)
        
        if mileage_max < 0:
            raise ValueError()
    except (ValueError, IndexError):
        await message.answer(_("errors.invalid_input"))
        return
    
    await state.update_data(mileage_max=mileage_max)
    await message.answer(
        _("auto.select_transmission"),
        reply_markup=build_transmission_keyboard(_),
    )
    await state.set_state(AutoRequirementStates.transmission)


@router.callback_query(F.data.startswith("auto_trans:"), AutoRequirementStates.transmission)
async def process_auto_req_transmission(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Process transmission selection for requirement."""
    transmission = callback.data.split(":")[1]
    await callback.answer()
    
    data = await state.get_data()
    transmissions = data.get("transmissions", [])
    transmissions.append(transmission)
    await state.update_data(transmissions=transmissions)
    
    await callback.message.edit_text(
        _("auto.select_fuel"),
        reply_markup=build_fuel_type_keyboard(_),
    )
    await state.set_state(AutoRequirementStates.fuel_type)


@router.callback_query(F.data.startswith("auto_fuel:"), AutoRequirementStates.fuel_type)
async def process_auto_req_fuel(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Process fuel type selection for requirement."""
    fuel_type = callback.data.split(":")[1]
    await callback.answer()
    
    data = await state.get_data()
    fuel_types = data.get("fuel_types", [])
    fuel_types.append(fuel_type)
    await state.update_data(fuel_types=fuel_types)
    
    await callback.message.edit_text(_("auto.enter_city"))
    await state.set_state(AutoRequirementStates.city)


@router.callback_query(F.data.startswith("auto_rental_class:"), AutoRequirementStates.body_type)
async def process_auto_req_rental_class(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Process rental class selection for requirement."""
    rental_class = callback.data.split(":")[1]
    await callback.answer()
    
    data = await state.get_data()
    rental_classes = data.get("rental_classes", [])
    rental_classes.append(rental_class)
    await state.update_data(rental_classes=rental_classes)
    
    await callback.message.edit_text(_("auto.enter_city"))
    await state.set_state(AutoRequirementStates.city)


@router.message(AutoRequirementStates.city)
async def process_auto_req_city(
    message: Message,
    state: FSMContext,
    _: Any,
) -> None:
    """Process city input for requirement."""
    city = message.text.strip()
    if len(city) < 2 or len(city) > 100:
        await message.answer(_("errors.invalid_input"))
        return
    
    await state.update_data(city=city)
    
    # Show confirmation
    await _show_auto_requirement_confirmation(message, state, _)


async def _show_auto_requirement_confirmation(
    message: Message,
    state: FSMContext,
    _: Any,
) -> None:
    """Show auto requirement confirmation."""
    data = await state.get_data()
    
    deal_type = data.get("deal_type", "sale")
    brands = ", ".join(data.get("brands", []))
    year_min = data.get("year_min", "")
    year_max = data.get("year_max", "")
    price_min = data.get("price_min", "0")
    price_max = data.get("price_max", "0")
    city = data.get("city", "")
    
    if deal_type == "rent":
        rental_classes = data.get("rental_classes", [])
        classes_text = ", ".join([_(f"auto.rental_class.{c}") for c in rental_classes])
        text = (
            f"🔍 <b>{_('auto.rent')}</b>\n\n"
            f"<b>{_('auto.brand')}:</b> {brands}\n"
            f"<b>{_('auto.year')}:</b> {year_min}-{year_max}\n"
            f"<b>🎯 Класс:</b> {classes_text}\n"
            f"<b>💰 {_('auto.price')}:</b> {price_min}-{price_max} AZN/день\n"
            f"<b>🏙️:</b> {city}\n\n"
            f"{_('buttons.confirm')}?"
        )
    else:
        mileage_max = data.get("mileage_max", 0)
        transmissions = data.get("transmissions", [])
        fuel_types = data.get("fuel_types", [])
        trans_text = ", ".join([_(f"auto.transmission.{t}") for t in transmissions])
        fuel_text = ", ".join([_(f"auto.fuel.{f}") for f in fuel_types])
        text = (
            f"🔍 <b>{_('auto.sale')}</b>\n\n"
            f"<b>{_('auto.brand')}:</b> {brands}\n"
            f"<b>{_('auto.year')}:</b> {year_min}-{year_max}\n"
            f"<b>{_('auto.mileage')}:</b> до {mileage_max:,} км\n"
            f"<b>⚙️:</b> {trans_text}\n"
            f"<b>⛽:</b> {fuel_text}\n"
            f"<b>💰 {_('auto.price')}:</b> {price_min}-{price_max} AZN\n"
            f"<b>🏙️:</b> {city}\n\n"
            f"{_('buttons.confirm')}?"
        )
    
    await message.answer(text, reply_markup=build_confirm_keyboard(_), parse_mode="HTML")
    await state.set_state(AutoRequirementStates.confirmation)


@router.callback_query(F.data == "auto:confirm", AutoRequirementStates.confirmation)
async def confirm_auto_requirement(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: AsyncSession,
) -> None:
    """Confirm and create auto requirement, then find matches."""
    await callback.answer()
    
    data = await state.get_data()
    deal_type = data.get("deal_type", "sale")
    
    req_service = AutoRequirementService(db_session)
    match_service = AutoMatchService(db_session)
    
    requirement = await req_service.create_requirement(
        user_id=user.id,
        brands=data.get("brands"),
        year_min=data.get("year_min"),
        year_max=data.get("year_max"),
        price_min=Decimal(data.get("price_min", "0")) if data.get("price_min") else None,
        price_max=Decimal(data.get("price_max", "0")) if data.get("price_max") else None,
        mileage_max=data.get("mileage_max") if deal_type == "sale" else None,
        fuel_types=data.get("fuel_types") if deal_type == "sale" else None,
        transmissions=data.get("transmissions") if deal_type == "sale" else None,
        rental_classes=data.get("rental_classes") if deal_type == "rent" else None,
        city=data.get("city"),
    )
    
    # Update deal_type
    requirement.deal_type = deal_type
    await db_session.commit()
    
    # Find matches
    matches = await match_service.find_matches(requirement.id)
    
    await state.clear()
    
    if matches:
        await callback.message.edit_text(
            f"{_('auto.requirement_created')}\n\n"
            f"🎯 {_('auto.matches_found')} ({len(matches)})"
        )
        # Start browsing matches
        await state.update_data(
            requirement_id=str(requirement.id),
            match_index=0,
            matches=[str(m.id) for m in matches],
        )
        await _show_match(callback.message, state, _, db_session, edit=False)
    else:
        await callback.message.edit_text(
            f"{_('auto.requirement_created')}\n\n"
            f"{_('auto.no_matches')}"
        )
    
    logger.info(f"Auto requirement {requirement.id} created by user {user.id}, {len(matches)} matches found")


# ============ MATCH BROWSING HANDLERS ============

async def _show_match(
    message: Message,
    state: FSMContext,
    _: Any,
    db_session: AsyncSession,
    edit: bool = True,
) -> None:
    """Show current match to user."""
    data = await state.get_data()
    matches = data.get("matches", [])
    index = data.get("match_index", 0)
    
    if not matches or index >= len(matches):
        text = _("auto.no_matches")
        if edit:
            await message.edit_text(text)
        else:
            await message.answer(text)
        return
    
    match_id = matches[index]
    match_service = AutoMatchService(db_session)
    match = await match_service.get_match(uuid.UUID(match_id))
    
    if not match or not match.listing:
        # Skip invalid match
        await state.update_data(match_index=index + 1)
        await _show_match(message, state, _, db_session, edit)
        return
    
    listing = match.listing
    
    # Build listing info text
    if listing.deal_type.value == "rent":
        price_text = f"{listing.price_per_day or listing.price} AZN/день"
        rental_class = listing.rental_class.value if listing.rental_class else ""
        text = (
            f"🚗 <b>{listing.brand} {listing.model}</b> ({listing.year})\n\n"
            f"🎯 Класс: {_(f'auto.rental_class.{rental_class}')}\n"
            f"💰 {price_text}\n"
            f"🏙️ {listing.city}\n"
        )
    else:
        text = (
            f"🚗 <b>{listing.brand} {listing.model}</b> ({listing.year})\n\n"
            f"🛣️ Пробег: {listing.mileage:,} км\n"
            f"⚙️ {_(f'auto.transmission.{listing.transmission.value}')}\n"
            f"⛽ {_(f'auto.fuel.{listing.fuel_type.value}')}\n"
            f"💰 {listing.price:,.0f} AZN\n"
            f"🏙️ {listing.city}\n"
        )
    
    if listing.description:
        text += f"\n📝 {listing.description[:200]}..."
    
    text += f"\n\n🎯 Совпадение: {match.score}%"
    
    # Mark as viewed
    await match_service.mark_viewed(match.id)
    
    keyboard = build_match_browse_keyboard(
        match_id=match_id,
        current=index + 1,
        total=len(matches),
        _=_,
    )
    
    # If listing has photos, send with photo
    if listing.media and len(listing.media) > 0:
        photo_url = listing.media[0].url
        if edit:
            try:
                await message.edit_media(
                    InputMediaPhoto(media=photo_url, caption=text, parse_mode="HTML"),
                    reply_markup=keyboard,
                )
            except Exception:
                await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            try:
                await message.answer_photo(photo_url, caption=text, reply_markup=keyboard, parse_mode="HTML")
            except Exception:
                await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        if edit:
            await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    
    await state.set_state(MatchBrowseStates.viewing)


@router.callback_query(F.data.startswith("auto_match:prev:"))
async def prev_match(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: AsyncSession,
) -> None:
    """Show previous match."""
    await callback.answer()
    data = await state.get_data()
    index = data.get("match_index", 0)
    matches = data.get("matches", [])
    
    new_index = (index - 1) % len(matches) if matches else 0
    await state.update_data(match_index=new_index)
    await _show_match(callback.message, state, _, db_session)


@router.callback_query(F.data.startswith("auto_match:next:"))
async def next_match(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: AsyncSession,
) -> None:
    """Show next match."""
    await callback.answer()
    data = await state.get_data()
    index = data.get("match_index", 0)
    matches = data.get("matches", [])
    
    new_index = (index + 1) % len(matches) if matches else 0
    await state.update_data(match_index=new_index)
    await _show_match(callback.message, state, _, db_session)


@router.callback_query(F.data.startswith("auto_match:respond:"))
async def respond_to_match(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: AsyncSession,
) -> None:
    """Show response options for match."""
    match_id = callback.data.split(":")[2]
    await callback.answer()
    
    match_service = AutoMatchService(db_session)
    match = await match_service.get_match(uuid.UUID(match_id))
    
    if not match or not match.listing:
        await callback.message.edit_text(_("errors.not_found"))
        return
    
    listing = match.listing
    car_info = f"{listing.brand} {listing.model}, {listing.year} г."
    
    text = _("auto.interested").format(car_info=car_info)
    
    await callback.message.edit_text(
        text,
        reply_markup=build_respond_choice_keyboard(match_id, _),
        parse_mode="HTML",
    )
    await state.set_state(MatchBrowseStates.respond_choice)


@router.callback_query(F.data.startswith("auto_respond:contacts:"))
async def request_contacts(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: AsyncSession,
) -> None:
    """Request seller contacts - needs seller approval."""
    match_id = callback.data.split(":")[2]
    await callback.answer()
    
    match_service = AutoMatchService(db_session)
    chat_service = AutoChatService(db_session)
    match = await match_service.get_match(uuid.UUID(match_id))
    
    if not match or not match.listing:
        await callback.message.edit_text(_("errors.not_found"))
        return
    
    # Create chat and send contact request to seller
    chat = await chat_service.create_chat(
        match_id=match.id,
        buyer_id=user.id,
        seller_id=match.listing.user_id,
    )
    
    # Mark buyer as wanting to reveal
    chat.buyer_revealed = True
    await db_session.commit()
    
    await callback.message.edit_text(_("auto.contact_request_sent"))
    
    # TODO: Send notification to seller about contact request
    logger.info(f"Contact request sent for match {match_id} by user {user.id}")


@router.callback_query(F.data.startswith("auto_respond:chat:"))
async def start_chat_with_seller(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: AsyncSession,
) -> None:
    """Start chat with seller via bot."""
    match_id = callback.data.split(":")[2]
    await callback.answer()
    
    match_service = AutoMatchService(db_session)
    chat_service = AutoChatService(db_session)
    match = await match_service.get_match(uuid.UUID(match_id))
    
    if not match or not match.listing:
        await callback.message.edit_text(_("errors.not_found"))
        return
    
    # Create chat
    chat = await chat_service.create_chat(
        match_id=match.id,
        buyer_id=user.id,
        seller_id=match.listing.user_id,
    )
    
    await state.update_data(active_chat_id=str(chat.id))
    await callback.message.edit_text(_("auto.write_message"))
    await state.set_state(MatchBrowseStates.writing_message)


@router.message(MatchBrowseStates.writing_message)
async def send_message_to_seller(
    message: Message,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: AsyncSession,
) -> None:
    """Send message to seller."""
    data = await state.get_data()
    chat_id = data.get("active_chat_id")
    
    if not chat_id:
        await message.answer(_("errors.session_expired"))
        await state.clear()
        return
    
    chat_service = AutoChatService(db_session)
    
    # Send message
    msg = await chat_service.send_message(
        chat_id=uuid.UUID(chat_id),
        sender_id=user.id,
        content=message.text[:2000] if message.text else "",
    )
    
    if msg:
        await message.answer(_("auto.message_sent"))
        # TODO: Send notification to seller
    else:
        await message.answer(_("errors.general"))
    
    await state.clear()


@router.callback_query(F.data.startswith("auto_respond:back:"))
async def back_from_respond(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: AsyncSession,
) -> None:
    """Go back to match viewing."""
    await callback.answer()
    await _show_match(callback.message, state, _, db_session)


@router.callback_query(F.data == "auto:back_to_profile")
async def back_to_profile(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Go back to profile."""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(_("profile.title"))
