"""Conexão com o banco.

O endereço vem de DATABASE_URL. Hoje é um arquivo SQLite; na Etapa 2 basta trocar
a variável pela URL do Postgres do Supabase, sem mexer em nenhuma linha daqui.
"""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

_url = make_url(get_settings().database_url)
_is_sqlite = _url.get_backend_name() == "sqlite"

# O SQLite, por padrão, só aceita a thread que abriu a conexão. O FastAPI atende
# requisições em threads diferentes, então desligamos essa trava.
engine = create_engine(_url, connect_args={"check_same_thread": False} if _is_sqlite else {})


def init_db() -> None:
    """Cria a pasta do arquivo SQLite (se for o caso) e as tabelas que faltarem."""
    if _is_sqlite and _url.database:
        Path(_url.database).parent.mkdir(parents=True, exist_ok=True)
    # Importar os modelos "registra" as tabelas no SQLModel.metadata
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """Dependência do FastAPI: abre uma sessão por requisição e fecha no final."""
    with Session(engine) as session:
        yield session
