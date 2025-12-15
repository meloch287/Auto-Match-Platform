import logging
from decimal import Decimal
from typing import Any, Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reference import Category
from app.models.requirement import Requirement

logger = logging.getLogger(__name__)

from app.bot.keyboards.builders import (
    build_categories_keyboard,
    build_location_type_keyboard,
    build_city_keyboard,
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
    cities = await get_cities()
    await callback.message.edit_text(
        _("location.select_city"),
        reply_markup=build_city_keyboard(cities, _, lang),
    )
    await state.set_state(RequirementStates.location_select)

@router.callback_query(LocationCallback.filter(F.type == "district"), RequirementStates.location_select)
async def location_district(callback: CallbackQuery, callback_data: LocationCallback, state: FSMContext, _: Any, lang: str) -> None:
    await callback.answer()
    await state.update_data(city_id=callback_data.id)
    districts = await get_districts(callback_data.id)
    data = await state.get_data()
    selected = data.get("selected_locations", [])
    await callback.message.edit_text(
        f"{_('location.select_district')}\n{_('location.select_multiple')}\n✅ {len(selected)}/5",
        reply_markup=build_district_keyboard(districts, _, lang, allow_multiple=True, selected=selected),
    )

@router.callback_query(LocationCallback.filter(F.type == "select"), RequirementStates.location_select)
async def toggle_district(callback: CallbackQuery, callback_data: LocationCallback, state: FSMContext, _: Any, lang: str) -> None:
    data = await state.get_data()
    selected = data.get("selected_locations", [])
    
    if callback_data.id in selected:
        selected.remove(callback_data.id)
    elif len(selected) < 5:
        selected.append(callback_data.id)
    else:
        await callback.answer(_("location.max_5"), show_alert=True)
        return
    
    await callback.answer()
    await state.update_data(selected_locations=selected)
    
    districts = await get_districts(data.get("city_id", "1"))
    await callback.message.edit_text(
        f"{_('location.select_district')}\n{_('location.select_multiple')}\n✅ {len(selected)}/5",
        reply_markup=build_district_keyboard(districts, _, lang, allow_multiple=True, selected=selected),
    )

def parse_range(text: str) -> tuple[float | None, float | None]:
    """Parse range input like '12 - 34' or '12-34' into (min, max) tuple."""
    text = text.replace(" ", "").replace(",", ".")
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
    stations = await get_metro_stations(callback_data.id)
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
    lines.append(category_name)
    lines.append(f"{price_min:,.0f} - {price_max:,.0f} {currency}")
    lines.append(payment_name)
    
    if data.get('down_payment'):
        lines.append(f"{data.get('down_payment'):,.0f} {currency}")
    
    if data.get('category') != 'land':
        rooms_min = data.get('rooms_min', '-')
        rooms_max = data.get('rooms_max', '-')
        lines.append(f"{rooms_min} - {rooms_max} rooms")
    
    area_min = data.get('area_min', 0)
    area_max = data.get('area_max', 0)
    lines.append(f"{area_min} - {area_max} m2")
    
    if data.get('floor_min') is not None:
        floor_min = data.get('floor_min', '-')
        floor_max = data.get('floor_max', '-')
        lines.append(f"{floor_min} - {floor_max} floor")
    
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
    """Confirm and submit requirement to database."""
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
                from app.models.requirement import RequirementPaymentTypeEnum, RequirementStatusEnum
                payment_map = {
                    "cash": RequirementPaymentTypeEnum.CASH,
                    "credit": RequirementPaymentTypeEnum.CREDIT,
                    "both": RequirementPaymentTypeEnum.BOTH,
                    "any": RequirementPaymentTypeEnum.ANY,
                }
                payment_type_enum = payment_map.get(payment_type_str)
            
            requirement = Requirement(
                user_id=user.id,
                category_id=category.id,
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
            
            logger.info(f"Created requirement {requirement.id} for user {user.id}")
        
        await state.clear()
        
        await callback.message.edit_text(
            _("requirement.created"),
            reply_markup=build_start_over_keyboard(_),
        )
        
    except Exception as e:
        logger.error(f"Error creating requirement: {e}")
        await callback.message.edit_text(
            _("errors.general"),
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
async def back_to_role_from_req(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    from app.bot.keyboards.builders import build_role_keyboard
    from app.bot.states import OnboardingStates
    await callback.answer()
    await callback.message.edit_text(_("roles.select"), reply_markup=build_role_keyboard(_))
    await state.set_state(OnboardingStates.role_select)

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

@router.callback_query(NavigationCallback.filter(F.action == "back"), RequirementStates.payment_type)
async def back_to_price_max(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await callback.message.edit_text(_("form.price.enter_max"))
    await state.set_state(RequirementStates.price_max)

@router.callback_query(NavigationCallback.filter(F.action == "back"), RequirementStates.down_payment)
async def back_to_payment_type(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await callback.message.edit_text(_("form.payment.select"), reply_markup=build_payment_type_keyboard(_))
    await state.set_state(RequirementStates.payment_type)

@router.callback_query(NavigationCallback.filter(F.action == "back"), RequirementStates.floor_preferences)
async def back_to_floor_max(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await callback.message.edit_text(_("form.floor.enter_max"))
    await state.set_state(RequirementStates.floor_max)

@router.callback_query(NavigationCallback.filter(F.action == "back"), RequirementStates.renovation)
async def back_to_floor_prefs(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    data = await state.get_data()
    if data.get("category") in ("land", "private_house"):
        await callback.message.edit_text(_("form.area.enter_max"))
        await state.set_state(RequirementStates.area_max)
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

async def get_cities() -> list[dict]:

    return [
        {"id": "1", "name_az": "Bakı", "name_ru": "Баку", "name_en": "Baku"},
        {"id": "2", "name_az": "Sumqayıt", "name_ru": "Сумгаит", "name_en": "Sumgait"},
        {"id": "3", "name_az": "Gəncə", "name_ru": "Гянджа", "name_en": "Ganja"},
        {"id": "4", "name_az": "Lənkəran", "name_ru": "Ленкорань", "name_en": "Lankaran"},
        {"id": "5", "name_az": "Mingəçevir", "name_ru": "Мингечевир", "name_en": "Mingachevir"},
    ]

async def get_districts(city_id: str) -> list[dict]:

    if city_id == "1":
        return [
            {"id": "11", "name_az": "Nəsimi", "name_ru": "Насими", "name_en": "Nasimi"},
            {"id": "12", "name_az": "Yasamal", "name_ru": "Ясамал", "name_en": "Yasamal"},
            {"id": "13", "name_az": "Nizami", "name_ru": "Низами", "name_en": "Nizami"},
            {"id": "14", "name_az": "Xətai", "name_ru": "Хатаи", "name_en": "Khatai"},
            {"id": "15", "name_az": "Binəqədi", "name_ru": "Бинагади", "name_en": "Binagadi"},
            {"id": "16", "name_az": "Sabunçu", "name_ru": "Сабунчу", "name_en": "Sabunchu"},
            {"id": "17", "name_az": "Suraxanı", "name_ru": "Сураханы", "name_en": "Surakhani"},
            {"id": "18", "name_az": "Qaradağ", "name_ru": "Гарадаг", "name_en": "Garadagh"},
        ]
    return [{"id": f"{city_id}1", "name_az": "Mərkəz", "name_ru": "Центр", "name_en": "Center"}]

METRO_STATIONS = {
    "green": [
        {"id": "g1", "name_az": "İçərişəhər", "name_ru": "Ичеришехер", "name_en": "Icherisheher"},
        {"id": "g2", "name_az": "Sahil", "name_ru": "Сахил", "name_en": "Sahil"},
        {"id": "g3", "name_az": "Cəfər Cabbarlı", "name_ru": "Джафар Джаббарлы", "name_en": "Jafar Jabbarly"},
        {"id": "g4", "name_az": "28 May", "name_ru": "28 Мая", "name_en": "28 May"},
        {"id": "g5", "name_az": "Nizami Gəncəvi", "name_ru": "Низами Гянджеви", "name_en": "Nizami Ganjavi"},
        {"id": "g6", "name_az": "Elmlər Akademiyası", "name_ru": "Эмляр академиясы", "name_en": "Academy of Sciences"},
        {"id": "g7", "name_az": "İnşaatçılar", "name_ru": "Иншаатчылар", "name_en": "Inshaatchilar"},
        {"id": "g8", "name_az": "20 Yanvar", "name_ru": "20 Января", "name_en": "20 January"},
        {"id": "g9", "name_az": "Memar Əcəmi", "name_ru": "Мемар Аджеми", "name_en": "Memar Ajami"},
        {"id": "g10", "name_az": "Nəsimi", "name_ru": "Насими", "name_en": "Nasimi"},
        {"id": "g11", "name_az": "Azadlıq prospekti", "name_ru": "Проспект Азадлыг", "name_en": "Azadlig Avenue"},
        {"id": "g12", "name_az": "Dərnəgül", "name_ru": "Дарнагюль", "name_en": "Darnagul"},
        {"id": "g13", "name_az": "Bakmil", "name_ru": "Бакмил", "name_en": "Bakmil"},
        {"id": "g14", "name_az": "Gənclik", "name_ru": "Гянджлик", "name_en": "Ganjlik"},
        {"id": "g15", "name_az": "Nəriman Nərimanov", "name_ru": "Нариман Нариманов", "name_en": "Nariman Narimanov"},
        {"id": "g16", "name_az": "Ulduz", "name_ru": "Улдуз", "name_en": "Ulduz"},
        {"id": "g17", "name_az": "Koroğlu", "name_ru": "Кёроглу", "name_en": "Koroglu"},
        {"id": "g18", "name_az": "Qara Qarayev", "name_ru": "Кара Караев", "name_en": "Gara Garayev"},
        {"id": "g19", "name_az": "Neftçilər", "name_ru": "Нефтчиляр", "name_en": "Neftchilar"},
        {"id": "g20", "name_az": "Xalqlar Dostluğu", "name_ru": "Халглар Достлугу", "name_en": "Khalglar Dostlugu"},
        {"id": "g21", "name_az": "Əhmədli", "name_ru": "Ахмедлы", "name_en": "Ahmadli"},
        {"id": "g22", "name_az": "Həzi Aslanov", "name_ru": "Ази Асланов", "name_en": "Hazi Aslanov"},
    ],
    "red": [
        {"id": "r1", "name_az": "İçərişəhər", "name_ru": "Ичеришехер", "name_en": "Icherisheher"},
        {"id": "r2", "name_az": "Sahil", "name_ru": "Сахил", "name_en": "Sahil"},
        {"id": "r3", "name_az": "Cəfər Cabbarlı", "name_ru": "Джафар Джаббарлы", "name_en": "Jafar Jabbarly"},
        {"id": "r4", "name_az": "28 May", "name_ru": "28 Мая", "name_en": "28 May"},
        {"id": "r5", "name_az": "Gənclik", "name_ru": "Гянджлик", "name_en": "Ganjlik"},
        {"id": "r6", "name_az": "Nəriman Nərimanov", "name_ru": "Нариман Нариманов", "name_en": "Nariman Narimanov"},
        {"id": "r7", "name_az": "Ulduz", "name_ru": "Улдуз", "name_en": "Ulduz"},
        {"id": "r8", "name_az": "Koroğlu", "name_ru": "Кёроглу", "name_en": "Koroglu"},
        {"id": "r9", "name_az": "Qara Qarayev", "name_ru": "Кара Караев", "name_en": "Gara Garayev"},
        {"id": "r10", "name_az": "Neftçilər", "name_ru": "Нефтчиляр", "name_en": "Neftchilar"},
        {"id": "r11", "name_az": "Xalqlar Dostluğu", "name_ru": "Халглар Достлугу", "name_en": "Khalglar Dostlugu"},
        {"id": "r12", "name_az": "Əhmədli", "name_ru": "Ахмедлы", "name_en": "Ahmadli"},
        {"id": "r13", "name_az": "Həzi Aslanov", "name_ru": "Ази Асланов", "name_en": "Hazi Aslanov"},
    ],
    "purple": [
        {"id": "p1", "name_az": "Xocəsən", "name_ru": "Ходжасан", "name_en": "Khojasan"},
        {"id": "p2", "name_az": "Avtovağzal", "name_ru": "Автовокзал", "name_en": "Avtovagzal"},
        {"id": "p3", "name_az": "Memar Əcəmi", "name_ru": "Мемар Аджеми", "name_en": "Memar Ajami"},
        {"id": "p4", "name_az": "8 Noyabr", "name_ru": "8 Ноября", "name_en": "8 November"},
    ],
}

async def get_metro_stations(line: str) -> list[dict]:

    return METRO_STATIONS.get(line, [])
