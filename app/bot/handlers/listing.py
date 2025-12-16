import logging
from decimal import Decimal
from typing import Any, Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reference import Category
from app.models.listing import Listing, PaymentTypeEnum, RenovationStatusEnum, HeatingTypeEnum, ListingStatusEnum
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
    build_skip_keyboard,
    build_confirm_keyboard,
    build_start_over_keyboard,
)
from app.bot.keyboards.callbacks import (
    LocationCallback,
    FormFieldCallback,
    NavigationCallback,
)
from app.bot.states import ListingStates

router = Router(name="listing")

@router.callback_query(F.data.startswith("cat:"), ListingStates.category)
async def process_category(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
) -> None:
    """Handle category selection for listing."""
    await callback.answer()
    
    category = callback.data.split(":")[1]
    await state.update_data(category=category)
    
    await callback.message.edit_text(
        _("location.select_type"),
        reply_markup=build_location_type_keyboard(_),
    )
    await state.set_state(ListingStates.location_type)

@router.callback_query(LocationCallback.filter(F.type == "city"), ListingStates.location_type)
async def location_city(callback: CallbackQuery, state: FSMContext, _: Any, lang: str) -> None:
    await callback.answer()
    await callback.message.edit_text(
        _("location.select_city"),
        reply_markup=build_city_keyboard_static(_, lang=lang),
    )
    await state.set_state(ListingStates.location_select)


@router.callback_query(F.data.startswith("city_select:"), ListingStates.location_select)
async def city_selected(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    """Handle city selection from static list."""
    await callback.answer()
    city = callback.data.split(":", 1)[1]
    await state.update_data(city=city, location_id=city)
    await callback.message.edit_text(_("form.price.enter"))
    await state.set_state(ListingStates.price)


@router.callback_query(F.data.startswith("city_page:"), ListingStates.location_select)
async def city_page(callback: CallbackQuery, state: FSMContext, _: Any, lang: str) -> None:
    """Handle city pagination."""
    page = int(callback.data.split(":")[1])
    await callback.answer()
    await callback.message.edit_text(
        _("location.select_city"),
        reply_markup=build_city_keyboard_static(_, page=page, lang=lang),
    )




@router.callback_query(LocationCallback.filter(F.type == "metro"), ListingStates.location_type)
async def location_metro(callback: CallbackQuery, state: FSMContext, _: Any) -> None:

    await callback.answer()
    await callback.message.edit_text(
        _("metro.select_line"),
        reply_markup=build_metro_line_keyboard(_),
    )
    await state.set_state(ListingStates.location_select)

@router.callback_query(LocationCallback.filter(F.type == "metro_line"), ListingStates.location_select)
async def metro_line_selected(callback: CallbackQuery, callback_data: LocationCallback, state: FSMContext, _: Any, lang: str) -> None:

    await callback.answer()
    await state.update_data(metro_line=callback_data.id)
    stations = get_metro_stations(callback_data.id)
    await callback.message.edit_text(
        _("location.select_metro"),
        reply_markup=build_metro_keyboard(stations, _, lang),
    )

@router.callback_query(LocationCallback.filter(F.type == "metro_back"), ListingStates.location_select)
async def metro_back_to_lines(callback: CallbackQuery, state: FSMContext, _: Any) -> None:

    await callback.answer()
    await callback.message.edit_text(
        _("metro.select_line"),
        reply_markup=build_metro_line_keyboard(_),
    )

@router.callback_query(LocationCallback.filter(F.type == "metro_station"), ListingStates.location_select)
async def metro_station_selected(callback: CallbackQuery, callback_data: LocationCallback, state: FSMContext, _: Any) -> None:

    await callback.answer()
    await state.update_data(metro_id=callback_data.id)
    await callback.message.edit_text(_("form.price.enter"))
    await state.set_state(ListingStates.price)

@router.callback_query(LocationCallback.filter(F.type == "gps"), ListingStates.location_type)
async def location_gps(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await callback.message.edit_text(_("location.share_location"))
    await state.set_state(ListingStates.location_gps)

@router.message(F.location, ListingStates.location_gps)
async def gps_received(message: Message, state: FSMContext, _: Any) -> None:
    await state.update_data(latitude=message.location.latitude, longitude=message.location.longitude)
    await message.answer(_("form.price.enter"))
    await state.set_state(ListingStates.price)

@router.message(ListingStates.price)
async def process_price(message: Message, state: FSMContext, _: Any) -> None:
    try:
        price = float(message.text.replace(",", ".").replace(" ", ""))
        if price <= 0:
            raise ValueError()
        await state.update_data(price=price)
        await message.answer(_("form.payment.select"), reply_markup=build_payment_type_keyboard(_))
        await state.set_state(ListingStates.payment_type)
    except ValueError:
        await message.answer(_("form.price.invalid"))

@router.callback_query(FormFieldCallback.filter(F.field == "payment_type"), ListingStates.payment_type)
async def process_payment(callback: CallbackQuery, callback_data: FormFieldCallback, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await state.update_data(payment_type=callback_data.value)
    if callback_data.value in ("credit", "both"):
        await callback.message.edit_text(_("form.down_payment.enter"), reply_markup=build_skip_keyboard(_))
        await state.set_state(ListingStates.down_payment)
    else:
        data = await state.get_data()
        if data.get("category") == "land":
            await callback.message.edit_text(_("form.area.enter_sot"))
        else:
            await callback.message.edit_text(_("form.rooms.enter"))
        await state.set_state(ListingStates.rooms)

@router.message(ListingStates.down_payment)
async def process_down_payment(message: Message, state: FSMContext, _: Any) -> None:
    try:
        dp = float(message.text.replace(",", ".").replace(" ", ""))
        await state.update_data(down_payment=dp)
    except ValueError:
        pass
    data = await state.get_data()
    if data.get("category") == "land":
        await message.answer(_("form.area.enter_sot"))
    else:
        await message.answer(_("form.rooms.enter"))
    await state.set_state(ListingStates.rooms)

@router.callback_query(NavigationCallback.filter(F.action == "skip"), ListingStates.down_payment)
async def skip_down_payment(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    data = await state.get_data()
    if data.get("category") == "land":
        await callback.message.edit_text(_("form.area.enter_sot"))
    else:
        await callback.message.edit_text(_("form.rooms.enter"))
    await state.set_state(ListingStates.rooms)

@router.message(ListingStates.rooms)
async def process_rooms(message: Message, state: FSMContext, _: Any) -> None:
    try:
        rooms = int(message.text)
        if not 1 <= rooms <= 50:
            raise ValueError()
        await state.update_data(rooms=rooms)
        await message.answer(_("form.area.enter"))
        await state.set_state(ListingStates.area)
    except ValueError:
        await message.answer(_("form.rooms.invalid"))

@router.message(ListingStates.area)
async def process_area(message: Message, state: FSMContext, _: Any) -> None:
    try:
        area = float(message.text.replace(",", ".").replace(" ", ""))
        if area <= 0:
            raise ValueError()
        await state.update_data(area=area)
        data = await state.get_data()
        if data.get("category") in ("land", "private_house"):
            await message.answer(_("form.renovation.select"), reply_markup=build_renovation_keyboard(_))
            await state.set_state(ListingStates.renovation)
        else:
            await message.answer(_("form.floor.enter"))
            await state.set_state(ListingStates.floor)
    except ValueError:
        await message.answer(_("form.area.invalid"))

@router.message(ListingStates.floor)
async def process_floor(message: Message, state: FSMContext, _: Any) -> None:
    try:
        floor = int(message.text)
        if not -2 <= floor <= 50:
            raise ValueError()
        await state.update_data(floor=floor)
        await message.answer(_("form.building_floors.enter"))
        await state.set_state(ListingStates.building_floors)
    except ValueError:
        await message.answer(_("form.floor.invalid"))

@router.message(ListingStates.building_floors)
async def process_building_floors(message: Message, state: FSMContext, _: Any) -> None:
    try:
        bf = int(message.text)
        if not 1 <= bf <= 50:
            raise ValueError()
        await state.update_data(building_floors=bf)
        await message.answer(_("form.renovation.select"), reply_markup=build_renovation_keyboard(_))
        await state.set_state(ListingStates.renovation)
    except ValueError:
        await message.answer(_("form.building_floors.invalid"))

@router.callback_query(FormFieldCallback.filter(F.field == "renovation"), ListingStates.renovation)
async def process_renovation(callback: CallbackQuery, callback_data: FormFieldCallback, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await state.update_data(renovation=callback_data.value)
    await callback.message.edit_text(_("form.documents.select"), reply_markup=build_documents_keyboard(_, allow_multiple=False))
    await state.set_state(ListingStates.documents)

@router.callback_query(FormFieldCallback.filter(F.field == "documents"), ListingStates.documents)
async def process_documents(callback: CallbackQuery, callback_data: FormFieldCallback, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await state.update_data(documents=callback_data.value)
    await callback.message.edit_text(_("form.utilities.gas"), reply_markup=build_utilities_keyboard(_, "gas"))
    await state.set_state(ListingStates.utilities)
    await state.update_data(utility_step="gas")

@router.callback_query(FormFieldCallback.filter(F.field.startswith("utility_")), ListingStates.utilities)
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
        await callback.message.edit_text(_("form.heating.select"), reply_markup=build_heating_keyboard(_))
        await state.set_state(ListingStates.heating)

@router.callback_query(FormFieldCallback.filter(F.field == "heating"), ListingStates.heating)
async def process_heating(callback: CallbackQuery, callback_data: FormFieldCallback, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await state.update_data(heating=callback_data.value)
    await callback.message.edit_text(_("form.age.select"), reply_markup=build_property_age_keyboard(_))
    await state.set_state(ListingStates.property_age)

@router.callback_query(FormFieldCallback.filter(F.field == "property_age"), ListingStates.property_age)
async def process_age(callback: CallbackQuery, callback_data: FormFieldCallback, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await state.update_data(property_age=callback_data.value)
    await callback.message.edit_text(_("form.photos.upload"))
    await state.set_state(ListingStates.photos)
    await state.update_data(photos=[])

@router.message(F.photo, ListingStates.photos)
async def process_photo(message: Message, state: FSMContext, _: Any) -> None:
    data = await state.get_data()
    photos = data.get("photos", [])
    if len(photos) >= 15:
        await message.answer(_("form.photos.max_exceeded"))
        return
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    
    if len(photos) < 3:
        await message.answer(_("form.photos.need_more").format(count=len(photos), min=3))
    else:
        await message.answer(
            _("form.photos.received").format(count=len(photos)),
            reply_markup=build_skip_keyboard(_)
        )
        await state.set_state(ListingStates.video_link)

@router.callback_query(NavigationCallback.filter(F.action == "skip"), ListingStates.photos)
async def skip_more_photos(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    data = await state.get_data()
    photos = data.get("photos", [])
    if len(photos) < 3:
        await callback.answer(_("form.photos.min_required"), show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(_("form.video.enter"))
    await state.set_state(ListingStates.video_link)

@router.message(ListingStates.video_link)
async def process_video(message: Message, state: FSMContext, _: Any) -> None:
    url = message.text
    if "youtube.com" in url or "youtu.be" in url or "vimeo.com" in url:
        await state.update_data(video_url=url)
    await message.answer(_("form.description.enter"))
    await state.set_state(ListingStates.description)

@router.callback_query(NavigationCallback.filter(F.action == "skip"), ListingStates.video_link)
async def skip_video(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await callback.message.edit_text(_("form.description.enter"))
    await state.set_state(ListingStates.description)

@router.message(ListingStates.description)
async def process_description(message: Message, state: FSMContext, _: Any) -> None:
    await state.update_data(description=message.text[:1000])
    await show_listing_summary(message, state, _)

async def show_listing_summary(message: Message, state: FSMContext, _: Any) -> None:

    data = await state.get_data()
    
    category = data.get('category', '')
    category_name = _(f"categories.{category}") if category else '-'
    
    payment = data.get('payment_type', '')
    payment_name = _(f"form.payment.{payment}") if payment else '-'
    
    renovation = data.get('renovation', '')
    renovation_name = _(f"form.renovation.{renovation}") if renovation else '-'
    
    currency = _("form.price.currency")
    
    summary = f"""📋 <b>{_('listing.summary')}</b>

📦 {category_name}
💰 {data.get('price', 0):,.0f} {currency}
💳 {payment_name}"""
    
    if data.get('down_payment'):
        summary += f"\n💵 {data.get('down_payment'):,.0f} {currency}"
    
    if data.get('category') != 'land':
        summary += f"\n🏠 {data.get('rooms', '-')}"
    
    summary += f"\n📐 {data.get('area', 0)} m²"
    
    if data.get('floor'):
        summary += f"\n🏢 {data.get('floor', '-')}/{data.get('building_floors', '-')}"
    
    summary += f"""
✨ {renovation_name}
📷 {len(data.get('photos', []))}

📝 {(data.get('description', '') or '-')[:100]}...
"""
    
    await message.answer(summary, reply_markup=build_confirm_keyboard(_), parse_mode="HTML")
    await state.set_state(ListingStates.confirmation)

@router.callback_query(NavigationCallback.filter(F.action == "confirm"), ListingStates.confirmation)
async def confirm_listing(
    callback: CallbackQuery,
    state: FSMContext,
    _: Any,
    user: Any,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """Confirm and submit listing to database."""
    await callback.answer()
    
    data = await state.get_data()
    
    try:
        if db_session and user:
            category_code = data.get("category", "other")
            category = await get_or_create_category(db_session, category_code)
            
            location_id = await get_or_create_location(db_session)
            
            payment_type_str = data.get("payment_type", "cash")
            payment_map = {
                "cash": PaymentTypeEnum.CASH,
                "credit": PaymentTypeEnum.CREDIT,
                "both": PaymentTypeEnum.BOTH,
            }
            payment_type_enum = payment_map.get(payment_type_str, PaymentTypeEnum.CASH)
            
            renovation_str = data.get("renovation")
            renovation_enum = None
            if renovation_str:
                reno_map = {
                    "renovated": RenovationStatusEnum.RENOVATED,
                    "not_renovated": RenovationStatusEnum.NOT_RENOVATED,
                    "partial": RenovationStatusEnum.PARTIAL,
                }
                renovation_enum = reno_map.get(renovation_str)
            
            heating_str = data.get("heating")
            heating_enum = None
            if heating_str:
                heat_map = {
                    "central": HeatingTypeEnum.CENTRAL,
                    "individual": HeatingTypeEnum.INDIVIDUAL,
                    "combi": HeatingTypeEnum.COMBI,
                    "none": HeatingTypeEnum.NONE,
                }
                heating_enum = heat_map.get(heating_str)
            
            # Get deal type from state
            from app.models.listing import DealTypeEnum
            deal_type_str = data.get("deal_type", "sale")
            deal_type_enum = DealTypeEnum.RENT if deal_type_str == "rent" else DealTypeEnum.SALE
            
            listing = Listing(
                user_id=user.id,
                category_id=category.id,
                location_id=location_id,
                deal_type=deal_type_enum,
                price=Decimal(str(data.get("price", 0))),
                payment_type=payment_type_enum,
                down_payment=Decimal(str(data.get("down_payment", 0))) if data.get("down_payment") else None,
                rooms=data.get("rooms"),
                area=Decimal(str(data.get("area", 0))),
                floor=data.get("floor"),
                building_floors=data.get("building_floors"),
                renovation_status=renovation_enum,
                document_types=data.get("documents", []),
                utilities=data.get("utilities", {}),
                heating_type=heating_enum,
                description=data.get("description"),
                status=ListingStatusEnum.ACTIVE,  # Auto-approve for now
            )
            
            db_session.add(listing)
            await db_session.flush()  # Get listing.id
            
            # Save photos
            photos = data.get("photos", [])
            if photos:
                from app.models.listing import ListingMedia, ListingMediaTypeEnum
                for i, photo_file_id in enumerate(photos):
                    media = ListingMedia(
                        listing_id=listing.id,
                        type=ListingMediaTypeEnum.IMAGE,
                        url=photo_file_id,
                        order=i,
                    )
                    db_session.add(media)
                logger.info(f"Saved {len(photos)} photos for listing {listing.id}")
            
            await db_session.commit()
            
            logger.info(f"Created listing {listing.id} for user {user.id}")
            
            # Trigger matching and send notifications
            try:
                from app.services.match import MatchService
                from app.services.notification import NotificationService
                from app.models.user import User
                from sqlalchemy import select
                
                match_service = MatchService(db_session)
                notifications = await match_service.process_new_listing(listing.id)
                
                if notifications:
                    logger.info(f"Found {len(notifications)} matches for listing {listing.id}")
                    notification_service = NotificationService(db_session)
                    bot = callback.bot
                    
                    for notif in notifications:
                        try:
                            # Get buyer user
                            result = await db_session.execute(
                                select(User).where(User.id == notif.buyer_user_id)
                            )
                            buyer = result.scalar_one_or_none()
                            
                            if buyer and buyer.telegram_id:
                                is_premium = await notification_service.is_user_premium(buyer.id)
                                
                                if is_premium:
                                    # Send immediately for premium users
                                    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                                        [
                                            InlineKeyboardButton(text="👁️ Смотреть", callback_data=f"match:view:{notif.match_id}"),
                                            InlineKeyboardButton(text="💬 Связаться", callback_data=f"match:contact:{notif.match_id}"),
                                        ],
                                        [
                                            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"match:reject:{notif.match_id}"),
                                        ]
                                    ])
                                    await bot.send_message(
                                        chat_id=buyer.telegram_id,
                                        text=f"🎯 Найдено новое совпадение!\n\nСовпадение: {notif.score}%",
                                        reply_markup=keyboard,
                                    )
                                    logger.info(f"Sent immediate notification to premium user {buyer.telegram_id}")
                                else:
                                    logger.info(f"Free user {buyer.telegram_id} - notification delayed 24h")
                        except Exception as notif_err:
                            logger.error(f"Failed to send notification: {notif_err}")
            except Exception as match_err:
                logger.error(f"Matching error: {match_err}")
        
        await state.clear()
        await callback.message.edit_text(
            _("listing.created"),
            reply_markup=build_start_over_keyboard(_),
        )
        
    except Exception as e:
        logger.error(f"Error creating listing: {e}")
        await callback.message.edit_text(
            _("errors.general"),
            reply_markup=build_start_over_keyboard(_),
        )
        await state.clear()

@router.callback_query(NavigationCallback.filter(F.action == "cancel"), ListingStates.confirmation)
async def cancel_listing(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        _("buttons.cancelled"),
        reply_markup=build_start_over_keyboard(_),
    )

@router.callback_query(NavigationCallback.filter(F.action == "back"), ListingStates.category)
async def back_to_deal_type_from_listing(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    """Go back from category to deal type selection."""
    from app.bot.keyboards.builders import build_deal_type_keyboard
    from app.bot.states import OnboardingStates
    await callback.answer()
    data = await state.get_data()
    role = data.get("current_role", "seller")
    market_type = data.get("market_type", "real_estate")
    await callback.message.edit_text(
        _("deal_type.select"),
        reply_markup=build_deal_type_keyboard(_, market_type, role)
    )
    await state.set_state(OnboardingStates.market_type_select)

@router.callback_query(NavigationCallback.filter(F.action == "back"), ListingStates.location_type)
async def back_to_category(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await callback.message.edit_text(_("categories.select"), reply_markup=build_categories_keyboard(_))
    await state.set_state(ListingStates.category)

@router.callback_query(NavigationCallback.filter(F.action == "back"), ListingStates.location_select)
async def back_to_location_type(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.answer()
    await callback.message.edit_text(_("location.select_type"), reply_markup=build_location_type_keyboard(_))
    await state.set_state(ListingStates.location_type)
async def get_or_create_category(session: AsyncSession, code: str) -> Category:

    from app.models.reference import Category
    
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

async def get_or_create_location(session: AsyncSession) -> str:

    from app.models.reference import Location
    import uuid
    
    result = await session.execute(
        select(Location).where(Location.name_en == "Baku")
    )
    location = result.scalar_one_or_none()
    
    if not location:
        location = Location(
            name_az="Bakı",
            name_ru="Баку",
            name_en="Baku",
            type="city",
        )
        session.add(location)
        await session.flush()
    
    return location.id
