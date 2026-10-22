"""Dependências compartilhadas entre as rotas.

Os "apelidos" com Annotated (SessionDep, UserIdDep) são o jeito recomendado pelo
FastAPI: a rota só declara `session: SessionDep` e o framework injeta o valor.
"""

from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from app.config import get_settings
from app.db import get_session


def get_current_user_id() -> str:
    """Quem está usando o app.

    Na Etapa 1 é sempre o usuário local do .env. Na Etapa 2 esta é a ÚNICA função
    que muda: ela vai ler o token de login do Supabase. As rotas não mudam nada.
    """
    return get_settings().local_user_id


SessionDep = Annotated[Session, Depends(get_session)]
UserIdDep = Annotated[str, Depends(get_current_user_id)]
