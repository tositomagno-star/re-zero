from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin_assets import AssetUploadLimitMiddleware
from app.api.admin_assets import public_router as public_assets_router
from app.api.admin_assets import router as admin_assets_router
from app.api.admin_animations import router as admin_animations_router
from app.api.admin_combat_balance import router as admin_combat_balance_router
from app.api.admin_entity_profiles import router as admin_entity_profiles_router
from fastapi.responses import JSONResponse

from app.api.admin_content import public_router as published_content_router
from app.api.admin_content import router as admin_content_router
from app.api.auth import router as auth_router
from app.api.campaigns import router as campaigns_router
from app.api.combat import router as combat_router
from app.api.discord import router as discord_router
from app.api.health import router as health_router
from app.api.realtime import router as realtime_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(AssetUploadLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(campaigns_router)
app.include_router(combat_router)
app.include_router(discord_router)
app.include_router(realtime_router)
app.include_router(admin_content_router)
app.include_router(published_content_router)
app.include_router(admin_assets_router)
app.include_router(admin_animations_router)
app.include_router(admin_combat_balance_router)
app.include_router(admin_entity_profiles_router)
app.include_router(public_assets_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = [
        {
            "loc": error["loc"],
            "msg": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})
