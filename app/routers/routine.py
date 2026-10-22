"""Rotina fixa e expediente da pessoa."""

from fastapi import APIRouter

from app.deps import SessionDep, SettingsDep, UserIdDep
from app.schemas import RoutineData
from app.services.routine import get_routine, save_routine

router = APIRouter(prefix="/api/routine", tags=["routine"])


@router.get("", response_model=RoutineData)
def read_routine(user_id: UserIdDep, session: SessionDep, settings: SettingsDep) -> RoutineData:
    return get_routine(session, user_id, settings.routine_file)


@router.put("", response_model=RoutineData)
def replace_routine(data: RoutineData, user_id: UserIdDep, session: SessionDep) -> RoutineData:
    """Substitui a rotina inteira pela enviada (é o que a tela de Ajustes faz ao salvar)."""
    return save_routine(session, user_id, data)
