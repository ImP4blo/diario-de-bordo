"""As migrações criam o banco certo, atualizam bancos antigos e batem com os modelos."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlmodel import SQLModel

import app.models  # noqa: F401
from app.db import run_migrations

TABELAS = {"entry", "generateddiary", "routineblock", "workschedule"}


def _engine(tmp_path, nome="banco.db"):
    return create_engine(f"sqlite:///{tmp_path / nome}")


def test_banco_novo_ganha_todas_as_tabelas(tmp_path):
    engine = _engine(tmp_path)
    run_migrations(engine)
    assert TABELAS <= set(inspect(engine).get_table_names())
    engine.dispose()


def test_migracoes_batem_com_os_modelos(tmp_path):
    """Se este teste falhar, alguém mudou um modelo e esqueceu de gerar a migração."""
    engine = _engine(tmp_path)
    run_migrations(engine)
    with engine.connect() as connection:
        diferencas = compare_metadata(MigrationContext.configure(connection), SQLModel.metadata)
    engine.dispose()
    assert diferencas == []


def test_banco_antigo_sem_alembic_e_aproveitado_sem_perder_dados(tmp_path):
    engine = _engine(tmp_path, "antigo.db")
    # Como o app criava antes do Alembic: só as tabelas que existiam naquela época
    antigas = [SQLModel.metadata.tables[nome] for nome in TABELAS]
    SQLModel.metadata.create_all(engine, tables=antigas)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO workschedule (user_id, work_start, work_end) "
                "VALUES ('local', '09:00:00', '18:00:00')"
            )
        )

    run_migrations(engine)

    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM workschedule")).scalar() == 1
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
    engine.dispose()


def test_rodar_duas_vezes_nao_quebra(tmp_path):
    engine = _engine(tmp_path)
    run_migrations(engine)
    run_migrations(engine)  # é o que acontece toda vez que o servidor reinicia
    engine.dispose()


def test_endereco_do_supabase_ganha_o_driver_certo():
    from app.db import normalize_url

    assert normalize_url("postgresql://u:s@host:5432/db") == "postgresql+psycopg://u:s@host:5432/db"
    assert normalize_url("postgres://u:s@host/db") == "postgresql+psycopg://u:s@host/db"
    assert normalize_url("postgresql+psycopg://u:s@h/db") == "postgresql+psycopg://u:s@h/db"
    assert normalize_url("sqlite:///./data/diario.db") == "sqlite:///./data/diario.db"
