from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    language_select = State()
    role_select = State()
    market_type_select = State()


class ListingStates(StatesGroup):
    category = State()
    location_type = State()
    location_select = State()
    location_gps = State()
    price = State()
    payment_type = State()
    down_payment = State()
    rooms = State()
    area = State()
    floor = State()
    building_floors = State()
    renovation = State()
    documents = State()
    utilities = State()
    heating = State()
    property_age = State()
    description = State()
    photos = State()
    video_link = State()
    confirmation = State()


class RequirementStates(StatesGroup):
    category = State()
    location_type = State()
    location_select = State()
    district_select = State()  # Район для Баку
    metro_select = State()  # Метро для Баку
    landmark_input = State()  # Ориентир для Баку
    location_gps = State()
    price_range = State()
    price_min = State()
    price_max = State()
    payment_type = State()
    down_payment = State()
    rooms_range = State()
    rooms_min = State()
    rooms_max = State()
    area_range = State()
    area_min = State()
    area_max = State()
    floor_range = State()
    floor_min = State()
    floor_max = State()
    building_floors_min = State()
    building_floors_max = State()
    floor_preferences = State()
    renovation = State()
    documents = State()
    utilities = State()
    heating = State()
    property_age = State()
    comments = State()
    confirmation = State()


class ChatStates(StatesGroup):
    chatting = State()
    reveal_request = State()


class ManagementStates(StatesGroup):
    viewing_listing = State()
    editing_listing = State()
    viewing_requirement = State()
    editing_requirement = State()


class MatchStates(StatesGroup):
    viewing_matches = State()
    viewing_match_detail = State()


class VIPStates(StatesGroup):
    select_listing = State()
    select_duration = State()
    confirm_upgrade = State()


class SubscriptionStates(StatesGroup):
    viewing_status = State()
    select_plan = State()
    confirm_purchase = State()


class ListingEditStates(StatesGroup):
    select_field = State()
    edit_price = State()
    edit_rooms = State()
    edit_area = State()
    edit_description = State()


class RequirementEditStates(StatesGroup):
    select_field = State()
    edit_price = State()
    edit_rooms = State()
    edit_area = State()
    edit_price_min = State()
    edit_price_max = State()
    edit_rooms_min = State()
    edit_rooms_max = State()
    edit_area_min = State()
    edit_area_max = State()


# ============ AUTO STATES ============

class AutoListingStates(StatesGroup):
    """States for creating auto listing."""
    brand = State()
    model = State()
    year = State()
    mileage = State()
    engine_volume = State()
    fuel_type = State()
    transmission = State()
    body_type = State()
    color = State()
    price = State()
    city = State()
    description = State()
    photos = State()
    confirmation = State()


class AutoRequirementStates(StatesGroup):
    """States for creating auto requirement (buyer search)."""
    brands = State()
    models = State()
    year_range = State()
    price_range = State()
    mileage_max = State()
    fuel_type = State()
    transmission = State()
    body_type = State()
    city = State()
    confirmation = State()


class MatchBrowseStates(StatesGroup):
    """States for browsing matched listings."""
    viewing = State()
    respond_choice = State()
    writing_message = State()
    waiting_seller_approval = State()


class BotChatStates(StatesGroup):
    """States for in-bot chat between buyer and seller."""
    active_chat = State()
    writing_reply = State()


class AutoRequirementEditStates(StatesGroup):
    """States for editing auto requirement."""
    select_field = State()
    edit_brands = State()
    edit_year = State()
    edit_price = State()
    edit_mileage = State()


class AutoListingEditStates(StatesGroup):
    """States for editing auto listing."""
    select_field = State()
    edit_price = State()
    edit_mileage = State()
    edit_description = State()
