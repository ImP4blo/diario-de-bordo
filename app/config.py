"""Configurações do app, lidas de variáveis de ambiente (ou do arquivo .env).

Por que pydantic-settings? Ele valida os tipos na inicialização: se alguém puser
INACTIVITY_MINUTES=abc no .env, o app falha logo ao subir, com uma mensagem clara,
em vez de quebrar lá no meio do dia.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Raiz do projeto (a pasta acima de app/)
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Banco
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'diario.db'}"

    # Usuário e fuso
    local_user_id: str = "local"
    display_name: str = "Seu Nome"
    timezone: str = "America/Sao_Paulo"

    # Gravação
    save_mode: Literal["all", "notes_only"] = "all"
    inactivity_minutes: int = 15

    # Rotina fixa
    routine_file: Path = BASE_DIR / "config" / "routine.toml"

    # IA. SecretStr esconde o valor em logs e prints ("**********")
    llm_provider: Literal["groq", "anthropic"] = "groq"
    llm_model: str = ""
    groq_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    """Lê as configurações uma vez só e reaproveita (cache)."""
    return Settings()
