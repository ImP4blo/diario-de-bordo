"""Ponto de entrada da aplicação.

O FastAPI faz duas coisas aqui:
1. expõe a API em /api/... (o frontend conversa com o backend só por ela);
2. serve os arquivos estáticos do frontend (HTML/CSS/JS) na raiz "/".

Manter o frontend separado da API desde já é o que permite, na Etapa 2,
hospedar os dois em lugares diferentes sem reescrever nada.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR

FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="Diário de Bordo", version="0.1.0")


@app.get("/api/health")
def health() -> dict[str, str]:
    """Rota simples para checar se o servidor está de pé."""
    return {"status": "ok"}


# Precisa vir por último: o mount na raiz "captura" tudo que não for rota da API.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
