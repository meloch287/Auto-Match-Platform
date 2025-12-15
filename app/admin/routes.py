from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/admin", tags=["Admin Web"])


@router.get("", response_class=RedirectResponse)
@router.get("/", response_class=RedirectResponse)
async def admin_panel():
    return RedirectResponse(url="/crm/")
