import logging
from decimal import Decimal
from typing import Any, Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reference import Category
from app.models.requirement import Requirement
from app.core.cache import get_cities, get_districts, get_metro_stations

logger = logging.getLogger(__name__)

from app.bot.keyboards.builders import (
    build_categories_keyboard,
    build_location_type_keyboard,
    build_city_keyboard,
    build_city_keyboard_static,
    build_district_keyboard,
    build_metro_line_keyboard,
    build_metro_keyboard,
    build_payment_type_keyboard,
    build_renovation_keyboard,
    build_documents_keyboard,
    build_utilities_keyboard,
    build_heating_keyboard,
    build_property_age_keyboard,
    build_floor_preferences_keyboard,
    build_skip_keyboard,
    build_confirm_keyboard,
    build_start_over_keyboard,
)
from app.bot.keyboards.callbacks import (
    LocationCallback,
    FormFieldCallback,
    NavigationCallback,
)
from app.bot.states import RequirementStates

router = Router(name="requirement")

@router.callback_query(F.data.startswith("cat:"), RequirementStates.category)
async def process_category(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    category = callback.data.split(":")[1]
    await state.update_data(category=category)
    await callback.message.edit_text(
        _("location.select_type"),
        reply_markup=build_location_type_keyboard(_),
    )
    await state.set_state(RequirementStates.location_type)

@router.callback_query(LocationCallback.filter(F.type == "city"), RequirementStates.location_type)
async def location_city(callback: CallbackQuery, state: FSMContext, _: Any, lang: str) -> None:
    await callback.answer()
    await state.update_data(selected_locations=[], user_lang=lang)
    await callback.message.edit_text(
        _("location.select_city"),
        reply_markup=build_city_keyboard_static(_, allow_multiple=False, lang=lang),
    )
    await state.set_state(RequirementStates.location_select)


@router.callback_query(F.data.startswith("city_select:"), RequirementStates.location_select)
async def city_selected(callback: CallbackQuery, state: FSMContext, _: Any, lang: str) -> None:
    """Handle city selection - single city only. If Baku, start sequential location input."""
    city = callback.data.split(":", 1)[1]
    await callback.answer()
    
    await state.update_data(city=city, selected_locations=[city])
    
    # Check if Baku selected (Bakı, Баку, Baku)
    if city.lower() in ["bakı", "баку", "baku"]:
        # Step 1: Show districts for Baku
        districts = get_districts("1")
        keyboard = build_district_keyboard_with_skip(districts, _, lang=lang)
        await callback.message.edit_text(
            _("location.select_district"),
            reply_markup=keyboard,
        )
        await state.set_state(RequirementStates.district_select)
    else:
        # For other cities, go directly to price
        await callback.message.edit_text(_("form.price.enter_range"))
        await state.set_state(RequirementStates.price_range)


def build_district_keyboard_with_skip(
    districts: list[dict],
    _: Any,
    lang: str = "az",
) -> InlineKeyboardMarkup:
    """Build district keyboard with skip button."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    
    name_field = f"name_{lang}"
    for district in districts:
        name = district.get(name_field, district.get("name_en", "Unknown"))
        builder.button(
            text=name,
            callback_data=LocationCallback(type="select", id=str(district["id"])),
        )
    
    builder.adjust(2)
    
    # Skip button
    builder.row()
    builder.button(text=f"⏭️ {_('buttons.skip')}", callback_data="skip_district")
    
    builder.row()
    builder.button(text=_("buttons.back"), callback_data=NavigationCallback(action="back").pack())
    
    return builder.as_markup()


@router.callback_query(LocationCallback.filter(F.type == "select"), RequirementStates.district_select)
async def district_selected(callback: CallbackQuery, state: FSMContext, _: Any, lang: str, callback_data: LocationCallback) -> None:
    """Handle district selection for Baku. Then go to metro."""
    district_id = callback_data.id
    await callback.answer()
    
    # Get district name
    districts = get_districts("1")
    district_name = None
    for d in districts:
        if str(d["id"]) == district_id:
            district_name = d.get("name_az", d.get("name_en"))
            break
    
    await state.update_data(district=district_name, district_id=district_id)
    
    # Step 2: Go to metro selection
    keyboard = build_metro_line_keyboard_with_skip(_)
    await callback.message.edit_text(
        _("metro.select_line"),
        reply_markup=keyboard,
    )
    await state.set_state(RequirementStates.metro_select)


@router.callback_query(F.data == "skip_district", RequirementStates.district_select)
async def skip_district(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    """Skip district selection, go to metro."""
    await callback.answer()
    
    # Step 2: Go to metro selection
    keyboard = build_metro_line_keyboard_with_skip(_)
    await callback.message.edit_text(
        _("metro.select_line"),
        reply_markup=keyboard,
    )
    await state.set_state(RequirementStates.metro_select)


def build_metro_line_keyboard_with_skip(_: Any) -> InlineKeyboardMarkup:
    """Build metro line keyboard with skip button."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text=f"🟢 {_('metro.green_line')}",
        callback_data=LocationCallback(type="metro_line", id="green"),
    )
    builder.button(
        text=f"🔴 {_('metro.red_line')}",
        callback_data=LocationCallback(type="metro_line", id="red"),
    )
    builder.button(
        text=f"🟣 {_('metro.purple_line')}",
        callback_data=LocationCallback(type="metro_line", id="purple"),
    )
    
    builder.adjust(1)
    
    # Skip button
    builder.row()
    builder.button(text=f"⏭️ {_('buttons.skip')}", callback_data="skip_metro")
    
    builder.row()
    builder.button(text=_("buttons.back"), callback_data=NavigationCallback(action="back").pack())
    
    return builder.as_markup()


@router.callback_query(LocationCallback.filter(F.type == "metro_line"), RequirementStates.metro_select)
async def metro_line_selected(callback: CallbackQuery, state: FSMContext, _: Any, lang: str, callback_data: LocationCallback) -> None:
    """Handle metro line selection."""
    line = callback_data.id
    await callback.answer()
    
    stations = get_metro_stations(line)
    keyboard = build_metro_keyboard_with_skip(stations, _, lang=lang)
    await callback.message.edit_text(
        _("location.select_metro"),
        reply_markup=keyboard,
    )
    await state.update_data(metro_line=line)


def build_metro_keyboard_with_skip(
    stations: list[dict],
    _: Any,
    lang: str = "az",
) -> InlineKeyboardMarkup:
    """Build metro station keyboard with skip button."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    
    name_field = f"name_{lang}"
    for station in stations:
        name = station.get(name_field, station.get("name_en", "Unknown"))
        builder.button(
            text=name,
            callback_data=LocationCallback(type="metro_station", id=str(station["id"])),
        )
    
    builder.adjust(2)
    
    # Skip button
    builder.row()
    builder.button(text=f"⏭️ {_('buttons.skip')}", callback_data="skip_metro")
    
    builder.row()
    builder.button(text=_("buttons.back"), callback_data=LocationCallback(type="metro_back").pack())
    
    return builder.as_markup()


@router.callback_query(LocationCallback.filter(F.type == "metro_station"), RequirementStates.metro_select)
async def metro_station_selected(callback: CallbackQuery, state: FSMContext, _: Any, callback_data: LocationCallback) -> None:
    """Handle metro station selection. Then go to landmark."""
    station_id = callback_data.id
    await callback.answer()
    
    data = await state.get_data()
    line = data.get("metro_line", "green")
    stations = get_metro_stations(line)
    
    station_name = None
    for s in stations:
        if str(s["id"]) == station_id:
            station_name = s.get("name_az", s.get("name_en"))
            break
    
    await state.update_data(metro_station=station_name, metro_id=station_id)
    
    # Step 3: Go to landmark input
    keyboard = build_landmark_keyboard(_)
    await callback.message.edit_text(
        _("location.enter_landmark"),
        reply_markup=keyboard,
    )
    await state.set_state(RequirementStates.landmark_input)


@router.callback_query(F.data == "skip_metro", RequirementStates.metro_select)
async def skip_metro(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    """Skip metro selection, go to landmark."""
    await callback.answer()
    
    # Step 3: Go to landmark input
    keyboard = build_landmark_keyboard(_)
    await callback.message.edit_text(
        _("location.enter_landmark"),
        reply_markup=keyboard,
    )
    await state.set_state(RequirementStates.landmark_input)


def build_landmark_keyboard(_: Any) -> InlineKeyboardMarkup:
    """Build landmark input keyboard with skip button."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    
    builder.button(text=f"⏭️ {_('buttons.skip')}", callback_data="skip_landmark")
    builder.row()
    builder.button(text=_("buttons.back"), callback_data=NavigationCallback(action="back").pack())
    
    return builder.as_markup()


@router.message(RequirementStates.landmark_input)
async def landmark_input(message: Message, state: FSMContext, _: Any) -> None:
    """Handle landmark text input."""
    landmark = message.text.strip()[:100] if message.text else None
    
    if landmark:
        await state.update_data(landmark=landmark)
    
    await message.answer(_("form.price.enter_range"))
    await state.set_state(RequirementStates.price_range)


@router.callback_query(F.data == "skip_landmark", RequirementStates.landmark_input)
async def skip_landmark(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    """Skip landmark input, go to price."""
    await callback.answer()
    await callback.message.edit_text(_("form.price.enter_range"))
    await state.set_state(RequirementStates.price_range)


@router.callback_query(F.data.startswith("city_page:"), RequirementStates.location_select)
async def city_page(callback: CallbackQuery, state: FSMContext, _: Any, lang: str) -> None:
    """Handle city pagination for requirements."""
    page = int(callback.data.split(":")[1])
    await callback.answer()
    await callback.message.edit_text(
        _("location.select_city"),
        reply_markup=build_city_keyboard_static(_, page=page, allow_multiple=False, lang=lang),
    )


@router.callback_query(F.data == "city_confirm", RequirementStates.location_select)
async def city_confirm(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    """Confirm city selection for requirements."""
    data = await state.get_data()
    selected = data.get("selected_locations", [])
    if not selected:
        await callback.answer(_("location.select_at_least_one"), show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(_("form.price.enter_range"))
    await state.set_state(RequirementStates.price_range)



def parse_range(text: str) -> tuple[float | None, float | None]:
    """Parse range input like '12 - 34' or '12-34' into (min, max) tuple."""
    # Remove spaces and thousand separators (commas), keep decimal dots
    text = text.replace(" ", "").replace(",", "")
    if "-" in text:
        parts = text.split("-")
        if len(parts) == 2:
            try:
                min_val = float(parts[0]) if parts[0] else None
                max_val = float(parts[1]) if parts[1] else None
                return min_val, max_val
            except ValueError:
                pass
    return None, None

@router.callback_query(NavigationCallback.filter(F.action == "confirm"), RequirementStates.location_select)
async def confirm_locations(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    data = await state.get_data()
    if not data.get("selected_locations") and not data.get("metro_id"):
        await callback.answer(_("location.select_at_least_one"), show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(_("form.price.enter_range"))
    await state.set_state(RequirementStates.price_range)

@router.callback_query(LocationCallback.filter(F.type == "metro"), RequirementStates.location_type)
async def location_metro(callback: CallbackQuery, state: FSMContext, _: Any) -> None:

    await callback.answer()
    await callback.message.edit_text(
        _("metro.select_line"),
        reply_markup=build_metro_line_keyboard(_),
    )
    await state.set_state(RequirementStates.location_select)

@router.callback_query(LocationCallback.filter(F.type == "metro_line"), RequirementStates.location_select)
async def metro_line_selected(callback: CallbackQuery, callback_data: LocationCallback, state: FSMContext, _: Any, lang: str) -> None:

    await callback.answer()
    await state.update_data(metro_line=callback_data.id)
    stations = get_metro_stations(callback_data.id)
    await callback.message.edit_text(
        _("location.select_metro"),
        reply_markup=build_metro_keyboard(stations, _, lang),
    )

@router.callback_query(LocationCallback.filter(F.type == "metro_back"), RequirementStates.location_select)
async def metro_back_to_lines(callback: CallbackQuery, state: FSMContext, _: Any) -> None:

    await callback.answer()
    await callback.message.edit_text(
        _("metro.select_line"),
        reply_markup=build_metro_line_keyboard(_),
    )

@router.callback_query(LocationCallback.filter(F.type == "metro_station"), RequirementStates.location_select)
async def metro_station_selected(callback: CallbackQuery, callback_data: LocationCallback, state: FSMContext, _: Any) -> None:

    await callback.answer()
    await state.update_data(metro_id=callback_data.id)
    await callback.message.edit_text(_("form.price.enter_range"))
    await state.set_state(RequirementStates.price_range)

@router.callback_query(LocationCallback.filter(F.type == "gps"), RequirementStates.location_type)
async def location_gps(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await callback.message.edit_text(_("location.share_location"))
    await state.set_state(RequirementStates.location_gps)

@router.message(F.location, RequirementStates.location_gps)
async def gps_received(message: Message, state: FSMContext, _: Any) -> None:
    await state.update_data(latitude=message.location.latitude, longitude=message.location.longitude)
    await message.answer(_("form.price.enter_range"))
    await state.set_state(RequirementStates.price_range)

@router.message(RequirementStates.price_range)
async def process_price_range(message: Message, state: FSMContext, _: Any) -> None:
    price_min, price_max = parse_range(message.text)
    if price_min is None or price_max is None or price_min < 0 or price_max <= 0:
        await message.answer(_("form.price.invalid_range"))
        return
    if price_min > price_max:
        price_min, price_max = price_max, price_min
    await state.update_data(price_min=price_min, price_max=price_max)
    await message.answer(_("form.payment.select"), reply_markup=build_payment_type_keyboard(_))
    await state.set_state(RequirementStates.payment_type)

@router.callback_query(FormFieldCallback.filter(F.field == "payment_type"), RequirementStates.payment_type)
async def process_payment(callback: CallbackQuery, callback_data: FormFieldCallback, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await state.update_data(payment_type=callback_data.value)
    
    if callback_data.value in ("credit", "both"):
        await callback.message.edit_text(_("form.down_payment.enter"), reply_markup=build_skip_keyboard(_))
        await state.set_state(RequirementStates.down_payment)
    else:
        data = await state.get_data()
        if data.get("category") == "land":
            await callback.message.edit_text(_("form.area.enter_range"))
            await state.set_state(RequirementStates.area_range)
        else:
            await callback.message.edit_text(_("form.rooms.enter_range"))
            await state.set_state(RequirementStates.rooms_range)

@router.message(RequirementStates.down_payment)
async def process_down_payment(message: Message, state: FSMContext, _: Any) -> None:
    try:
        dp = float(message.text.replace(",", ".").replace(" ", ""))
        await state.update_data(down_payment=dp)
    except ValueError:
        pass
    data = await state.get_data()
    if data.get("category") == "land":
        await message.answer(_("form.area.enter_range"))
        await state.set_state(RequirementStates.area_range)
    else:
        await message.answer(_("form.rooms.enter_range"))
        await state.set_state(RequirementStates.rooms_range)

@router.callback_query(NavigationCallback.filter(F.action == "skip"), RequirementStates.down_payment)
async def skip_down_payment(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    data = await state.get_data()
    if data.get("category") == "land":
        await callback.message.edit_text(_("form.area.enter_range"))
        await state.set_state(RequirementStates.area_range)
    else:
        await callback.message.edit_text(_("form.rooms.enter_range"))
        await state.set_state(RequirementStates.rooms_range)

@router.message(RequirementStates.rooms_range)
async def process_rooms_range(message: Message, state: FSMContext, _: Any) -> None:
    rooms_min, rooms_max = parse_range(message.text)
    if rooms_min is None or rooms_max is None:
        await message.answer(_("form.rooms.invalid_range"))
        return
    rooms_min, rooms_max = int(rooms_min), int(rooms_max)
    if not (1 <= rooms_min <= 20) or not (1 <= rooms_max <= 20):
        await message.answer(_("form.rooms.invalid"))
        return
    if rooms_min > rooms_max:
        rooms_min, rooms_max = rooms_max, rooms_min
    await state.update_data(rooms_min=rooms_min, rooms_max=rooms_max)
    await message.answer(_("form.area.enter_range"))
    await state.set_state(RequirementStates.area_range)

@router.message(RequirementStates.area_range)
async def process_area_range(message: Message, state: FSMContext, _: Any) -> None:
    area_min, area_max = parse_range(message.text)
    if area_min is None or area_max is None or area_min < 0 or area_max <= 0:
        await message.answer(_("form.area.invalid_range"))
        return
    if area_min > area_max:
        area_min, area_max = area_max, area_min
    await state.update_data(area_min=area_min, area_max=area_max)
    data = await state.get_data()
    if data.get("category") in ("land", "private_house"):
        await message.answer(_("form.renovation.select"), reply_markup=build_renovation_keyboard(_, allow_multiple=True))
        await state.set_state(RequirementStates.renovation)
    else:
        await message.answer(_("form.floor.enter_range"))
        await state.set_state(RequirementStates.floor_range)

@router.message(RequirementStates.floor_range)
async def process_floor_range(message: Message, state: FSMContext, _: Any) -> None:
    floor_min, floor_max = parse_range(message.text)
    if floor_min is None or floor_max is None:
        await message.answer(_("form.floor.invalid_range"))
        return
    floor_min, floor_max = int(floor_min), int(floor_max)
    if not (-2 <= floor_min <= 50) or not (-2 <= floor_max <= 50):
        await message.answer(_("form.floor.invalid"))
        return
    if floor_min > floor_max:
        floor_min, floor_max = floor_max, floor_min
    await state.update_data(floor_min=floor_min, floor_max=floor_max)
    await message.answer(_("form.floor.preferences"), reply_markup=build_floor_preferences_keyboard(_))
    await state.set_state(RequirementStates.floor_preferences)

@router.callback_query(FormFieldCallback.filter(F.field == "floor_pref"), RequirementStates.floor_preferences)
async def toggle_floor_pref(callback: CallbackQuery, callback_data: FormFieldCallback, state: FSMContext, _: Any) -> None:
    await callback.answer()
    data = await state.get_data()
    prefs = data.get("floor_preferences", {})
    key = callback_data.value
    prefs[key] = not prefs.get(key, False)
    await state.update_data(floor_preferences=prefs)
    await callback.message.edit_reply_markup(reply_markup=build_floor_preferences_keyboard(_, selected=prefs))

@router.callback_query(NavigationCallback.filter(F.action == "confirm"), RequirementStates.floor_preferences)
async def confirm_floor_prefs(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await callback.message.edit_text(_("form.renovation.select"), reply_markup=build_renovation_keyboard(_, allow_multiple=True))
    await state.set_state(RequirementStates.renovation)

@router.callback_query(FormFieldCallback.filter(F.field == "renovation"), RequirementStates.renovation)
async def process_renovation(callback: CallbackQuery, callback_data: FormFieldCallback, state: FSMContext, _: Any) -> None:
    await callback.answer()
    if callback_data.value == "any":
        await state.update_data(renovation=["any"])
        await callback.message.edit_text(_("form.documents.select"), reply_markup=build_documents_keyboard(_, allow_multiple=True))
        await state.set_state(RequirementStates.documents)
        return
    data = await state.get_data()
    reno = data.get("renovation", [])
    if "any" in reno:
        reno = []
    if callback_data.value in reno:
        reno.remove(callback_data.value)
    else:
        reno.append(callback_data.value)
    await state.update_data(renovation=reno)
    await callback.message.edit_reply_markup(reply_markup=build_renovation_keyboard(_, allow_multiple=True, selected=reno))

@router.callback_query(NavigationCallback.filter(F.action == "confirm"), RequirementStates.renovation)
async def confirm_renovation(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await callback.message.edit_text(_("form.documents.select"), reply_markup=build_documents_keyboard(_, allow_multiple=True))
    await state.set_state(RequirementStates.documents)

@router.callback_query(FormFieldCallback.filter(F.field == "documents"), RequirementStates.documents)
async def process_documents(callback: CallbackQuery, callback_data: FormFieldCallback, state: FSMContext, _: Any) -> None:
    await callback.answer()
    if callback_data.value == "any":
        await state.update_data(documents=["any"])
        await callback.message.edit_text(_("form.utilities.gas"), reply_markup=build_utilities_keyboard(_, "gas"))
        await state.set_state(RequirementStates.utilities)
        return
    data = await state.get_data()
    docs = data.get("documents", [])
    if "any" in docs:
        docs = []
    if callback_data.value in docs:
        docs.remove(callback_data.value)
    else:
        docs.append(callback_data.value)
    await state.update_data(documents=docs)
    await callback.message.edit_reply_markup(reply_markup=build_documents_keyboard(_, allow_multiple=True, selected=docs))

@router.callback_query(NavigationCallback.filter(F.action == "confirm"), RequirementStates.documents)
async def confirm_documents(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await callback.message.edit_text(_("form.utilities.gas"), reply_markup=build_utilities_keyboard(_, "gas"))
    await state.set_state(RequirementStates.utilities)

@router.callback_query(FormFieldCallback.filter(F.field.startswith("utility_")), RequirementStates.utilities)
async def process_utilities(callback: CallbackQuery, callback_data: FormFieldCallback, state: FSMContext, _: Any) -> None:
    await callback.answer()
    data = await state.get_data()
    utility_type = callback_data.field.replace("utility_", "")
    utilities = data.get("utilities", {})
    utilities[utility_type] = callback_data.value
    await state.update_data(utilities=utilities)
    
    if utility_type == "gas":
        await callback.message.edit_text(_("form.utilities.electricity"), reply_markup=build_utilities_keyboard(_, "electricity"))
    elif utility_type == "electricity":
        await callback.message.edit_text(_("form.utilities.water"), reply_markup=build_utilities_keyboard(_, "water"))
    else:
        await callback.message.edit_text(_("form.heating.select"), reply_markup=build_heating_keyboard(_, allow_multiple=True))
        await state.set_state(RequirementStates.heating)

@router.callback_query(FormFieldCallback.filter(F.field == "heating"), RequirementStates.heating)
async def process_heating(callback: CallbackQuery, callback_data: FormFieldCallback, state: FSMContext, _: Any) -> None:
    await callback.answer()
    if callback_data.value == "any":
        await state.update_data(heating=["any"])
        await callback.message.edit_text(_("form.age.select"), reply_markup=build_property_age_keyboard(_, allow_multiple=True))
        await state.set_state(RequirementStates.property_age)
        return
    data = await state.get_data()
    heat = data.get("heating", [])
    if "any" in heat:
        heat = []
    if callback_data.value in heat:
        heat.remove(callback_data.value)
    else:
        heat.append(callback_data.value)
    await state.update_data(heating=heat)
    await callback.message.edit_reply_markup(reply_markup=build_heating_keyboard(_, allow_multiple=True, selected=heat))

@router.callback_query(NavigationCallback.filter(F.action == "confirm"), RequirementStates.heating)
async def confirm_heating(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await callback.message.edit_text(_("form.age.select"), reply_markup=build_property_age_keyboard(_, allow_multiple=True))
    await state.set_state(RequirementStates.property_age)

@router.callback_query(FormFieldCallback.filter(F.field == "property_age"), RequirementStates.property_age)
async def process_age(callback: CallbackQuery, callback_data: FormFieldCallback, state: FSMContext, _: Any) -> None:
    await callback.answer()
    if callback_data.value == "any":
        await state.update_data(property_age=["any"])
        await callback.message.edit_text(_("form.description.enter_comments"), reply_markup=build_skip_keyboard(_))
        await state.set_state(RequirementStates.comments)
        return
    data = await state.get_data()
    ages = data.get("property_age", [])
    if "any" in ages:
        ages = []
    if callback_data.value in ages:
        ages.remove(callback_data.value)
    else:
        ages.append(callback_data.value)
    await state.update_data(property_age=ages)
    await callback.message.edit_reply_markup(reply_markup=build_property_age_keyboard(_, allow_multiple=True, selected=ages))

@router.callback_query(NavigationCallback.filter(F.action == "confirm"), RequirementStates.property_age)
async def confirm_age(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await callback.message.edit_text(_("form.description.enter_comments"), reply_markup=build_skip_keyboard(_))
    await state.set_state(RequirementStates.comments)

@router.message(RequirementStates.comments)
async def process_comments(message: Message, state: FSMContext, _: Any) -> None:

    await state.update_data(comments=message.text[:500])
    await show_requirement_summary(message, state, _)

@router.callback_query(NavigationCallback.filter(F.action == "skip"), RequirementStates.comments)
async def skip_comments(callback: CallbackQuery, state: FSMContext, _: Any) -> None:

    await callback.answer()
    await show_requirement_summary_callback(callback, state, _)

async def show_requirement_summary(message: Message, state: FSMContext, _: Any) -> None:

    data = await state.get_data()
    summary = format_requirement_summary(data, _)
    await message.answer(summary, reply_markup=build_confirm_keyboard(_), parse_mode="HTML")
    await state.set_state(RequirementStates.confirmation)

async def show_requirement_summary_callback(callback: CallbackQuery, state: FSMContext, _: Any) -> None:

    data = await state.get_data()
    summary = format_requirement_summary(data, _)
    await callback.message.edit_text(summary, reply_markup=build_confirm_keyboard(_), parse_mode="HTML")
    await state.set_state(RequirementStates.confirmation)

def format_requirement_summary(data: dict, _: Any) -> str:

    category = data.get('category', '')
    category_name = _(f'categories.{category}') if category else '-'
    
    payment = data.get('payment_type', '')
    payment_name = _(f'form.payment.{payment}') if payment else '-'
    
    currency = _('form.price.currency')
    
    price_min = data.get('price_min', 0)
    price_max = data.get('price_max', 0)
    
    lines = []
    lines.append("<b>" + _('requirement.summary') + "</b>")
    lines.append("")
    lines.append(f"<b>{_('form.category')}:</b> {category_name}")
    lines.append(f"<b>{_('form.price.label')}:</b> {price_min:,.0f} - {price_max:,.0f} {currency}")
    lines.append(f"<b>{_('form.payment.label')}:</b> {payment_name}")
    
    if data.get('down_payment'):
        lines.append(f"<b>{_('form.down_payment.label')}:</b> {data.get('down_payment'):,.0f} {currency}")
    
    if data.get('category') != 'land':
        rooms_min = data.get('rooms_min', '-')
        rooms_max = data.get('rooms_max', '-')
        lines.append(f"<b>{_('form.rooms.label')}:</b> {rooms_min} - {rooms_max}")
    
    area_min = data.get('area_min', 0)
    area_max = data.get('area_max', 0)
    lines.append(f"<b>{_('form.area.label')}:</b> {area_min} - {area_max} m²")
    
    if data.get('floor_min') is not None:
        floor_min = data.get('floor_min', '-')
        floor_max = data.get('floor_max', '-')
        lines.append(f"<b>{_('form.floor.label')}:</b> {floor_min} - {floor_max}")
    
    city = data.get('city')
    if city:
        lines.append(f"<b>{_('form.city')}:</b> {city}")
        # Show district, metro, landmark separately
        district = data.get('district') or '-'
        metro = data.get('metro_station') or '-'
        landmark = data.get('landmark') or '-'
        lines.append(f"<b>{_('location.district')}:</b> {district}")
        lines.append(f"<b>{_('location.metro')}:</b> {metro}")
        lines.append(f"<b>{_('location.landmark')}:</b> {landmark}")
    
    if data.get('comments'):
        lines.append("")
        lines.append(data.get('comments', '')[:100])
    
    lines.append("")
    lines.append(_('requirement.confirm_to_start'))
    
    return "\n".join(lines)

@router.callback_query(NavigationCallback.filter(F.action == "confirm"), RequirementStates.confirmation)
async def confirm_requirement(
    callback: CallbackQuery, 
    state: FSMContext, 
    _: Any, 
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Confirm and submit requirement to database, then show matching listings."""
    await callback.answer()
    
    data = await state.get_data()
    
    try:
        if db_session and user:
            category_code = data.get("category", "other")
            category = await get_or_create_category(db_session, category_code)
            
            floor_prefs = data.get("floor_preferences", {})
            
            payment_type_str = data.get("payment_type")
            payment_type_enum = None
            if payment_type_str:
                from app.models.requirement import RequirementPaymentTypeEnum, RequirementStatusEnum, RequirementDealTypeEnum
                payment_map = {
                    "cash": RequirementPaymentTypeEnum.CASH,
                    "credit": RequirementPaymentTypeEnum.CREDIT,
                    "both": RequirementPaymentTypeEnum.BOTH,
                    "any": RequirementPaymentTypeEnum.ANY,
                }
                payment_type_enum = payment_map.get(payment_type_str)
            else:
                from app.models.requirement import RequirementStatusEnum, RequirementDealTypeEnum
            
            # Get deal type from state
            deal_type_str = data.get("deal_type", "sale")
            deal_type_enum = RequirementDealTypeEnum.RENT if deal_type_str == "rent" else RequirementDealTypeEnum.SALE
            
            requirement = Requirement(
                user_id=user.id,
                category_id=category.id,
                deal_type=deal_type_enum,
                price_min=Decimal(str(data.get("price_min", 0))) if data.get("price_min") else None,
                price_max=Decimal(str(data.get("price_max", 0))) if data.get("price_max") else None,
                payment_type=payment_type_enum,
                down_payment_max=Decimal(str(data.get("down_payment", 0))) if data.get("down_payment") else None,
                rooms_min=data.get("rooms_min"),
                rooms_max=data.get("rooms_max"),
                area_min=Decimal(str(data.get("area_min", 0))) if data.get("area_min") else None,
                area_max=Decimal(str(data.get("area_max", 0))) if data.get("area_max") else None,
                floor_min=data.get("floor_min"),
                floor_max=data.get("floor_max"),
                not_first_floor=floor_prefs.get("not_first", False),
                not_last_floor=floor_prefs.get("not_last", False),
                renovation_status=data.get("renovation", []),
                document_types=data.get("documents", []),
                utilities=data.get("utilities", {}),
                heating_types=data.get("heating", []),
                property_age=data.get("property_age", []),
                comments=data.get("comments"),
                status=RequirementStatusEnum.ACTIVE,
            )
            
            db_session.add(requirement)
            await db_session.commit()
            await db_session.refresh(requirement)
            
            logger.info(f"Created requirement {requirement.id} for user {user.id}")
            
            # Search for matching listings immediately
            matches_found = await _search_and_show_matches(
                callback, state, _, user, db_session, requirement
            )
            
            if matches_found:
                # Matches found and shown to user
                return
        
        # No matches found - show message with recommended button
        await state.clear()
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"⭐ {_('buttons.recommended')}", callback_data="show_recommended")],
            [InlineKeyboardButton(text=_("buttons.start_over"), callback_data="start_over")],
        ])
        await callback.message.edit_text(
            _("requirement.created_no_matches"),
            reply_markup=keyboard,
        )
        
    except Exception as e:
        logger.error(f"Error creating requirement: {e}")
        await callback.message.edit_text(
            _("errors.general"),
            reply_markup=build_start_over_keyboard(_),
        )
        await state.clear()


async def _search_and_show_matches(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: AsyncSession,
    requirement: Requirement,
) -> bool:
    """Search for matching listings and show them with pagination. Returns True if matches found."""
    from app.models.listing import Listing, ListingStatusEnum, ListingMedia
    from app.models.match import Match, MatchStatusEnum
    from app.services.matching.scorer import MatchScorer, ListingData
    from sqlalchemy import and_
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    # Find active listings in the same category
    result = await db_session.execute(
        select(Listing).where(
            and_(
                Listing.category_id == requirement.category_id,
                Listing.status == ListingStatusEnum.ACTIVE,
            )
        )
    )
    listings = result.scalars().all()
    
    if not listings:
        return False
    
    # Calculate scores and create matches
    scorer = MatchScorer()
    matches_data = []
    
    for listing in listings:
        # Check if match already exists
        existing = await db_session.execute(
            select(Match).where(
                and_(
                    Match.listing_id == listing.id,
                    Match.requirement_id == requirement.id,
                )
            )
        )
        existing_match = existing.scalar_one_or_none()
        
        if existing_match:
            if existing_match.score >= 60:
                matches_data.append({
                    "match": existing_match,
                    "listing": listing,
                    "score": existing_match.score,
                })
            continue
        
        # Calculate score
        from app.services.matching.scorer import RequirementData
        listing_data = ListingData.from_model(listing)
        # Pass empty location_ids to avoid lazy loading error
        requirement_data = RequirementData.from_model(requirement, location_ids=[])
        score = scorer.calculate_total_score(listing_data, requirement_data)
        
        if score >= 60:
            # Create match
            match = Match(
                listing_id=listing.id,
                requirement_id=requirement.id,
                score=score,
                status=MatchStatusEnum.NEW,
            )
            db_session.add(match)
            matches_data.append({
                "match": match,
                "listing": listing,
                "score": score,
            })
    
    if matches_data:
        await db_session.commit()
    
    if not matches_data:
        return False
    
    # Sort by score descending
    matches_data.sort(key=lambda x: x["score"], reverse=True)
    
    # Store matches in state for pagination
    await state.update_data(
        search_matches=[str(m["match"].id) for m in matches_data],
        search_match_index=0,
        search_requirement_id=str(requirement.id),
    )
    
    # Show first match
    await _show_search_match(callback.message, state, _, db_session, edit=True)
    return True


async def _show_search_match(
    message: Any,
    state: FSMContext,
    _: Any,
    db_session: AsyncSession,
    edit: bool = True,
) -> None:
    """Show a single search match with pagination."""
    from app.models.match import Match
    from app.models.listing import Listing, ListingMedia
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
    
    data = await state.get_data()
    match_ids = data.get("search_matches", [])
    index = data.get("search_match_index", 0)
    
    if not match_ids:
        await message.answer(_("matches.empty"))
        await state.clear()
        return
    
    # Ensure index is in bounds
    index = max(0, min(index, len(match_ids) - 1))
    total = len(match_ids)
    
    # Get match and listing
    match_id = match_ids[index]
    result = await db_session.execute(
        select(Match, Listing)
        .join(Listing, Match.listing_id == Listing.id)
        .where(Match.id == match_id)
    )
    row = result.first()
    
    if not row:
        await state.clear()
        await message.answer(_("errors.general"))
        return
    
    match, listing = row
    
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
    text = f"<b>📊 {_('match.title')} {index + 1}/{total}</b> 🏠\n\n"
    text += f"🎯 {_('match.score')}: <b>{match.score}%</b>\n\n"
    text += f"<b>📋 {_('match.listing')}:</b>\n"
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
    if listing.is_vip:
        text += f"\n📌 {_('listing.vip')}\n"
    
    # Build keyboard
    buttons = []
    
    # Navigation row
    if total > 1:
        nav_row = []
        if index > 0:
            nav_row.append(InlineKeyboardButton(text=f"⬅️ {_('buttons.back_simple')}", callback_data="search_match:prev"))
        else:
            nav_row.append(InlineKeyboardButton(text=" ", callback_data="noop"))
        if index < total - 1:
            nav_row.append(InlineKeyboardButton(text=f"{_('buttons.next')} ➡️", callback_data="search_match:next"))
        else:
            nav_row.append(InlineKeyboardButton(text=" ", callback_data="noop"))
        buttons.append(nav_row)
    
    # Contact button
    buttons.append([
        InlineKeyboardButton(text=f"💬 {_('buttons.contact')}", callback_data=f"search_match:contact:{match.id}")
    ])
    
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
                try:
                    await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
                except Exception:
                    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            else:
                await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error showing search match: {e}")
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "search_match:prev")
async def search_match_prev(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Go to previous search match."""
    await callback.answer()
    data = await state.get_data()
    index = data.get("search_match_index", 0)
    matches = data.get("search_matches", [])
    
    new_index = max(0, index - 1)
    await state.update_data(search_match_index=new_index)
    
    if db_session:
        await _show_search_match(callback.message, state, _, db_session, edit=True)


@router.callback_query(F.data == "search_match:next")
async def search_match_next(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Go to next search match."""
    await callback.answer()
    data = await state.get_data()
    index = data.get("search_match_index", 0)
    matches = data.get("search_matches", [])
    
    new_index = min(len(matches) - 1, index + 1)
    await state.update_data(search_match_index=new_index)
    
    if db_session:
        await _show_search_match(callback.message, state, _, db_session, edit=True)


@router.callback_query(F.data.startswith("search_match:contact:"))
async def search_match_contact(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Contact seller from search match - send contact request."""
    await callback.answer()
    
    if not db_session:
        return
    
    match_id = callback.data.split(":")[2]
    
    from app.models.match import Match, MatchStatusEnum
    from app.models.listing import Listing
    from app.models.user import User
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    # Get match and listing
    result = await db_session.execute(
        select(Match, Listing)
        .join(Listing, Match.listing_id == Listing.id)
        .where(Match.id == match_id)
    )
    row = result.first()
    
    if not row:
        await callback.message.answer(_("errors.general"))
        return
    
    match, listing = row
    
    # Update match status to pending contact
    match.status = MatchStatusEnum.PENDING_CONTACT
    await db_session.commit()
    
    # Get seller
    seller_result = await db_session.execute(
        select(User).where(User.id == listing.user_id)
    )
    seller = seller_result.scalar_one_or_none()
    
    if seller and seller.telegram_id:
        # Send contact request to seller
        price = float(listing.price) if listing.price else 0
        request_text = (
            f"📩 {_('chat.contact_request')}\n\n"
            f"🏠 {_('listing.your_listing')}:\n"
            f"💰 {price:,.0f} AZN"
        )
        if listing.rooms:
            request_text += f" | {listing.rooms} комн."
        if listing.area:
            request_text += f" | {float(listing.area)} м²"
        request_text += f"\n\n🎯 {_('match.score')}: {match.score}%"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=f"✅ {_('buttons.accept')}", callback_data=f"cb_chat_accept:{match.id}"),
                InlineKeyboardButton(text=f"❌ {_('buttons.decline')}", callback_data=f"cb_chat_decline:{match.id}"),
            ]
        ])
        
        try:
            await callback.bot.send_message(
                chat_id=seller.telegram_id,
                text=request_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Failed to send contact request: {e}")
    
    # Notify buyer
    await callback.message.edit_text(
        _("chat.request_sent"),
        reply_markup=build_start_over_keyboard(_),
    )
    await state.clear()

async def get_or_create_category(session: AsyncSession, code: str) -> Category:

    category_names = {
        "private_house": ("Həyət evi / Bağ evi", "Частный дом / Дача", "Private House / Dacha"),
        "land": ("Torpaq sahəsi", "Земельный участок", "Land Plot"),
        "new_construction": ("Yeni tikili", "Новостройка", "New Construction"),
        "secondary": ("Köhnə tikili", "Вторичка", "Secondary Market"),
        "commercial": ("Kommersiya obyekti", "Коммерческий объект", "Commercial Property"),
        "office_warehouse": ("Ofis / Anbar", "Офис / Склад", "Office / Warehouse"),
        "villa": ("Villa / Kottec", "Вилла / Коттедж", "Villa / Cottage"),
        "other": ("Digər", "Другое", "Other"),
    }
    
    names = category_names.get(code, ("Digər", "Другое", "Other"))
    
    result = await session.execute(
        select(Category).where(Category.name_en == names[2])
    )
    category = result.scalar_one_or_none()
    
    if not category:
        category = Category(
            name_az=names[0],
            name_ru=names[1],
            name_en=names[2],
        )
        session.add(category)
        await session.flush()
    
    return category

@router.callback_query(NavigationCallback.filter(F.action == "cancel"), RequirementStates.confirmation)
async def cancel_requirement(callback: CallbackQuery, state: FSMContext, _: Any) -> None:

    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        _("buttons.cancelled"),
        reply_markup=build_start_over_keyboard(_),
    )

@router.callback_query(NavigationCallback.filter(F.action == "back"), RequirementStates.category)
async def back_to_deal_type_from_req(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    """Go back from category to deal type selection."""
    from app.bot.keyboards.builders import build_deal_type_keyboard
    from app.bot.states import OnboardingStates
    await callback.answer()
    data = await state.get_data()
    role = data.get("current_role", "buyer")
    market_type = data.get("market_type", "real_estate")
    await callback.message.edit_text(
        _("deal_type.select"),
        reply_markup=build_deal_type_keyboard(_, market_type, role)
    )
    await state.set_state(OnboardingStates.market_type_select)

@router.callback_query(NavigationCallback.filter(F.action == "back"), RequirementStates.location_type)
async def back_to_category(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await callback.message.edit_text(_("categories.select"), reply_markup=build_categories_keyboard(_))
    await state.set_state(RequirementStates.category)

@router.callback_query(NavigationCallback.filter(F.action == "back"), RequirementStates.location_select)
async def back_to_location_type(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await callback.message.edit_text(_("location.select_type"), reply_markup=build_location_type_keyboard(_))
    await state.set_state(RequirementStates.location_type)

@router.callback_query(NavigationCallback.filter(F.action == "back"), RequirementStates.district_select)
async def back_to_city_select(callback: CallbackQuery, state: FSMContext, _: Any, lang: str) -> None:
    """Go back from district select to city selection."""
    await callback.answer()
    await callback.message.edit_text(
        _("location.select_city"),
        reply_markup=build_city_keyboard_static(_, allow_multiple=False, lang=lang),
    )
    await state.set_state(RequirementStates.location_select)

@router.callback_query(NavigationCallback.filter(F.action == "back"), RequirementStates.metro_select)
async def back_to_district_select(callback: CallbackQuery, state: FSMContext, _: Any, lang: str) -> None:
    """Go back from metro select to district select."""
    await callback.answer()
    districts = get_districts("1")
    keyboard = build_district_keyboard_with_skip(districts, _, lang=lang)
    await callback.message.edit_text(
        _("location.select_district"),
        reply_markup=keyboard,
    )
    await state.set_state(RequirementStates.district_select)

@router.callback_query(LocationCallback.filter(F.type == "metro_back"), RequirementStates.metro_select)
async def metro_back_to_lines(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    """Go back from metro stations to metro lines."""
    await callback.answer()
    keyboard = build_metro_line_keyboard_with_skip(_)
    await callback.message.edit_text(
        _("metro.select_line"),
        reply_markup=keyboard,
    )

@router.callback_query(NavigationCallback.filter(F.action == "back"), RequirementStates.landmark_input)
async def back_to_metro_select(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    """Go back from landmark input to metro select."""
    await callback.answer()
    keyboard = build_metro_line_keyboard_with_skip(_)
    await callback.message.edit_text(
        _("metro.select_line"),
        reply_markup=keyboard,
    )
    await state.set_state(RequirementStates.metro_select)

@router.callback_query(NavigationCallback.filter(F.action == "back"), RequirementStates.payment_type)
async def back_to_price_range(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await callback.message.edit_text(_("form.price.enter_range"))
    await state.set_state(RequirementStates.price_range)

@router.callback_query(NavigationCallback.filter(F.action == "back"), RequirementStates.down_payment)
async def back_to_payment_type(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await callback.message.edit_text(_("form.payment.select"), reply_markup=build_payment_type_keyboard(_))
    await state.set_state(RequirementStates.payment_type)

@router.callback_query(NavigationCallback.filter(F.action == "back"), RequirementStates.floor_preferences)
async def back_to_floor_range(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await callback.message.edit_text(_("form.floor.enter_range"))
    await state.set_state(RequirementStates.floor_range)

@router.callback_query(NavigationCallback.filter(F.action == "back"), RequirementStates.renovation)
async def back_to_floor_prefs(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    data = await state.get_data()
    if data.get("category") in ("land", "private_house"):
        await callback.message.edit_text(_("form.area.enter_range"))
        await state.set_state(RequirementStates.area_range)
    else:
        prefs = data.get("floor_preferences", {})
        await callback.message.edit_text(_("form.floor.preferences"), reply_markup=build_floor_preferences_keyboard(_, selected=prefs))
        await state.set_state(RequirementStates.floor_preferences)

@router.callback_query(NavigationCallback.filter(F.action == "back"), RequirementStates.documents)
async def back_to_renovation(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    data = await state.get_data()
    reno = data.get("renovation", [])
    await callback.message.edit_text(_("form.renovation.select"), reply_markup=build_renovation_keyboard(_, allow_multiple=True, selected=reno))
    await state.set_state(RequirementStates.renovation)

@router.callback_query(NavigationCallback.filter(F.action == "back"), RequirementStates.utilities)
async def back_to_documents(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    data = await state.get_data()
    docs = data.get("documents", [])
    await callback.message.edit_text(_("form.documents.select"), reply_markup=build_documents_keyboard(_, allow_multiple=True, selected=docs))
    await state.set_state(RequirementStates.documents)

@router.callback_query(NavigationCallback.filter(F.action == "back"), RequirementStates.heating)
async def back_to_utilities(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await callback.message.edit_text(_("form.utilities.gas"), reply_markup=build_utilities_keyboard(_, "gas"))
    await state.set_state(RequirementStates.utilities)

@router.callback_query(NavigationCallback.filter(F.action == "back"), RequirementStates.property_age)
async def back_to_heating(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    data = await state.get_data()
    heat = data.get("heating", [])
    await callback.message.edit_text(_("form.heating.select"), reply_markup=build_heating_keyboard(_, allow_multiple=True, selected=heat))
    await state.set_state(RequirementStates.heating)

@router.callback_query(NavigationCallback.filter(F.action == "back"), RequirementStates.comments)
async def back_to_property_age(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    data = await state.get_data()
    ages = data.get("property_age", [])
    await callback.message.edit_text(_("form.age.select"), reply_markup=build_property_age_keyboard(_, allow_multiple=True, selected=ages))
    await state.set_state(RequirementStates.property_age)

@router.callback_query(NavigationCallback.filter(F.action == "back"), RequirementStates.confirmation)
async def back_to_comments(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await callback.message.edit_text(_("form.description.enter_comments"), reply_markup=build_skip_keyboard(_))
    await state.set_state(RequirementStates.comments)
