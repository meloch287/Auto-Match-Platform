from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.responses import create_error_response, create_success_response
from app.core.config import get_settings

settings = get_settings()

__all__ = ["create_success_response", "create_error_response", "app", "create_app"]

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):

    yield

def create_app() -> FastAPI:

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Auto-Match Platform API for real estate buyers and sellers",
        docs_url="/api/docs" if settings.debug else None,
        redoc_url="/api/redoc" if settings.debug else None,
        openapi_url="/api/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )
    
    app.state.limiter = limiter
    
    _configure_cors(app)
    
    _configure_error_handlers(app)
    
    _include_routers(app)
    
    return app

def _configure_cors(app: FastAPI) -> None:

    origins = ["*"] if settings.debug else [
        "https://automatch.az",
        "https://www.automatch.az",
        "https://admin.automatch.az",
    ]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

def _configure_error_handlers(app: FastAPI) -> None:

    
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle Pydantic validation errors with consistent format."""
        errors = []
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error["loc"] if loc != "body")
            errors.append({
                "field": field,
                "message": error["msg"],
            })
        
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=create_error_response(
                code="VALIDATION_ERROR",
                message="Invalid input data",
                details=errors,
            ),
        )
    
    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Handle unexpected exceptions."""
        if not settings.debug:
            pass
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=create_error_response(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred" if not settings.debug else str(exc),
            ),
        )

def _include_routers(app: FastAPI) -> None:

    from app.api.v1.router import api_router
    from app.admin.routes import router as admin_web_router
    
    app.include_router(api_router, prefix=settings.api_prefix)
    app.include_router(admin_web_router)
    
    # Serve CRM static files
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    
    # Try multiple paths for CRM dist
    possible_paths = [
        Path("/app/crm/dist"),  # Docker container path
        Path(__file__).parent.parent.parent / "crm" / "dist",  # Local dev path
    ]
    
    crm_dist_path = None
    for path in possible_paths:
        if path.exists():
            crm_dist_path = path
            break
    
    if crm_dist_path:
        app.mount("/crm", StaticFiles(directory=str(crm_dist_path), html=True), name="crm")

app = create_app()

@app.get("/health", tags=["Health"])
async def health_check() -> dict:

    return create_success_response(data={"status": "healthy"})
