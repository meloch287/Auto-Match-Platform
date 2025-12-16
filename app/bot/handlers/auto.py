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


def build_back_keyboard(_: Any) -> Any:
    """Build keyboard with only back button for text input steps."""
    builder = InlineKeyboardBuilder()
    builder.button(text=_("buttons.back"), callback_data="auto:back")
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


# Popular car brands from turbo.az
CAR_BRANDS = [
    "Mercedes-Benz", "BMW", "Toyota", "Lexus", "Audi",
    "Volkswagen", "Hyundai", "Kia", "Nissan", "Honda",
    "Chevrolet", "Ford", "Mazda", "Mitsubishi", "Porsche",
    "Land Rover", "Jeep", "Opel", "Peugeot", "Renault",
    "Skoda", "Subaru", "Suzuki", "Volvo", "VAZ (Lada)",
]

# Popular models by brand
CAR_MODELS = {
    "Mercedes-Benz": ["C-Class", "E-Class", "S-Class", "GLE", "GLC", "A-Class", "CLA", "GLA", "G-Class", "ML"],
    "BMW": ["3 Series", "5 Series", "7 Series", "X3", "X5", "X6", "X7", "1 Series", "4 Series", "X1"],
    "Toyota": ["Camry", "Corolla", "RAV4", "Land Cruiser", "Prado", "Highlander", "Prius", "Yaris", "C-HR", "Avalon"],
    "Lexus": ["RX", "ES", "NX", "LX", "IS", "GX", "LS", "UX", "RC", "LC"],
    "Audi": ["A4", "A6", "A8", "Q5", "Q7", "Q3", "A3", "Q8", "A5", "e-tron"],
    "Volkswagen": ["Passat", "Golf", "Tiguan", "Polo", "Jetta", "Touareg", "Arteon", "T-Roc", "ID.4", "Atlas"],
    "Hyundai": ["Tucson", "Santa Fe", "Elantra", "Sonata", "Accent", "Creta", "Palisade", "Kona", "i30", "i20"],
    "Kia": ["Sportage", "Sorento", "Cerato", "Optima", "Rio", "Seltos", "Carnival", "Stinger", "Soul", "Telluride"],
    "Nissan": ["Qashqai", "X-Trail", "Patrol", "Altima", "Sentra", "Juke", "Murano", "Pathfinder", "Kicks", "Note"],
    "Honda": ["CR-V", "Civic", "Accord", "HR-V", "Pilot", "City", "Jazz", "Odyssey", "Passport", "Insight"],
    "Chevrolet": ["Malibu", "Cruze", "Captiva", "Tahoe", "Camaro", "Equinox", "Traverse", "Spark", "Trax", "Blazer"],
    "Ford": ["Focus", "Mustang", "Explorer", "Escape", "F-150", "Ranger", "Edge", "Bronco", "Fusion", "Fiesta"],
    "Mazda": ["CX-5", "3", "6", "CX-30", "CX-9", "MX-5", "CX-3", "2", "CX-50", "CX-60"],
    "Mitsubishi": ["Outlander", "Pajero", "ASX", "L200", "Eclipse Cross", "Lancer", "Montero", "Mirage", "Xpander"],
    "Porsche": ["Cayenne", "Macan", "Panamera", "911", "Taycan", "Boxster", "Cayman", "718"],
    "Land Rover": ["Range Rover", "Discovery", "Defender", "Evoque", "Velar", "Sport", "Freelander"],
    "Jeep": ["Grand Cherokee", "Wrangler", "Compass", "Cherokee", "Renegade", "Gladiator"],
    "Opel": ["Astra", "Insignia", "Corsa", "Mokka", "Crossland", "Grandland", "Zafira", "Vectra"],
    "Peugeot": ["3008", "5008", "208", "308", "508", "2008", "Partner", "Rifter"],
    "Renault": ["Duster", "Logan", "Sandero", "Megane", "Captur", "Kadjar", "Koleos", "Clio", "Arkana"],
    "Skoda": ["Octavia", "Superb", "Kodiaq", "Karoq", "Rapid", "Fabia", "Kamiq", "Scala"],
    "Subaru": ["Forester", "Outback", "XV", "Impreza", "Legacy", "WRX", "Crosstrek", "Ascent"],
    "Suzuki": ["Vitara", "SX4", "Swift", "Jimny", "Ignis", "Baleno", "S-Cross"],
    "Volvo": ["XC90", "XC60", "XC40", "S60", "S90", "V60", "V90", "C40"],
    "VAZ (Lada)": ["Vesta", "Granta", "Niva", "XRAY", "Largus", "Priora", "Kalina", "2107", "2110", "2114"],
}

# Azerbaijan cities
AZ_CITIES = [
    "Bakı", "Gəncə", "Sumqayıt", "Mingəçevir", "Şirvan", "Naxçıvan", "Şəki", "Lənkəran",
    "Yevlax", "Xankəndi", "Quba", "Qusar", "Şamaxı", "Qəbələ", "Zaqatala", "Balakən",
    "Ağdam", "Ağdaş", "Ağcabədi", "Ağstafa", "Ağsu", "Astara", "Babək", "Bərdə",
    "Beyləqan", "Biləsuvar", "Cəbrayıl", "Cəlilabad", "Culfa", "Daşkəsən", "Füzuli",
    "Gədəbəy", "Goranboy", "Göyçay", "Göygöl", "Hacıqabul", "İmişli", "İsmayıllı",
    "Kəlbəcər", "Kürdəmir", "Laçın", "Lerik", "Masallı", "Neftçala", "Oğuz", "Ordubad",
    "Qax", "Qazax", "Qobustan", "Qubadlı", "Saatlı", "Sabirabad", "Salyan", "Samux",
    "Siyəzən", "Şabran", "Şahbuz", "Şəmkir", "Şərur", "Şuşa", "Tərtər", "Tovuz",
    "Ucar", "Xaçmaz", "Xızı", "Xocavənd", "Yardımlı", "Zəngilan", "Zərdab",
]


def build_city_keyboard_auto(_: Any, page: int = 0) -> Any:
    """Build city selection keyboard with pagination."""
    builder = InlineKeyboardBuilder()
    
    # 12 cities per page
    page_size = 12
    start = page * page_size
    end = start + page_size
    cities_page = AZ_CITIES[start:end]
    
    for city in cities_page:
        builder.button(text=city, callback_data=f"auto_city:{city}")
    
    builder.adjust(2)
    
    # Pagination
    nav_buttons = []
    if page > 0:
        nav_buttons.append(("⬅️", f"auto_city_page:{page-1}"))
    if end < len(AZ_CITIES):
        nav_buttons.append(("➡️", f"auto_city_page:{page+1}"))
    
    if nav_buttons:
        builder.row()
        for text, data in nav_buttons:
            builder.button(text=text, callback_data=data)
    
    builder.row()
    builder.button(text=_("buttons.back"), callback_data="auto:back")
    
    return builder.as_markup()


def build_model_keyboard(_: Any, brand: str, page: int = 0) -> Any:
    """Build model selection keyboard with pagination."""
    builder = InlineKeyboardBuilder()
    
    models = CAR_MODELS.get(brand, [])
    if not models:
        # If no models defined, allow text input
        builder.button(text=_("buttons.skip"), callback_data="auto:skip_model")
        builder.row()
        builder.button(text=_("buttons.back"), callback_data="auto:back")
        return builder.as_markup()
    
    # 10 models per page
    page_size = 10
    start = page * page_size
    end = start + page_size
    models_page = models[start:end]
    
    for model in models_page:
        builder.button(text=model, callback_data=f"auto_model:{model}")
    
    builder.adjust(2)
    
    # Pagination
    nav_buttons = []
    if page > 0:
        nav_buttons.append(("⬅️", f"auto_model_page:{page-1}"))
    if end < len(models):
        nav_buttons.append(("➡️", f"auto_model_page:{page+1}"))
    
    if nav_buttons:
        builder.row()
        for text, data in nav_buttons:
            builder.button(text=text, callback_data=data)
    
    builder.row()
    builder.button(text=_("buttons.back"), callback_data="auto:back")
    
    return builder.as_markup()


def build_model_keyboard_req(_: Any, brand: str, page: int = 0) -> Any:
    """Build model selection keyboard for requirement (with skip button)."""
    builder = InlineKeyboardBuilder()
    
    models = CAR_MODELS.get(brand, [])
    if not models:
        # If no models defined, show skip button
        builder.button(text=f"⏭️ {_('buttons.skip')}", callback_data="auto:skip")
        builder.row()
        builder.button(text=_("buttons.back"), callback_data="auto:back")
        return builder.as_markup()
    
    # 10 models per page
    page_size = 10
    start = page * page_size
    end = start + page_size
    models_page = models[start:end]
    
    for model in models_page:
        builder.button(text=model, callback_data=f"auto_model_req:{model}")
    
    builder.adjust(2)
    
    # Pagination
    nav_buttons = []
    if page > 0:
        nav_buttons.append(("⬅️", f"auto_model_req_page:{page-1}"))
    if end < len(models):
        nav_buttons.append(("➡️", f"auto_model_req_page:{page+1}"))
    
    if nav_buttons:
        builder.row()
        for text, data in nav_buttons:
            builder.button(text=text, callback_data=data)
    
    # Skip and back buttons
    builder.row()
    builder.button(text=f"⏭️ {_('buttons.skip')}", callback_data="auto:skip")
    builder.row()
    builder.button(text=_("buttons.back"), callback_data="auto:back")
    
    return builder.as_markup()


def build_brand_keyboard(_: Any, selected: list[str] = None, page: int = 0) -> Any:
    """Build car brand selection keyboard with pagination."""
    builder = InlineKeyboardBuilder()
    selected = selected or []
    
    # 10 brands per page
    page_size = 10
    start = page * page_size
    end = start + page_size
    brands_page = CAR_BRANDS[start:end]
    
    for brand in brands_page:
        # Show icon only for selected items
        if brand in selected:
            builder.button(
                text=f"🔴 {brand}",
                callback_data=f"auto_brand:{brand}"
            )
        else:
            builder.button(
                text=brand,
                callback_data=f"auto_brand:{brand}"
            )
    
    builder.adjust(2)
    
    # Pagination
    nav_buttons = []
    if page > 0:
        nav_buttons.append(("⬅️", f"auto_brand_page:{page-1}"))
    if end < len(CAR_BRANDS):
        nav_buttons.append(("➡️", f"auto_brand_page:{page+1}"))
    
    if nav_buttons:
        builder.row()
        for text, data in nav_buttons:
            builder.button(text=text, callback_data=data)
    
    # Confirm button - only show when something is selected
    if selected:
        builder.row()
        builder.button(
            text=f"✅ {_('buttons.confirm')} ({len(selected)})",
            callback_data="auto_brand:confirm"
        )
    
    builder.row()
    builder.button(text=_("buttons.back"), callback_data="auto:back")
    
    return builder.as_markup()


# ============ BRAND SELECTION HANDLERS ============

@router.callback_query(F.data.startswith("auto_brand:"), AutoListingStates.brand)
async def select_listing_brand(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Handle brand selection for listing."""
    action = callback.data.split(":")[1]
    await callback.answer()
    
    if action == "confirm":
        # Should not happen for listing (single brand)
        return
    
    # Single brand selected for listing
    brand = action
    await state.update_data(brand=brand)
    await callback.message.edit_text(
        _("auto.enter_model"),
        reply_markup=build_model_keyboard(_, brand),
    )
    await state.set_state(AutoListingStates.model)


@router.callback_query(F.data.startswith("auto_brand_page:"), AutoListingStates.brand)
async def listing_brand_page(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Handle brand pagination for listing."""
    page = int(callback.data.split(":")[1])
    await callback.answer()
    await callback.message.edit_text(
        _("auto.enter_brand"),
        reply_markup=build_brand_keyboard(_, page=page),
    )


@router.callback_query(F.data.startswith("auto_brand:"), AutoRequirementStates.brands)
async def select_requirement_brand(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Handle brand selection for requirement (single select like listing)."""
    action = callback.data.split(":")[1]
    await callback.answer()
    
    if action == "confirm":
        # Should not happen for single brand selection
        return
    
    # Single brand selected - go directly to model input
    brand = action
    
    # Get year range from DB for selected brand
    db_year_min, db_year_max = 2000, 2025  # defaults
    if db_session:
        from sqlalchemy import select, func
        from app.models.auto import AutoListing
        
        query = select(
            func.min(AutoListing.year),
            func.max(AutoListing.year)
        ).where(
            AutoListing.brand == brand,
            AutoListing.status == AutoStatusEnum.ACTIVE
        )
        result = await db_session.execute(query)
        row = result.first()
        if row and row[0] and row[1]:
            db_year_min, db_year_max = row[0], row[1]
    
    await state.update_data(brand=brand, brands=[brand], db_year_min=db_year_min, db_year_max=db_year_max)
    
    # Go to model input with keyboard
    await callback.message.edit_text(
        _("auto.enter_model"),
        reply_markup=build_model_keyboard_req(_, brand),
    )
    await state.set_state(AutoRequirementStates.models)


@router.callback_query(F.data.startswith("auto_brand_page:"), AutoRequirementStates.brands)
async def requirement_brand_page(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Handle brand pagination for requirement."""
    page = int(callback.data.split(":")[1])
    await callback.answer()
    
    await state.update_data(brand_page=page)
    
    await callback.message.edit_text(
        _("auto.enter_brand"),
        reply_markup=build_brand_keyboard(_, page=page),
    )


# ============ AUTO LISTING BACK HANDLERS ============

@router.callback_query(F.data == "auto:back", AutoListingStates.model)
async def back_from_model(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Go back from model to brand selection."""
    await callback.answer()
    await callback.message.edit_text(
        _("auto.enter_brand"),
        reply_markup=build_brand_keyboard(_),
    )
    await state.set_state(AutoListingStates.brand)


@router.callback_query(F.data == "auto:back", AutoListingStates.year)
async def back_from_year(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Go back from year to model."""
    await callback.answer()
    data = await state.get_data()
    brand = data.get("brand", "")
    await callback.message.edit_text(
        _("auto.enter_model"),
        reply_markup=build_model_keyboard(_, brand),
    )
    await state.set_state(AutoListingStates.model)


@router.callback_query(F.data == "auto:back", AutoListingStates.mileage)
async def back_from_mileage(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Go back from mileage to year."""
    await callback.answer()
    await callback.message.edit_text(
        _("auto.enter_year"),
        reply_markup=build_back_keyboard(_),
    )
    await state.set_state(AutoListingStates.year)


@router.callback_query(F.data == "auto:back", AutoListingStates.price)
async def back_from_price(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Go back from price to previous step."""
    await callback.answer()
    data = await state.get_data()
    deal_type = data.get("deal_type", "sale")
    
    if deal_type == "rent":
        # Back to rental class
        await callback.message.edit_text(
            _("auto.select_rental_class"),
            reply_markup=build_rental_class_keyboard(_),
        )
        await state.set_state(AutoListingStates.body_type)
    else:
        # Back to fuel type
        await callback.message.edit_text(
            _("auto.select_fuel"),
            reply_markup=build_fuel_type_keyboard(_),
        )
        await state.set_state(AutoListingStates.fuel_type)


@router.callback_query(F.data == "auto:back", AutoListingStates.city)
async def back_from_city(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Go back from city to price."""
    await callback.answer()
    data = await state.get_data()
    deal_type = data.get("deal_type", "sale")
    
    if deal_type == "rent":
        await callback.message.edit_text(
            _("auto.enter_price_per_day"),
            reply_markup=build_back_keyboard(_),
        )
    else:
        await callback.message.edit_text(
            _("auto.enter_price"),
            reply_markup=build_back_keyboard(_),
        )
    await state.set_state(AutoListingStates.price)


# ============ AUTO LISTING HANDLERS (SELLER) ============

@router.message(AutoListingStates.brand)
async def process_auto_brand(
    message: Message,
    state: FSMContext,
    _: Any,
) -> None:
    """Process auto brand text input (fallback)."""
    brand = message.text.strip()
    if len(brand) < 2 or len(brand) > 50:
        await message.answer(_("errors.invalid_input"))
        return
    
    await state.update_data(brand=brand)
    await message.answer(
        _("auto.enter_model"),
        reply_markup=build_back_keyboard(_),
    )
    await state.set_state(AutoListingStates.model)


@router.callback_query(F.data.startswith("auto_model:"), AutoListingStates.model)
async def select_listing_model(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Handle model selection for listing."""
    model = callback.data.split(":", 1)[1]
    await callback.answer()
    
    await state.update_data(model=model)
    await callback.message.edit_text(
        _("auto.enter_year"),
        reply_markup=build_back_keyboard(_),
    )
    await state.set_state(AutoListingStates.year)


@router.callback_query(F.data.startswith("auto_model_page:"), AutoListingStates.model)
async def listing_model_page(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Handle model pagination for listing."""
    page = int(callback.data.split(":")[1])
    await callback.answer()
    data = await state.get_data()
    brand = data.get("brand", "")
    await callback.message.edit_text(
        _("auto.enter_model"),
        reply_markup=build_model_keyboard(_, brand, page=page),
    )


@router.message(AutoListingStates.model)
async def process_auto_model_text(
    message: Message,
    state: FSMContext,
    _: Any,
) -> None:
    """Process auto model text input (fallback)."""
    model = message.text.strip()
    if len(model) < 1 or len(model) > 50:
        await message.answer(_("errors.invalid_input"))
        return
    
    await state.update_data(model=model)
    await message.answer(
        _("auto.enter_year"),
        reply_markup=build_back_keyboard(_),
    )
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
        await message.answer(
            _("auto.enter_mileage"),
            reply_markup=build_back_keyboard(_),
        )
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
    
    await callback.message.edit_text(
        _("auto.enter_price"),
        reply_markup=build_back_keyboard(_),
    )
    await state.set_state(AutoListingStates.price)


@router.callback_query(F.data.startswith("auto_rental_class:"), AutoListingStates.body_type)
async def process_rental_class(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Process rental class selection for listing."""
    rental_class = callback.data.split(":")[1]
    await callback.answer()
    await state.update_data(rental_class=rental_class)
    
    await callback.message.edit_text(
        _("auto.enter_price_per_day"),
        reply_markup=build_back_keyboard(_),
    )
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
    await message.answer(
        _("auto.enter_city"),
        reply_markup=build_city_keyboard_auto(_),
    )
    await state.set_state(AutoListingStates.city)


@router.callback_query(F.data.startswith("auto_city:"), AutoListingStates.city)
async def select_listing_city(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Handle city selection for listing."""
    city = callback.data.split(":", 1)[1]
    await callback.answer()
    
    await state.update_data(city=city)
    await callback.message.edit_text(
        _("auto.enter_description"),
        reply_markup=build_skip_keyboard(_),
    )
    await state.set_state(AutoListingStates.description)


@router.callback_query(F.data.startswith("auto_city_page:"), AutoListingStates.city)
async def listing_city_page(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Handle city pagination for listing."""
    page = int(callback.data.split(":")[1])
    await callback.answer()
    await callback.message.edit_text(
        _("auto.enter_city"),
        reply_markup=build_city_keyboard_auto(_, page=page),
    )


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
            f"<b>{_('auto.mileage')}:</b> {mileage:,} km\n"
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
    
    # Save photos
    photos = data.get("photos", [])
    if photos:
        for i, photo_file_id in enumerate(photos):
            await service.add_media(
                listing_id=listing.id,
                url=photo_file_id,
                order=i,
            )
        logger.info(f"Saved {len(photos)} photos for auto listing {listing.id}")
    
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


# ============ AUTO REQUIREMENT BACK HANDLERS ============

@router.callback_query(F.data == "auto:back", AutoRequirementStates.year_range)
async def back_from_req_year_range(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Go back from year range to model input."""
    await callback.answer()
    data = await state.get_data()
    brand = data.get("brand", "")
    await callback.message.edit_text(
        _("auto.enter_model"),
        reply_markup=build_model_keyboard_req(_, brand),
    )
    await state.set_state(AutoRequirementStates.models)


@router.callback_query(F.data == "auto:back", AutoRequirementStates.price_range)
async def back_from_req_price_range(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Go back from price range to year range."""
    await callback.answer()
    
    # Get year range from DB for selected brands
    data = await state.get_data()
    selected = data.get("brands", [])
    db_year_min = data.get("db_year_min", 2000)
    db_year_max = data.get("db_year_max", 2025)
    
    await callback.message.edit_text(
        f"📅 {_('auto.enter_year_range_dynamic').format(min=db_year_min, max=db_year_max)}",
        reply_markup=build_back_keyboard(_),
    )
    await state.set_state(AutoRequirementStates.year_range)


@router.callback_query(F.data == "auto:back", AutoRequirementStates.mileage_max)
async def back_from_req_mileage(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Go back from mileage to price range."""
    await callback.answer()
    await callback.message.edit_text(
        _("auto.enter_price_range"),
        reply_markup=build_back_keyboard(_),
    )
    await state.set_state(AutoRequirementStates.price_range)


@router.callback_query(F.data == "auto:back", AutoRequirementStates.city)
async def back_from_req_city(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Go back from city to previous step."""
    await callback.answer()
    data = await state.get_data()
    deal_type = data.get("deal_type", "sale")
    
    if deal_type == "rent":
        # Back to rental class
        await state.update_data(rental_classes=[])
        await callback.message.edit_text(
            _("auto.select_rental_class"),
            reply_markup=build_rental_class_keyboard(_),
        )
        await state.set_state(AutoRequirementStates.body_type)
    else:
        # Back to fuel type
        await state.update_data(fuel_types=[])
        await callback.message.edit_text(
            _("auto.select_fuel"),
            reply_markup=build_fuel_type_keyboard(_),
        )
        await state.set_state(AutoRequirementStates.fuel_type)


# ============ AUTO REQUIREMENT HANDLERS (BUYER) ============

@router.message(AutoRequirementStates.brands)
async def process_auto_req_brands(
    message: Message,
    state: FSMContext,
    _: Any,
) -> None:
    """Process brand text input for requirement (fallback)."""
    brands_text = message.text.strip()
    # Allow comma-separated brands or single brand
    brands = [b.strip() for b in brands_text.split(",") if b.strip()]
    
    if not brands:
        await message.answer(_("errors.invalid_input"))
        return
    
    await state.update_data(brands=brands)
    await message.answer(_("auto.enter_year_range"))
    await state.set_state(AutoRequirementStates.year_range)


@router.callback_query(F.data.startswith("auto_model_req:"), AutoRequirementStates.models)
async def select_requirement_model(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Handle model selection for requirement."""
    model = callback.data.split(":", 1)[1]
    await callback.answer()
    
    data = await state.get_data()
    db_year_min = data.get("db_year_min", 2000)
    db_year_max = data.get("db_year_max", 2025)
    
    await state.update_data(models=[model])
    await callback.message.edit_text(
        f"📅 {_('auto.enter_year_range_dynamic').format(min=db_year_min, max=db_year_max)}",
        reply_markup=build_back_keyboard(_),
    )
    await state.set_state(AutoRequirementStates.year_range)


@router.callback_query(F.data.startswith("auto_model_req_page:"), AutoRequirementStates.models)
async def requirement_model_page(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Handle model pagination for requirement."""
    page = int(callback.data.split(":")[1])
    await callback.answer()
    data = await state.get_data()
    brand = data.get("brand", "")
    await callback.message.edit_text(
        _("auto.enter_model"),
        reply_markup=build_model_keyboard_req(_, brand, page=page),
    )


@router.message(AutoRequirementStates.models)
async def process_auto_req_models_text(
    message: Message,
    state: FSMContext,
    _: Any,
) -> None:
    """Process model text input for requirement (fallback)."""
    models_text = message.text.strip()
    # Allow comma-separated models
    models = [m.strip() for m in models_text.split(",") if m.strip()]
    
    if not models:
        await message.answer(_("errors.invalid_input"))
        return
    
    data = await state.get_data()
    db_year_min = data.get("db_year_min", 2000)
    db_year_max = data.get("db_year_max", 2025)
    
    await state.update_data(models=models)
    await message.answer(
        f"📅 {_('auto.enter_year_range_dynamic').format(min=db_year_min, max=db_year_max)}",
        reply_markup=build_back_keyboard(_),
    )
    await state.set_state(AutoRequirementStates.year_range)


@router.callback_query(F.data == "auto:skip", AutoRequirementStates.models)
async def skip_auto_req_models(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Skip model input for requirement."""
    await callback.answer()
    
    data = await state.get_data()
    db_year_min = data.get("db_year_min", 2000)
    db_year_max = data.get("db_year_max", 2025)
    
    await state.update_data(models=[])
    await callback.message.edit_text(
        f"📅 {_('auto.enter_year_range_dynamic').format(min=db_year_min, max=db_year_max)}",
        reply_markup=build_back_keyboard(_),
    )
    await state.set_state(AutoRequirementStates.year_range)


@router.callback_query(F.data == "auto:back", AutoRequirementStates.models)
async def back_from_req_models(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Go back from models to brand selection."""
    await callback.answer()
    data = await state.get_data()
    page = data.get("brand_page", 0)
    await callback.message.edit_text(
        _("auto.enter_brand"),
        reply_markup=build_brand_keyboard(_, page=page),
    )
    await state.set_state(AutoRequirementStates.brands)


@router.message(AutoRequirementStates.year_range)
async def process_auto_req_year_range(
    message: Message,
    state: FSMContext,
    _: Any,
) -> None:
    """Process year range input with validation against DB range."""
    data = await state.get_data()
    db_year_min = data.get("db_year_min", 1950)
    db_year_max = data.get("db_year_max", 2025)
    
    try:
        text = message.text.strip().replace(" ", "")
        if "-" in text:
            parts = text.split("-")
            year_min = int(parts[0])
            year_max = int(parts[1])
        else:
            year_min = int(text)
            year_max = db_year_max
        
        if year_min > year_max:
            raise ValueError()
        
        # Validate against available years in DB
        if year_min < db_year_min or year_max > db_year_max:
            await message.answer(
                _("auto.year_out_of_range").format(min=db_year_min, max=db_year_max)
            )
            return
            
    except (ValueError, IndexError):
        await message.answer(_("edit.invalid_range"))
        return
    
    await state.update_data(year_min=year_min, year_max=year_max)
    await message.answer(
        _("auto.enter_price_range"),
        reply_markup=build_back_keyboard(_),
    )
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
        await message.answer(
            _("auto.enter_mileage_range"),
            reply_markup=build_back_keyboard(_),
        )
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
    
    await callback.message.edit_text(
        _("auto.enter_city"),
        reply_markup=build_city_keyboard_auto(_),
    )
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
    
    await callback.message.edit_text(
        _("auto.enter_city"),
        reply_markup=build_city_keyboard_auto(_),
    )
    await state.set_state(AutoRequirementStates.city)


@router.callback_query(F.data.startswith("auto_city:"), AutoRequirementStates.city)
async def select_requirement_city(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Handle city selection for requirement."""
    city = callback.data.split(":", 1)[1]
    await callback.answer()
    
    await state.update_data(city=city)
    
    # Show confirmation
    await _show_auto_requirement_confirmation_edit(callback.message, state, _)


@router.callback_query(F.data.startswith("auto_city_page:"), AutoRequirementStates.city)
async def requirement_city_page(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Handle city pagination for requirement."""
    page = int(callback.data.split(":")[1])
    await callback.answer()
    await callback.message.edit_text(
        _("auto.enter_city"),
        reply_markup=build_city_keyboard_auto(_, page=page),
    )


async def _show_auto_requirement_confirmation(
    message: Message,
    state: FSMContext,
    _: Any,
) -> None:
    """Show auto requirement confirmation."""
    data = await state.get_data()
    
    deal_type = data.get("deal_type", "sale")
    brands = ", ".join(data.get("brands", []))
    models = data.get("models", [])
    models_text = ", ".join(models) if models else "-"
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
            f"<b>{_('auto.model')}:</b> {models_text}\n"
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
            f"<b>{_('auto.model')}:</b> {models_text}\n"
            f"<b>{_('auto.year')}:</b> {year_min}-{year_max}\n"
            f"<b>{_('auto.mileage')}:</b> {_('auto.mileage_up_to').format(value=f'{mileage_max:,}')}\n"
            f"<b>⚙️:</b> {trans_text}\n"
            f"<b>⛽:</b> {fuel_text}\n"
            f"<b>💰 {_('auto.price')}:</b> {price_min}-{price_max} AZN\n"
            f"<b>🏙️:</b> {city}\n\n"
            f"{_('buttons.confirm')}?"
        )
    
    await message.answer(text, reply_markup=build_confirm_keyboard(_), parse_mode="HTML")
    await state.set_state(AutoRequirementStates.confirmation)


async def _show_auto_requirement_confirmation_edit(
    message: Message,
    state: FSMContext,
    _: Any,
) -> None:
    """Show auto requirement confirmation (edit version)."""
    data = await state.get_data()
    
    deal_type = data.get("deal_type", "sale")
    brands = ", ".join(data.get("brands", []))
    models = data.get("models", [])
    models_text = ", ".join(models) if models else "-"
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
            f"<b>{_('auto.model')}:</b> {models_text}\n"
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
            f"<b>{_('auto.model')}:</b> {models_text}\n"
            f"<b>{_('auto.year')}:</b> {year_min}-{year_max}\n"
            f"<b>{_('auto.mileage')}:</b> {_('auto.mileage_up_to').format(value=f'{mileage_max:,}')}\n"
            f"<b>⚙️:</b> {trans_text}\n"
            f"<b>⛽:</b> {fuel_text}\n"
            f"<b>💰 {_('auto.price')}:</b> {price_min}-{price_max} AZN\n"
            f"<b>🏙️:</b> {city}\n\n"
            f"{_('buttons.confirm')}?"
        )
    
    await message.edit_text(text, reply_markup=build_confirm_keyboard(_), parse_mode="HTML")
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
            f"🛣️ {_('auto.mileage')}: {listing.mileage:,} km\n"
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


@router.callback_query(F.data == "auto:back", AutoListingStates.brand)
async def back_from_listing_brand(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Go back from brand to deal type selection."""
    from app.bot.keyboards.builders import build_deal_type_keyboard
    from app.bot.states import OnboardingStates
    await callback.answer()
    data = await state.get_data()
    role = data.get("current_role", "seller")
    await callback.message.edit_text(
        _("deal_type.select"),
        reply_markup=build_deal_type_keyboard(_, "auto", role),
    )
    await state.set_state(OnboardingStates.market_type_select)


@router.callback_query(F.data == "auto:back", AutoListingStates.transmission)
async def back_from_listing_transmission(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Go back from transmission to mileage."""
    await callback.answer()
    await callback.message.edit_text(
        _("auto.enter_mileage"),
        reply_markup=build_back_keyboard(_),
    )
    await state.set_state(AutoListingStates.mileage)


@router.callback_query(F.data == "auto:back", AutoListingStates.fuel_type)
async def back_from_listing_fuel(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Go back from fuel to transmission."""
    await callback.answer()
    await callback.message.edit_text(
        _("auto.select_transmission"),
        reply_markup=build_transmission_keyboard(_),
    )
    await state.set_state(AutoListingStates.transmission)


@router.callback_query(F.data == "auto:back", AutoListingStates.body_type)
async def back_from_listing_rental_class(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Go back from rental class to year."""
    await callback.answer()
    await callback.message.edit_text(
        _("auto.enter_year"),
        reply_markup=build_back_keyboard(_),
    )
    await state.set_state(AutoListingStates.year)


@router.callback_query(F.data == "auto:back", AutoListingStates.description)
async def back_from_listing_description(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Go back from description to city."""
    await callback.answer()
    await callback.message.edit_text(
        _("auto.enter_city"),
        reply_markup=build_back_keyboard(_),
    )
    await state.set_state(AutoListingStates.city)


@router.callback_query(F.data == "auto:back", AutoRequirementStates.brands)
async def back_from_req_brands(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Go back from brands to deal type selection."""
    from app.bot.keyboards.builders import build_deal_type_keyboard
    from app.bot.states import OnboardingStates
    await callback.answer()
    data = await state.get_data()
    role = data.get("current_role", "buyer")
    await callback.message.edit_text(
        _("deal_type.select"),
        reply_markup=build_deal_type_keyboard(_, "auto", role),
    )
    await state.set_state(OnboardingStates.market_type_select)


@router.callback_query(F.data == "auto:back", AutoRequirementStates.transmission)
async def back_from_req_transmission(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Go back from transmission to mileage."""
    await callback.answer()
    await callback.message.edit_text(
        _("auto.enter_mileage_range"),
        reply_markup=build_back_keyboard(_),
    )
    await state.set_state(AutoRequirementStates.mileage_max)


@router.callback_query(F.data == "auto:back", AutoRequirementStates.fuel_type)
async def back_from_req_fuel(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Go back from fuel to transmission."""
    await callback.answer()
    await state.update_data(transmissions=[])
    await callback.message.edit_text(
        _("auto.select_transmission"),
        reply_markup=build_transmission_keyboard(_),
    )
    await state.set_state(AutoRequirementStates.transmission)


@router.callback_query(F.data == "auto:back", AutoRequirementStates.body_type)
async def back_from_req_rental_class(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Go back from rental class to price range."""
    await callback.answer()
    await callback.message.edit_text(
        _("auto.enter_price_range"),
        reply_markup=build_back_keyboard(_),
    )
    await state.set_state(AutoRequirementStates.price_range)


@router.callback_query(F.data == "auto:back")
async def auto_back_default(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Default back handler - go to deal type selection."""
    from app.bot.keyboards.builders import build_deal_type_keyboard
    from app.bot.states import OnboardingStates
    await callback.answer()
    data = await state.get_data()
    role = data.get("current_role", "buyer")
    await callback.message.edit_text(
        _("deal_type.select"),
        reply_markup=build_deal_type_keyboard(_, "auto", role),
    )
    await state.set_state(OnboardingStates.market_type_select)
