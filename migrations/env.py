"""Configuração do Alembic (migrações do banco).

O endereço do banco vem do mesmo lugar que o app usa (DATABASE_URL), então as
migrações sempre rodam no banco certo: SQLite local ou Postgres do Supabase.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

import app.models  # noqa: F401  (registra as tabelas no SQLModel.metadata)
from app.config import get_settings
from app.db import normalize_url

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def _url() -> str:
    # Quem chama pode passar outro endereço (ex.: os testes); senão, o do .env
    return config.get_main_option("sqlalchemy.url") or normalize_url(get_settings().database_url)


def run_migrations_offline() -> None:
    """Gera o SQL sem conectar no banco (alembic upgrade --sql)."""
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Se o app já abriu uma conexão (é o que o init_db faz), reaproveita
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return

    engine = engine_from_config(
        {"sqlalchemy.url": _url()}, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with engine.connect() as connection:
        _run(connection)


def _run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # SQLite não sabe alterar colunas: "batch" recria a tabela por baixo dos panos
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
