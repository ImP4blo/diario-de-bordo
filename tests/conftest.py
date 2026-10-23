"""Fixtures compartilhadas pelos testes.

Cada teste ganha um banco SQLite novo, em memória: rápido, isolado e sem tocar
no seu banco real em data/.
"""

import os

# Precisa vir ANTES de importar o app: garante que nada nos testes aponte para
# o arquivo real, nem o init_db() que roda quando o app sobe.
os.environ["DATABASE_URL"] = "sqlite://"
# Nunca ler a rotina pessoal (config/routine.toml): os testes usam a de exemplo
os.environ["ROUTINE_FILE"] = "rotina-inexistente-nos-testes.toml"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402

import app.models  # noqa: E402, F401  (registra as tabelas)
from app.config import Settings, get_settings  # noqa: E402
from app.db import get_session  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def session():
    # StaticPool: todas as conexões usam o MESMO banco em memória
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()  # fecha a conexão; sem isso o Python avisa "unclosed database"


@pytest.fixture
def client(session):
    # Troca a dependência get_session pela sessão do banco de teste
    app.dependency_overrides[get_session] = lambda: session
    # _env_file=None: ignora o .env pessoal (chaves, SAVE_MODE...) para os testes
    # darem o mesmo resultado em qualquer máquina
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    yield TestClient(app)
    app.dependency_overrides.clear()
