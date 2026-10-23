"""Copia o histórico de um usuário de um banco para outro.

Uso principal: levar o que você gravou no modo local (SQLite, usuário "local") para
a sua conta online (Supabase, usuário = id da sua conta).

Regras, para poder rodar mais de uma vez sem estragar nada:
- falas: copia só as que ainda não existem no destino (mesmo horário, tipo e texto);
- rotina: só copia se a conta de destino ainda não tiver uma (não sobrescreve ajustes);
- diários: só copia os dias que ainda não têm diário no destino.
"""

from dataclasses import dataclass, field

from sqlalchemy import Engine
from sqlmodel import Session, select

from app.models import Entry, GeneratedDiary, RoutineBlock, WorkSchedule
from app.services.days import as_utc


@dataclass
class TransferReport:
    entries_copied: int = 0
    entries_skipped: int = 0
    routine_copied: bool = False
    diaries_copied: int = 0
    diaries_skipped: int = 0
    notes: list[str] = field(default_factory=list)


def transfer(
    source: Engine, target: Engine, from_user: str, to_user: str, execute: bool = False
) -> TransferReport:
    """Sem `execute`, só calcula o que seria feito (simulação) e não grava nada."""
    report = TransferReport()
    with Session(source) as src, Session(target) as dst:
        _copy_entries(src, dst, from_user, to_user, report)
        _copy_routine(src, dst, from_user, to_user, report)
        _copy_diaries(src, dst, from_user, to_user, report)
        if execute:
            dst.commit()
        else:
            dst.rollback()
    return report


def _copy_entries(src, dst, from_user, to_user, report):
    existing = {
        (as_utc(e.ts), e.kind, e.text)
        for e in dst.exec(select(Entry).where(Entry.user_id == to_user))
    }
    for entry in src.exec(select(Entry).where(Entry.user_id == from_user).order_by(Entry.ts)):
        key = (as_utc(entry.ts), entry.kind, entry.text)
        if key in existing:
            report.entries_skipped += 1
            continue
        existing.add(key)
        data = entry.model_dump(exclude={"id", "user_id"})
        for name in ("ts", "ends_at", "created_at", "updated_at"):
            if data[name] is not None:
                data[name] = as_utc(data[name])  # o SQLite devolve sem fuso; é UTC
        dst.add(Entry(user_id=to_user, **data))
        report.entries_copied += 1


def _copy_routine(src, dst, from_user, to_user, report):
    schedule = src.get(WorkSchedule, from_user)
    if schedule is None:
        return
    if dst.get(WorkSchedule, to_user) is not None:
        report.notes.append("A conta de destino já tem rotina: mantida como está.")
        return
    dst.add(
        WorkSchedule(user_id=to_user, work_start=schedule.work_start, work_end=schedule.work_end)
    )
    for block in src.exec(select(RoutineBlock).where(RoutineBlock.user_id == from_user)):
        dst.add(
            RoutineBlock(user_id=to_user, start=block.start, end=block.end, activity=block.activity)
        )
    report.routine_copied = True


def _copy_diaries(src, dst, from_user, to_user, report):
    for diary in src.exec(select(GeneratedDiary).where(GeneratedDiary.user_id == from_user)):
        if dst.get(GeneratedDiary, (to_user, diary.local_date)) is not None:
            report.diaries_skipped += 1
            continue
        data = diary.model_dump(exclude={"user_id"})
        data["updated_at"] = as_utc(data["updated_at"])
        dst.add(GeneratedDiary(user_id=to_user, **data))
        report.diaries_copied += 1
