"""Conexão com o banco.

O endereço vem de DATABASE_URL: um arquivo SQLite no modo local ou o Postgres do
Supabase online, sem mexer em nenhuma linha daqui.

As tabelas são criadas e atualizadas pelas migrações do Alembic (pasta migrations/),
que rodam sozinhas quando o servidor sobe.
"""

from collections.abc import Iterator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

from app.config import BASE_DIR, get_settings

ALEMBIC_INI = BASE_DIR / "alembic.ini"
# Primeira migração: bancos criados antes do Alembic já têm exatamente estas tabelas
INITIAL_REVISION = "a4c699fcccff"

_url = make_url(get_settings().database_url)
_is_sqlite = _url.get_backend_name() == "sqlite"

engine = create_engine(
    _url,
    # O SQLite, por padrão, só aceita a thread que abriu a conexão. O FastAPI atende
    # requisições em threads diferentes, então desligamos essa trava.
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    # Banco em memória (usado nos testes) precisa de UMA conexão compartilhada,
    # senão cada thread enxergaria um banco vazio diferente
    poolclass=StaticPool if _is_sqlite and not _url.database else None,
    # Online, conexões paradas podem ser derrubadas no meio do caminho: testa antes de usar
    pool_pre_ping=not _is_sqlite,
)


def run_migrations(target: Engine) -> None:
    """Leva o banco para a versão mais nova das migrações."""
    config = Config(str(ALEMBIC_INI))
    config.attributes["configure_logger"] = False  # não bagunça os logs do uvicorn
    with target.begin() as connection:
        config.attributes["connection"] = connection
        tables = inspect(connection).get_table_names()
        if "entry" in tables and "alembic_version" not in tables:
            # Banco criado antes das migrações existirem: marca como "já na versão
            # inicial" em vez de tentar criar de novo (e perder dados)
            command.stamp(config, INITIAL_REVISION)
        command.upgrade(config, "head")


def init_db() -> None:
    """Cria a pasta do arquivo SQLite (se for o caso) e aplica as migrações."""
    if _is_sqlite and _url.database:
        Path(_url.database).parent.mkdir(parents=True, exist_ok=True)
    run_migrations(engine)


def get_session() -> Iterator[Session]:
    """Dependência do FastAPI: abre uma sessão por requisição e fecha no final."""
    with Session(engine) as session:
        yield session
