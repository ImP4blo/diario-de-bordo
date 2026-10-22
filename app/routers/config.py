"""Configurações públicas que o frontend precisa conhecer.

Nunca exponha chaves de API aqui: tudo o que esta rota devolve fica visível no navegador.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.services.days import today

router = APIRouter(prefix="/api/config", tags=["config"])


class PublicConfig(BaseModel):
    display_name: str
    timezone: str
    today: str
    save_mode: str
    inactivity_minutes: int


@router.get("", response_model=PublicConfig)
def get_public_config() -> PublicConfig:
    settings = get_settings()
    return PublicConfig(
        display_name=settings.display_name,
        timezone=settings.timezone,
        today=today().isoformat(),
        save_mode=settings.save_mode,
        inactivity_minutes=settings.inactivity_minutes,
    )
