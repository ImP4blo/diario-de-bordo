"""Transferência do histórico local para a conta online (SQLite -> SQLite nos testes)."""

from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, select

from app.db import run_migrations
from app.models import Entry, EntryKind, GeneratedDiary, RoutineBlock, WorkSchedule
from app.services.transfer import transfer

CONTA = "33333333-3333-3333-3333-333333333333"


@pytest.fixture
def bancos(tmp_path):
    """Banco de origem (o "local") e de destino (a "nuvem"), fechados no fim do teste."""
    engines = []
    for nome in ("local.db", "nuvem.db"):
        engine = create_engine(f"sqlite:///{tmp_path / nome}")
        run_migrations(engine)
        engines.append(engine)
    yield engines
    for engine in engines:
        engine.dispose()


def popular_origem(engine):
    with Session(engine) as s:
        for minuto, texto in ((0, "bom dia"), (5, "refinamento")):
            s.add(
                Entry(
                    user_id="local",
                    ts=datetime(2026, 10, 22, 13, minuto, tzinfo=UTC),
                    local_date=date(2026, 10, 22),
                    kind=EntryKind.SPEECH,
                    text=texto,
                )
            )
        s.add(
            Entry(
                user_id="outra",
                ts=datetime(2026, 10, 22, 14, tzinfo=UTC),
                local_date=date(2026, 10, 22),
            )
        )
        s.add(WorkSchedule(user_id="local", work_start=time(9), work_end=time(18)))
        s.add(RoutineBlock(user_id="local", start=time(9, 15), end=time(9, 30), activity="Daily"))
        s.add(GeneratedDiary(user_id="local", local_date=date(2026, 10, 22), blocks_json="[]"))
        s.commit()


def contar(engine, model, user):
    with Session(engine) as s:
        return len(list(s.exec(select(model).where(model.user_id == user))))


def test_simulacao_nao_grava_nada(bancos):
    origem, destino = bancos
    popular_origem(origem)

    relatorio = transfer(origem, destino, "local", CONTA, execute=False)

    assert relatorio.entries_copied == 2
    assert contar(destino, Entry, CONTA) == 0


def test_copia_falas_rotina_e_diarios_so_do_usuario_local(bancos):
    origem, destino = bancos
    popular_origem(origem)

    relatorio = transfer(origem, destino, "local", CONTA, execute=True)

    assert (relatorio.entries_copied, relatorio.diaries_copied) == (2, 1)
    assert relatorio.routine_copied is True
    assert contar(destino, Entry, CONTA) == 2  # a fala de "outra" não veio
    assert contar(destino, RoutineBlock, CONTA) == 1
    assert contar(destino, GeneratedDiary, CONTA) == 1


def test_rodar_duas_vezes_nao_duplica(bancos):
    origem, destino = bancos
    popular_origem(origem)
    transfer(origem, destino, "local", CONTA, execute=True)

    segunda = transfer(origem, destino, "local", CONTA, execute=True)

    assert (segunda.entries_copied, segunda.entries_skipped) == (0, 2)
    assert segunda.routine_copied is False
    assert segunda.diaries_skipped == 1
    assert contar(destino, Entry, CONTA) == 2
