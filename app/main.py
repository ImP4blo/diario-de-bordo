"""Ponto de entrada da aplicação.

O FastAPI faz duas coisas aqui:
1. expõe a API em /api/... (o frontend conversa com o backend só por ela);
2. serve os arquivos estáticos do frontend (HTML/CSS/JS) na raiz "/".

Manter o frontend separado da API desde já é o que permite, na Etapa 2,
hospedar os dois em lugares diferentes sem reescrever nada.
"""

import mimetypes
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR
from app.db import init_db
from app.routers import config, entries, export, routine

FRONTEND_DIR = BASE_DIR / "frontend"

# No Windows, o tipo do .js vem do registro do sistema e às vezes está errado
# ("text/plain"). Aí o Chrome se recusa a carregar os módulos JS. Forçamos o certo.
mimetypes.add_type("text/javascript", ".js")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Roda uma vez quando o servidor sobe: garante que o banco existe."""
    init_db()
    yield


app = FastAPI(title="Diário de Bordo", version="0.1.0", lifespan=lifespan)
app.include_router(config.router)
app.include_router(entries.router)
app.include_router(export.router)
app.include_router(routine.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Rota simples para checar se o servidor está de pé."""
    return {"status": "ok"}


# Precisa vir por último: o mount na raiz "captura" tudo que não for rota da API.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
