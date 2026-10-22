"""Rotina fixa: expediente + blocos que se repetem todo dia (daily, intervalo...).

Na primeira vez que alguém usa o app, a rotina é carregada do arquivo TOML
(config/routine.toml, ou o de exemplo se ele não existir). Depois disso ela vive
no banco e é editada pela tela de Ajustes.
"""

import tomllib
from datetime import time
from pathlib import Path

from sqlmodel import Session, delete, select

from app.config import BASE_DIR
from app.models import RoutineBlock, WorkSchedule
from app.schemas import RoutineBlockData, RoutineData

EXAMPLE_FILE = BASE_DIR / "config" / "routine.example.toml"

# Usado só se não houver nenhum arquivo de rotina
DEFAULT_ROUTINE = RoutineData(work_start=time(9), work_end=time(18), blocks=[])


def load_routine_file(path: Path) -> RoutineData:
    """Lê o TOML (com chaves em português) e valida com os mesmos modelos da API."""
    with path.open("rb") as file:  # tomllib exige o arquivo em modo binário
        raw = tomllib.load(file)

    workday = raw.get("expediente", {})
    return RoutineData(
        work_start=workday.get("inicio", "09:00"),
        work_end=workday.get("fim", "18:00"),
        blocks=[
            RoutineBlockData(start=b["inicio"], end=b["fim"], activity=b["atividade"])
            for b in raw.get("blocos", [])
        ],
    )


def initial_routine(routine_file: Path) -> RoutineData:
    """Primeiro arquivo que existir: o da pessoa, o de exemplo ou o padrão embutido."""
    for path in (routine_file, EXAMPLE_FILE):
        if path.is_file():
            return load_routine_file(path)
    return DEFAULT_ROUTINE


def get_routine(session: Session, user_id: str, routine_file: Path) -> RoutineData:
    schedule = session.get(WorkSchedule, user_id)
    if schedule is None:
        # Primeira vez: carrega do arquivo e grava no banco
        return save_routine(session, user_id, initial_routine(routine_file))

    blocks = session.exec(
        select(RoutineBlock).where(RoutineBlock.user_id == user_id).order_by(RoutineBlock.start)
    )
    return RoutineData(
        work_start=schedule.work_start,
        work_end=schedule.work_end,
        blocks=[RoutineBlockData(start=b.start, end=b.end, activity=b.activity) for b in blocks],
    )


def save_routine(session: Session, user_id: str, routine: RoutineData) -> RoutineData:
    """Substitui a rotina inteira (mais simples que editar bloco por bloco)."""
    schedule = session.get(WorkSchedule, user_id) or WorkSchedule(
        user_id=user_id, work_start=routine.work_start, work_end=routine.work_end
    )
    schedule.work_start = routine.work_start
    schedule.work_end = routine.work_end
    session.add(schedule)

    session.exec(delete(RoutineBlock).where(RoutineBlock.user_id == user_id))
    for block in routine.blocks:
        session.add(
            RoutineBlock(user_id=user_id, start=block.start, end=block.end, activity=block.activity)
        )
    session.commit()
    return routine
