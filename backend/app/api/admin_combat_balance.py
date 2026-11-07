import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_admin, require_same_origin
from app.db.session import get_db
from app.models import CombatBalanceSetting
from app.schemas.combat_balance import CombatBalanceSettings
from app.services.combat_balance import load_combat_balance_settings


logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/admin/combat-balance",
    tags=["admin-combat-balance"],
    dependencies=[Depends(current_admin)],
)


@router.get("")
async def get_combat_balance(
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    settings = await load_combat_balance_settings(db)
    return settings.model_dump(mode="json")


@router.put("")
async def update_combat_balance(
    payload: CombatBalanceSettings,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    require_same_origin(request)
    record = await db.get(CombatBalanceSetting, 1)
    if record is None:
        record = CombatBalanceSetting(id=1, rules=[])
        db.add(record)
    record.rules = [rule.model_dump(mode="json") for rule in payload.rules]
    try:
        await db.commit()
    except SQLAlchemyError as error:
        await db.rollback()
        logger.exception("Could not save combat balance settings.")
        raise HTTPException(
            status_code=500,
            detail="Não foi possível salvar o balanceamento de combate.",
        ) from error
    return payload.model_dump(mode="json")
