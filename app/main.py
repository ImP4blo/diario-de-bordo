"""Ponto de entrada da aplicação.

O FastAPI faz duas coisas aqui:
1. expõe a API em /api/... (o frontend conversa com o backend só por ela);
2. serve os arquivos estáticos do frontend (HTML/CSS/JS) na raiz "/".

No modo local, os dois saem do mesmo endereço (localhost:8000). Online, o site
fica no Render Static Site e a API no Render Web Service: endereços diferentes,
por isso o CORS logo abaixo.
"""

import mimetypes
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR, get_settings
from app.db import init_db
from app.routers import config, diary, entries, export, me, routine

FRONTEND_DIR = BASE_DIR / "frontend"

# No Windows, o tipo do .js vem do registro do sistema e às vezes está errado
# ("text/plain"). Aí o Chrome se recusa a carregar os módulos JS. Forçamos o certo.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("application/manifest+json", ".webmanifest")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Roda uma vez quando o servidor sobe: garante que o banco existe."""
    init_db()
    yield


app = FastAPI(title="Diário de Bordo", version="0.1.0", lifespan=lifespan)

# CORS: o navegador só deixa o site oficial chamar a API (lista vinda do ambiente)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-User-AI-Key"],
    # Sem isto, o site não consegue ler o nome do arquivo nos downloads
    expose_headers=["Content-Disposition"],
)
app.include_router(config.router)
app.include_router(entries.router)
app.include_router(export.router)
app.include_router(routine.router)
app.include_router(diary.router)
app.include_router(me.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Rota simples para checar se o servidor está de pé."""
    return {"status": "ok"}


# Precisa vir por último: o mount na raiz "captura" tudo que não for rota da API.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
