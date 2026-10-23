"""Dependências compartilhadas entre as rotas.

Os "apelidos" com Annotated (SessionDep, UserIdDep) são o jeito recomendado pelo
FastAPI: a rota só declara `session: SessionDep` e o framework injeta o valor.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlmodel import Session

from app.config import Settings, get_settings
from app.db import get_session
from app.services.auth import AuthError, CurrentUser, TokenVerifier

SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[Session, Depends(get_session)]


@lru_cache
def _verifier(supabase_url: str, jwt_secret: str | None) -> TokenVerifier:
    # Um verificador só por projeto: ele guarda em cache as chaves públicas do Supabase
    return TokenVerifier(supabase_url, jwt_secret)


def get_token_verifier(settings: SettingsDep) -> TokenVerifier | None:
    """None no modo local: lá não existe login, então não há o que verificar."""
    if settings.app_mode == "local":
        return None
    if not settings.supabase_url:
        raise HTTPException(status_code=500, detail="SUPABASE_URL não configurada no servidor.")
    secret = settings.supabase_jwt_secret
    return _verifier(settings.supabase_url, secret.get_secret_value() if secret else None)


def get_current_user(
    settings: SettingsDep,
    verifier: Annotated[TokenVerifier | None, Depends(get_token_verifier)],
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentUser:
    """Quem está usando o app.

    Modo local: sempre o usuário do .env, sem login.
    Modo public: o dono do token de login enviado pelo navegador.
    """
    if verifier is None:
        return CurrentUser(id=settings.local_user_id, name=settings.display_name)

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="Faça login para continuar.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return verifier.verify(authorization[len("bearer ") :].strip())
    except AuthError as err:
        raise HTTPException(
            status_code=401, detail=str(err), headers={"WWW-Authenticate": "Bearer"}
        ) from err


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def get_current_user_id(user: CurrentUserDep) -> str:
    """Só o id: é o que a maioria das rotas precisa para filtrar os dados."""
    return user.id


UserIdDep = Annotated[str, Depends(get_current_user_id)]
