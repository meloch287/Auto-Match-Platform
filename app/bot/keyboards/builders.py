from typing import Any, Callable, Optional

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.callbacks import (
    CategoryCallback,
    ChatCallback,
    FormFieldCallback,
    LanguageCallback,
    LocationCallback,
    MatchCallback,
    NavigationCallback,
    RoleCallback,
    SubscriptionCallback,
    VIPCallback,
)

Translator = Callable[[str], str]

def build_language_keyboard() -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()
    
    languages = [
        ("🇦🇿 Azərbaycan", "az"),
        ("🇷🇺 Русский", "ru"),
        ("🇬🇧 English", "en"),
    ]
    
    for text, code in languages:
        builder.button(
            text=text,
            callback_data=LanguageCallback(code=code),
        )
    
    builder.adjust(1)
    return builder.as_markup()

def build_role_keyboard(_: Translator) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()
    
    builder.button(
        text=f"🏠 {_('roles.buyer')}",
        callback_data=RoleCallback(role="buyer"),
    )
    builder.button(
        text=f"🏷️ {_('roles.seller')}",
        callback_data=RoleCallback(role="seller"),
    )
    
    builder.adjust(1)
    return builder.as_markup()


def build_market_type_keyboard(_: Translator) -> InlineKeyboardMarkup:
    """Build market type selection keyboard (Real Estate / Auto)."""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text=f"🏠 {_('market.real_estate')}",
        callback_data="market:real_estate",
    )
    builder.button(
        text=f"🚗 {_('market.auto')}",
        callback_data="market:auto",
    )
    builder.button(
        text=f"⬅️ {_('buttons.back_simple')}",
        callback_data="market:back",
    )
    
    builder.adjust(1)
    return builder.as_markup()

def build_category_keyboard(
    categories: list[dict[str, Any]],
    _: Translator,
    lang: str = "az",
) -> InlineKeyboardMarkup:
    """
    Build category selection keyboard.
    
    Args:
        categories: List of category dicts with id, name_az, name_ru, name_en, icon
        _: Translator function
        lang: Current language code
        
    Returns:
        InlineKeyboardMarkup with category options
    """
    builder = InlineKeyboardBuilder()
    
    name_field = f"name_{lang}"
    
    for cat in categories:
        icon = cat.get("icon", "📦")
        name = cat.get(name_field, cat.get("name_en", "Unknown"))
        
        builder.button(
            text=f"{icon} {name}",
            callback_data=CategoryCallback(id=str(cat["id"])),
        )
    
    builder.adjust(2)
    
    builder.row(
        InlineKeyboardButton(
            text=f"⬅️ {_('buttons.back')}",
            callback_data=NavigationCallback(action="back").pack(),
        )
    )
    
    return builder.as_markup()

def build_location_type_keyboard(_: Translator) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()
    
    builder.button(
        text=f"🏙️ {_('location.city_district')}",
        callback_data=LocationCallback(type="city"),
    )
    builder.button(
        text=f"🚇 {_('location.metro')}",
        callback_data=LocationCallback(type="metro"),
    )
    builder.button(
        text=f"📍 {_('location.gps')}",
        callback_data=LocationCallback(type="gps"),
    )
    
    builder.adjust(1)
    
    builder.row(
        InlineKeyboardButton(
            text=_('buttons.back'),
            callback_data=NavigationCallback(action="back").pack(),
        )
    )
    
    return builder.as_markup()

def build_city_keyboard(
    cities: list[dict[str, Any]],
    _: Translator,
    lang: str = "az",
) -> InlineKeyboardMarkup:
    """
    Build city selection keyboard.
    
    Args:
        cities: List of city dicts
        _: Translator function
        lang: Current language code
        
    Returns:
        InlineKeyboardMarkup with city options
    """
    builder = InlineKeyboardBuilder()
    
    name_field = f"name_{lang}"
    
    for city in cities:
        name = city.get(name_field, city.get("name_en", "Unknown"))
        
        builder.button(
            text=name,
            callback_data=LocationCallback(type="district", id=str(city["id"])),
        )
    
    builder.adjust(2)
    
    builder.row(
        InlineKeyboardButton(
            text=_('buttons.back'),
            callback_data=NavigationCallback(action="back").pack(),
        )
    )
    
    return builder.as_markup()

def build_district_keyboard(
    districts: list[dict[str, Any]],
    _: Translator,
    lang: str = "az",
    allow_multiple: bool = False,
    selected: Optional[list[str]] = None,
) -> InlineKeyboardMarkup:
    """
    Build district selection keyboard.
    
    Args:
        districts: List of district dicts
        _: Translator function
        lang: Current language code
        allow_multiple: Whether to allow multiple selection
        selected: List of already selected district IDs
        
    Returns:
        InlineKeyboardMarkup with district options
    """
    builder = InlineKeyboardBuilder()
    selected = selected or []
    
    name_field = f"name_{lang}"
    
    for district in districts:
        name = district.get(name_field, district.get("name_en", "Unknown"))
        district_id = str(district["id"])
        
        if district_id in selected:
            name = f"✅ {name}"
        
        builder.button(
            text=name,
            callback_data=LocationCallback(type="select", id=district_id),
        )
    
    builder.adjust(2)
    
    if allow_multiple and selected:
        builder.row(
            InlineKeyboardButton(
                text=f"✅ {_('buttons.confirm')} ({len(selected)})",
                callback_data=NavigationCallback(action="confirm").pack(),
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text=_('buttons.back'),
            callback_data=NavigationCallback(action="back").pack(),
        )
    )
    
    return builder.as_markup()

def build_metro_line_keyboard(_: Translator) -> InlineKeyboardMarkup:

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
    
    builder.row(
        InlineKeyboardButton(
            text=_('buttons.back'),
            callback_data=NavigationCallback(action="back").pack(),
        )
    )
    
    return builder.as_markup()

def build_metro_keyboard(
    stations: list[dict[str, Any]],
    _: Translator,
    lang: str = "az",
) -> InlineKeyboardMarkup:
    """
    Build metro station selection keyboard.
    
    Args:
        stations: List of metro station dicts
        _: Translator function
        lang: Current language code
        
    Returns:
        InlineKeyboardMarkup with metro station options
    """
    builder = InlineKeyboardBuilder()
    
    name_field = f"name_{lang}"
    
    for station in stations:
        name = station.get(name_field, station.get("name_en", "Unknown"))
        
        builder.button(
            text=name,
            callback_data=LocationCallback(type="metro_station", id=str(station["id"])),
        )
    
    builder.adjust(2)
    
    builder.row(
        InlineKeyboardButton(
            text=_('buttons.back'),
            callback_data=LocationCallback(type="metro_back").pack(),
        )
    )
    
    return builder.as_markup()

def build_payment_type_keyboard(_: Translator) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()
    
    options = [
        ("cash", "💵", "form.payment.cash"),
        ("credit", "🏦", "form.payment.credit"),
        ("both", "💳", "form.payment.both"),
    ]
    
    for value, icon, key in options:
        builder.button(
            text=f"{icon} {_(key)}",
            callback_data=FormFieldCallback(field="payment_type", value=value),
        )
    
    builder.adjust(1)
    _add_back_button(builder, _)
    return builder.as_markup()

def build_renovation_keyboard(
    _: Translator,
    allow_multiple: bool = False,
    selected: Optional[list[str]] = None,
) -> InlineKeyboardMarkup:
    """Build renovation status selection keyboard."""
    builder = InlineKeyboardBuilder()
    selected = selected or []
    
    options = [
        ("renovated", "✨", "form.renovation.renovated"),
        ("not_renovated", "🔨", "form.renovation.not_renovated"),
        ("partial", "🔧", "form.renovation.partial"),
    ]
    
    if allow_multiple:
        options.append(("any", "🔄", "form.renovation.any"))
    
    for value, icon, key in options:
        text = f"{icon} {_(key)}"
        if value in selected:
            text = f"✅ {text}"
        
        builder.button(
            text=text,
            callback_data=FormFieldCallback(field="renovation", value=value),
        )
    
    builder.adjust(1)
    
    if allow_multiple and selected:
        builder.row(
            InlineKeyboardButton(
                text=f"✅ {_('buttons.confirm')}",
                callback_data=NavigationCallback(action="confirm").pack(),
            )
        )
    
    _add_back_button(builder, _)
    return builder.as_markup()

def build_documents_keyboard(
    _: Translator,
    allow_multiple: bool = True,
    selected: Optional[list[str]] = None,
) -> InlineKeyboardMarkup:
    """Build document type selection keyboard."""
    builder = InlineKeyboardBuilder()
    selected = selected or []
    
    options = [
        ("extract", "📄", "form.documents.extract"),
        ("title_deed", "📜", "form.documents.title_deed"),
        ("technical", "📋", "form.documents.technical"),
    ]
    
    if allow_multiple:
        options.append(("any", "🔄", "form.documents.any"))
    
    for value, icon, key in options:
        text = f"{icon} {_(key)}"
        if value in selected:
            text = f"✅ {text}"
        
        builder.button(
            text=text,
            callback_data=FormFieldCallback(field="documents", value=value),
        )
    
    builder.adjust(1)
    
    if allow_multiple and selected:
        builder.row(
            InlineKeyboardButton(
                text=f"✅ {_('buttons.confirm')}",
                callback_data=NavigationCallback(action="confirm").pack(),
            )
        )
    
    _add_back_button(builder, _)
    return builder.as_markup()

def build_utilities_keyboard(
    _: Translator,
    utility_type: str,
) -> InlineKeyboardMarkup:
    """Build utility availability selection keyboard."""
    builder = InlineKeyboardBuilder()
    
    options = [
        ("yes", "✅", "form.utilities.available"),
        ("no", "❌", "form.utilities.not_available"),
        ("any", "🔄", "form.utilities.any"),
    ]
    
    for value, icon, key in options:
        builder.button(
            text=f"{icon} {_(key)}",
            callback_data=FormFieldCallback(field=f"utility_{utility_type}", value=value),
        )
    
    builder.adjust(3)
    _add_back_button(builder, _)
    return builder.as_markup()

def build_heating_keyboard(
    _: Translator,
    allow_multiple: bool = False,
    selected: Optional[list[str]] = None,
) -> InlineKeyboardMarkup:
    """Build heating type selection keyboard."""
    builder = InlineKeyboardBuilder()
    selected = selected or []
    
    options = [
        ("central", "🏢", "form.heating.central"),
        ("individual", "🔥", "form.heating.individual"),
        ("combi", "♨️", "form.heating.combi"),
        ("none", "❄️", "form.heating.none"),
    ]
    
    if allow_multiple:
        options.append(("any", "🔄", "form.heating.any"))
    
    for value, icon, key in options:
        text = f"{icon} {_(key)}"
        if value in selected:
            text = f"✅ {text}"
        
        builder.button(
            text=text,
            callback_data=FormFieldCallback(field="heating", value=value),
        )
    
    builder.adjust(2)
    
    if allow_multiple and selected:
        builder.row(
            InlineKeyboardButton(
                text=f"✅ {_('buttons.confirm')}",
                callback_data=NavigationCallback(action="confirm").pack(),
            )
        )
    
    _add_back_button(builder, _)
    return builder.as_markup()

def build_property_age_keyboard(
    _: Translator,
    allow_multiple: bool = False,
    selected: Optional[list[str]] = None,
) -> InlineKeyboardMarkup:
    """Build property age selection keyboard."""
    builder = InlineKeyboardBuilder()
    selected = selected or []
    
    options = [
        ("new", "🆕", "form.age.new"),
        ("medium", "🏠", "form.age.medium"),
        ("old", "🏚️", "form.age.old"),
    ]
    
    if allow_multiple:
        options.append(("any", "🔄", "form.age.any"))
    
    for value, icon, key in options:
        text = f"{icon} {_(key)}"
        if value in selected:
            text = f"✅ {text}"
        
        builder.button(
            text=text,
            callback_data=FormFieldCallback(field="property_age", value=value),
        )
    
    builder.adjust(1)
    
    if allow_multiple and selected:
        builder.row(
            InlineKeyboardButton(
                text=f"✅ {_('buttons.confirm')}",
                callback_data=NavigationCallback(action="confirm").pack(),
            )
        )
    
    _add_back_button(builder, _)
    return builder.as_markup()

def build_floor_preferences_keyboard(
    _: Translator,
    selected: Optional[dict[str, bool]] = None,
) -> InlineKeyboardMarkup:
    """Build floor preferences keyboard."""
    builder = InlineKeyboardBuilder()
    selected = selected or {}
    
    not_first = selected.get("not_first", False)
    not_last = selected.get("not_last", False)
    
    builder.button(
        text=f"{'✅' if not_first else '⬜'} {_('form.floor.not_first')}",
        callback_data=FormFieldCallback(field="floor_pref", value="not_first"),
    )
    builder.button(
        text=f"{'✅' if not_last else '⬜'} {_('form.floor.not_last')}",
        callback_data=FormFieldCallback(field="floor_pref", value="not_last"),
    )
    
    builder.adjust(1)
    
    builder.row(
        InlineKeyboardButton(
            text=f"✅ {_('buttons.confirm')}",
            callback_data=NavigationCallback(action="confirm").pack(),
        )
    )
    
    _add_back_button(builder, _)
    return builder.as_markup()

def build_yes_no_keyboard(_: Translator) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()
    
    builder.button(
        text=f"✅ {_('buttons.yes')}",
        callback_data=FormFieldCallback(field="confirm", value="yes"),
    )
    builder.button(
        text=f"❌ {_('buttons.no')}",
        callback_data=FormFieldCallback(field="confirm", value="no"),
    )
    
    builder.adjust(2)
    return builder.as_markup()

def build_skip_keyboard(_: Translator) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()
    
    builder.button(
        text=f"⏭️ {_('buttons.skip')}",
        callback_data=NavigationCallback(action="skip"),
    )
    
    _add_back_button(builder, _)
    return builder.as_markup()

def build_match_actions_keyboard(
    match_id: str,
    _: Translator,
) -> InlineKeyboardMarkup:
    """
    Build match action buttons keyboard.
    
    Args:
        match_id: Match UUID
        _: Translator function
        
    Returns:
        InlineKeyboardMarkup with View, Contact, Reject buttons
    """
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text=f"👁️ {_('match.view')}",
        callback_data=MatchCallback(action="view", id=match_id),
    )
    builder.button(
        text=f"💬 {_('match.contact')}",
        callback_data=MatchCallback(action="contact", id=match_id),
    )
    builder.button(
        text=f"❌ {_('match.reject')}",
        callback_data=MatchCallback(action="reject", id=match_id),
    )
    
    builder.adjust(3)
    return builder.as_markup()

def build_chat_actions_keyboard(
    chat_id: str,
    _: Translator,
    can_reveal: bool = True,
) -> InlineKeyboardMarkup:
    """
    Build chat action buttons keyboard.
    
    Args:
        chat_id: Chat UUID
        _: Translator function
        can_reveal: Whether reveal button should be shown
        
    Returns:
        InlineKeyboardMarkup with chat action buttons
    """
    builder = InlineKeyboardBuilder()
    
    if can_reveal:
        builder.button(
            text=f"🔓 {_('chat.reveal')}",
            callback_data=ChatCallback(action="reveal", id=chat_id),
        )
    
    builder.button(
        text=f"🚫 {_('chat.report')}",
        callback_data=ChatCallback(action="report", id=chat_id),
    )
    builder.button(
        text=f"🚪 {_('chat.close')}",
        callback_data=ChatCallback(action="close", id=chat_id),
    )
    
    builder.adjust(3 if can_reveal else 2)
    return builder.as_markup()

def build_back_keyboard(_: Translator) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()
    _add_back_button(builder, _)
    return builder.as_markup()

def build_cancel_keyboard(_: Translator) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()
    
    builder.button(
        text=f"❌ {_('buttons.cancel')}",
        callback_data=NavigationCallback(action="cancel"),
    )
    
    return builder.as_markup()

def build_confirm_keyboard(_: Translator) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()
    
    builder.button(
        text=f"✅ {_('buttons.confirm')}",
        callback_data=NavigationCallback(action="confirm"),
    )
    builder.button(
        text=f"❌ {_('buttons.cancel')}",
        callback_data=NavigationCallback(action="cancel"),
    )
    
    builder.adjust(2)
    _add_back_button(builder, _)
    return builder.as_markup()

def build_categories_keyboard(_: Translator) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()
    
    builder.button(text=_('categories.private_house'), callback_data="cat:private_house")
    builder.button(text=_('categories.land'), callback_data="cat:land")
    builder.button(text=_('categories.new_construction'), callback_data="cat:new_construction")
    builder.button(text=_('categories.secondary'), callback_data="cat:secondary")
    builder.button(text=_('categories.commercial'), callback_data="cat:commercial")
    builder.button(text=_('categories.office_warehouse'), callback_data="cat:office_warehouse")
    builder.button(text=_('categories.villa'), callback_data="cat:villa")
    builder.button(text=_('categories.other'), callback_data="cat:other")
    
    builder.adjust(2)
    
    _add_back_button(builder, _)
    
    return builder.as_markup()

def build_start_over_keyboard(_: Translator) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()
    
    builder.button(text=_('buttons.start_over'), callback_data="menu:start_over")
    
    builder.adjust(1)
    return builder.as_markup()

def build_help_keyboard(_: Translator) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()
    
    builder.button(text=_('buttons.start_over'), callback_data="menu:start_over")
    
    builder.adjust(1)
    return builder.as_markup()

def build_settings_keyboard(_: Translator, is_premium: bool = False) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()
    
    # Subscription button - different text based on status
    if is_premium:
        builder.button(text=_('subscription.extend'), callback_data="subscription:plans")
    else:
        builder.button(text=_('subscription.subscribe'), callback_data="subscription:plans")
    
    builder.button(text=_('buttons.change_language'), callback_data="menu:change_language")
    builder.button(text=_('buttons.start_over'), callback_data="menu:start_over")
    
    # First row: subscription + language, second row: start over
    builder.adjust(2, 1)
    return builder.as_markup()

def build_profile_keyboard(_: Translator, is_premium: bool = False) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()
    
    # Subscription button - different text based on status
    if is_premium:
        builder.button(text=_('subscription.extend'), callback_data="subscription:from_profile")
    else:
        builder.button(text=_('subscription.subscribe'), callback_data="subscription:from_profile")
    
    builder.adjust(1)
    return builder.as_markup()

def build_cancel_operation_keyboard(_: Translator) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()
    
    builder.button(text=_('buttons.start_over'), callback_data="menu:start_over")
    
    builder.adjust(1)
    return builder.as_markup()

def _add_back_button(builder: InlineKeyboardBuilder, _: Translator) -> None:

    builder.row(
        InlineKeyboardButton(
            text=_('buttons.back'),
            callback_data=NavigationCallback(action="back").pack(),
        )
    )

def remove_keyboard() -> ReplyKeyboardRemove:

    return ReplyKeyboardRemove()

def build_vip_listings_keyboard(
    listings: list[dict[str, Any]],
    _: Translator,
) -> InlineKeyboardMarkup:
    """
    Build keyboard for selecting a listing to upgrade to VIP.
    
    Args:
        listings: List of listing dicts with id, price, rooms, area, is_vip
        _: Translator function
        
    Returns:
        InlineKeyboardMarkup with listing options
    """
    builder = InlineKeyboardBuilder()
    
    for listing in listings:
        listing_id = str(listing["id"])
        price = listing.get("price", 0)
        rooms = listing.get("rooms", "-")
        area = listing.get("area", 0)
        is_vip = listing.get("is_vip", False)
        
        vip_badge = "⭐ " if is_vip else ""
        text = f"{vip_badge}{rooms}🛏️ {area}m² - {price:,.0f} AZN"
        
        builder.button(
            text=text,
            callback_data=VIPCallback(action="select", id=listing_id),
        )
    
    builder.adjust(1)
    
    builder.row(
        InlineKeyboardButton(
            text=f"❌ {_('buttons.cancel')}",
            callback_data=VIPCallback(action="cancel").pack(),
        )
    )
    
    return builder.as_markup()

def build_vip_duration_keyboard(
    listing_id: str,
    _: Translator,
) -> InlineKeyboardMarkup:
    """
    Build keyboard for selecting VIP duration.
    
    Args:
        listing_id: Listing UUID
        _: Translator function
        
    Returns:
        InlineKeyboardMarkup with duration options
    """
    builder = InlineKeyboardBuilder()
    
    durations = [
        (7, "vip.duration_7"),
        (30, "vip.duration_30"),
        (90, "vip.duration_90"),
    ]
    
    for days, key in durations:
        builder.button(
            text=f"📅 {_(key)}",
            callback_data=VIPCallback(action="duration", id=listing_id, days=days),
        )
    
    builder.adjust(1)
    
    builder.row(
        InlineKeyboardButton(
            text=_('buttons.back'),
            callback_data=VIPCallback(action="back").pack(),
        ),
        InlineKeyboardButton(
            text=f"❌ {_('buttons.cancel')}",
            callback_data=VIPCallback(action="cancel").pack(),
        ),
    )
    
    return builder.as_markup()

def build_vip_confirm_keyboard(
    listing_id: str,
    days: int,
    _: Translator,
) -> InlineKeyboardMarkup:
    """
    Build keyboard for confirming VIP upgrade.
    
    Args:
        listing_id: Listing UUID
        days: VIP duration in days
        _: Translator function
        
    Returns:
        InlineKeyboardMarkup with confirm/cancel options
    """
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text=f"✅ {_('buttons.confirm')}",
        callback_data=VIPCallback(action="confirm", id=listing_id, days=days),
    )
    builder.button(
        text=f"❌ {_('buttons.cancel')}",
        callback_data=VIPCallback(action="cancel"),
    )
    
    builder.adjust(2)
    return builder.as_markup()

def build_subscription_status_keyboard(
    _: Translator,
    is_premium: bool = False,
) -> InlineKeyboardMarkup:
    """
    Build keyboard for subscription status view.
    
    Args:
        _: Translator function
        is_premium: Whether user has active premium subscription
        
    Returns:
        InlineKeyboardMarkup with subscription options
    """
    builder = InlineKeyboardBuilder()
    
    if is_premium:
        builder.button(
            text=_('subscription.view_plans'),
            callback_data=SubscriptionCallback(action="plans"),
        )
    else:
        builder.button(
            text=_('subscription.upgrade'),
            callback_data=SubscriptionCallback(action="plans"),
        )
    
    builder.button(
        text=_('buttons.back_simple'),
        callback_data=SubscriptionCallback(action="back_to_profile"),
    )
    
    builder.adjust(2)
    
    return builder.as_markup()

def build_subscription_plans_keyboard(
    plans: list[dict[str, Any]],
    _: Translator,
    lang: str = "en",
) -> InlineKeyboardMarkup:
    """
    Build keyboard for selecting a subscription plan.
    
    Args:
        plans: List of plan dicts with id, name, price, duration_days
        _: Translator function
        lang: Current language code
        
    Returns:
        InlineKeyboardMarkup with plan options
    """
    builder = InlineKeyboardBuilder()
    
    for plan in plans:
        plan_id = plan["id"]
        name = plan.get("name", plan_id)
        price = plan.get("price", 0)
        duration = plan.get("duration_days", 30)
        
        text = f"{name} - {price} AZN"
        
        builder.button(
            text=text,
            callback_data=SubscriptionCallback(action="select", plan_id=plan_id),
        )
    
    # 2 plans on one row, then back button
    builder.adjust(2, 1)
    
    builder.row(
        InlineKeyboardButton(
            text=_('buttons.back_simple'),
            callback_data="subscription:back_to_choice",
        )
    )
    
    return builder.as_markup()

def build_subscription_confirm_keyboard(
    plan_id: str,
    _: Translator,
) -> InlineKeyboardMarkup:
    """
    Build keyboard for confirming subscription purchase.
    
    Args:
        plan_id: Subscription plan ID
        _: Translator function
        
    Returns:
        InlineKeyboardMarkup with confirm/cancel options
    """
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text=f"✅ {_('buttons.confirm')}",
        callback_data=SubscriptionCallback(action="confirm", plan_id=plan_id),
    )
    builder.button(
        text=f"❌ {_('buttons.cancel')}",
        callback_data=SubscriptionCallback(action="cancel"),
    )
    
    builder.adjust(2)
    return builder.as_markup()
