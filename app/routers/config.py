"""Configurações públicas que o frontend precisa conhecer.

Nunca exponha chaves de API aqui: tudo o que esta rota devolve fica visível no navegador.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.deps import SettingsDep
from app.services.days import today

router = APIRouter(prefix="/api/config", tags=["config"])


class PublicConfig(BaseModel):
    app_mode: str
    # Dados públicos do Supabase, que o navegador usa para fazer o login
    supabase_url: str
    supabase_publishable_key: str
    timezone: str
    today: str
    save_mode: str
    inactivity_minutes: int
    phrase_gap_seconds: float


@router.get("", response_model=PublicConfig)
def get_public_config(settings: SettingsDep) -> PublicConfig:
    return PublicConfig(
        app_mode=settings.app_mode,
        supabase_url=settings.supabase_url,
        supabase_publishable_key=settings.supabase_publishable_key,
        timezone=settings.timezone,
        today=today().isoformat(),
        save_mode=settings.save_mode,
        inactivity_minutes=settings.inactivity_minutes,
        phrase_gap_seconds=settings.phrase_gap_seconds,
    )
