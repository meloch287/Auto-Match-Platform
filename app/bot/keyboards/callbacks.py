from aiogram.filters.callback_data import CallbackData

class LanguageCallback(CallbackData, prefix="lang"):

    
    code: str

class RoleCallback(CallbackData, prefix="role"):

    
    role: str

class CategoryCallback(CallbackData, prefix="cat"):

    
    id: str

class LocationCallback(CallbackData, prefix="loc"):

    
    type: str
    id: str = ""

class MatchCallback(CallbackData, prefix="match"):

    
    action: str
    id: str

class ChatCallback(CallbackData, prefix="chat"):

    
    action: str
    id: str

class NavigationCallback(CallbackData, prefix="nav"):

    
    action: str
    target: str = ""

class FormFieldCallback(CallbackData, prefix="form"):

    
    field: str
    value: str

class PaginationCallback(CallbackData, prefix="page"):

    
    type: str
    page: int

class ListingCallback(CallbackData, prefix="listing"):

    
    action: str
    id: str

class RequirementCallback(CallbackData, prefix="req"):

    
    action: str
    id: str

class VIPCallback(CallbackData, prefix="vip"):

    
    action: str
    id: str = ""
    days: int = 0

class SubscriptionCallback(CallbackData, prefix="sub"):

    
    action: str
    plan_id: str = ""


class AutoRequirementCallback(CallbackData, prefix="auto_req"):
    """Callback for auto requirement actions."""
    action: str
    id: str


class AutoListingCallback(CallbackData, prefix="auto_lst"):
    """Callback for auto listing actions."""
    action: str
    id: str
