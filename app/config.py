"""Configurações do app, lidas de variáveis de ambiente (ou do arquivo .env).

Por que pydantic-settings? Ele valida os tipos na inicialização: se alguém puser
INACTIVITY_MINUTES=abc no .env, o app falha logo ao subir, com uma mensagem clara,
em vez de quebrar lá no meio do dia.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Raiz do projeto (a pasta acima de app/)
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Banco
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'diario.db'}"

    # Modo de uso:
    #   local  = no seu PC, sem login (um usuário só, o LOCAL_USER_ID)
    #   public = online, com login pelo Supabase (cada conta vê só o próprio diário)
    app_mode: Literal["local", "public"] = "local"

    # Supabase Auth (só no modo public). A publishable key é PÚBLICA por natureza:
    # o navegador precisa dela para fazer o login. Segredo é a senha do banco.
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    # Só para projetos antigos do Supabase, que assinam tokens com segredo (HS256)
    supabase_jwt_secret: SecretStr | None = None
    # Chave ADMINISTRATIVA do Supabase (segredo!): usada só para apagar contas de login
    # no "Apagar minha conta". Nunca vai para o navegador.
    supabase_service_role_key: SecretStr | None = None

    # CORS: quais sites podem chamar a API pelo navegador. Online, o site e a API
    # ficam em endereços diferentes; sem isso, o navegador bloqueia as chamadas.
    # FRONTEND_HOST vem do Render (só o domínio); ALLOWED_ORIGINS aceita uma
    # lista separada por vírgula (ex.: http://localhost:8000).
    frontend_host: str = ""
    allowed_origins: str = ""

    # Usuário e fuso
    local_user_id: str = "local"
    display_name: str = "Seu Nome"
    timezone: str = "America/Sao_Paulo"

    # Gravação
    save_mode: Literal["all", "notes_only"] = "all"
    inactivity_minutes: int = Field(default=15, ge=1, le=240)
    # Segundos de silêncio que encerram uma fala (junta os trechos picados do Chrome)
    phrase_gap_seconds: float = Field(default=5, ge=1, le=60)

    # Rotina fixa
    routine_file: Path = BASE_DIR / "config" / "routine.toml"

    # IA. SecretStr esconde o valor em logs e prints ("**********")
    llm_provider: Literal["groq", "anthropic"] = "groq"
    llm_model: str = ""
    groq_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    # Modelo usado com a chave PRÓPRIA da pessoa (Google AI Studio)
    gemini_model: str = ""

    # Limites diários da IA paga por você (só no modo public; 1 refinamento = 1 dia gerado).
    # Quem usar a própria chave não entra na conta.
    daily_refinements_per_user: int = Field(default=3, ge=0)
    daily_refinements_total: int = Field(default=100, ge=0)

    @property
    def cors_origins(self) -> list[str]:
        origins = [o.strip().rstrip("/") for o in self.allowed_origins.split(",") if o.strip()]
        if self.frontend_host:
            origins.append(f"https://{self.frontend_host}")
        return origins


@lru_cache
def get_settings() -> Settings:
    """Lê as configurações uma vez só e reaproveita (cache)."""
    return Settings()
