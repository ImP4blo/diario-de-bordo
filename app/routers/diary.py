"""Diário gerado pela IA: gerar, consultar e salvar a revisão."""

import json
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from app.deps import SessionDep, SettingsDep, UserIdDep
from app.llm.base import LLMError, LLMNotConfiguredError, LLMProvider
from app.llm.factory import create_llm
from app.models import Entry, GeneratedDiary, utcnow
from app.schemas import DiaryBlock, DiaryDay
from app.services.days import get_tz, today, week_bounds
from app.services.diary import generate_day
from app.services.diary_docx import diary_filename, render_diary_docx
from app.services.routine import get_routine
from app.services.transcript import collect

router = APIRouter(prefix="/api/diary", tags=["diary"])


def get_llm(settings: SettingsDep) -> LLMProvider:
    try:
        return create_llm(settings)
    except LLMNotConfiguredError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


LLMDep = Annotated[LLMProvider, Depends(get_llm)]


class DiaryUpdate(BaseModel):
    blocks: list[DiaryBlock]


def _period(start: date | None, end: date | None) -> tuple[date, date]:
    """Sem datas: a semana atual. Só `start`: aquele dia."""
    if start is None:
        return week_bounds(today())
    end = end or start
    if end < start:
        raise HTTPException(status_code=422, detail="A data final é anterior à inicial")
    return start, end


def _to_day(diary: GeneratedDiary) -> DiaryDay:
    return DiaryDay(
        day=diary.local_date,
        blocks=json.loads(diary.blocks_json),
        status=diary.status,
        provider=diary.provider,
    )


def _save(
    session: Session, user_id: str, day: date, blocks: list[DiaryBlock], status: str, provider: str
) -> GeneratedDiary:
    diary = session.get(GeneratedDiary, (user_id, day)) or GeneratedDiary(
        user_id=user_id, local_date=day, blocks_json="[]"
    )
    diary.blocks_json = json.dumps([b.model_dump(mode="json") for b in blocks], ensure_ascii=False)
    diary.status = status
    diary.provider = provider
    diary.updated_at = utcnow()
    session.add(diary)
    session.commit()
    session.refresh(diary)
    return diary


@router.post("/generate", response_model=list[DiaryDay])
def generate(
    user_id: UserIdDep,
    session: SessionDep,
    settings: SettingsDep,
    llm: LLMDep,
    start: date | None = None,
    end: date | None = None,
) -> list[DiaryDay]:
    """Gera (ou gera de novo) o diário de cada dia do período que tenha registros."""
    start, end = _period(start, end)
    entries = session.exec(
        select(Entry)
        .where(Entry.user_id == user_id, Entry.local_date >= start, Entry.local_date <= end)
        .order_by(Entry.ts)
    )
    routine = get_routine(session, user_id, settings.routine_file)
    transcript = collect(entries, start, end, settings.display_name, get_tz(), routine)
    if not transcript.days:
        raise HTTPException(status_code=404, detail="Nenhum registro no período para gerar.")

    provider = f"{llm.name} / {llm.model}"
    result = []
    for day, lines in transcript.days:
        day_routine = routine if day.weekday() < 5 else None
        try:
            blocks = generate_day(llm, day, lines, day_routine)
        except LLMError as err:
            # 502: o problema foi no serviço de IA, não no pedido do usuário
            raise HTTPException(status_code=502, detail=str(err)) from err
        result.append(_to_day(_save(session, user_id, day, blocks, "draft", provider)))
    return result


@router.get("", response_model=list[DiaryDay])
def read_diary(
    user_id: UserIdDep, session: SessionDep, start: date | None = None, end: date | None = None
) -> list[DiaryDay]:
    start, end = _period(start, end)
    diaries = session.exec(
        select(GeneratedDiary)
        .where(
            GeneratedDiary.user_id == user_id,
            GeneratedDiary.local_date >= start,
            GeneratedDiary.local_date <= end,
        )
        .order_by(GeneratedDiary.local_date)
    )
    return [_to_day(diary) for diary in diaries]


@router.get("/docx")
def download_docx(
    user_id: UserIdDep,
    session: SessionDep,
    settings: SettingsDep,
    start: date | None = None,
    end: date | None = None,
) -> Response:
    """Baixa o diário salvo (revisado ou não) do período em Word."""
    start, end = _period(start, end)
    days = read_diary(user_id, session, start, end)
    if not days:
        raise HTTPException(status_code=404, detail="Nenhum diário gerado no período.")

    content = render_diary_docx(settings.display_name, start, end, days)
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{diary_filename(start, end)}"'},
    )


@router.put("/{day}", response_model=DiaryDay)
def save_review(day: date, data: DiaryUpdate, user_id: UserIdDep, session: SessionDep) -> DiaryDay:
    """Salva os blocos revisados pela pessoa na tela de revisão."""
    current = session.get(GeneratedDiary, (user_id, day))
    provider = current.provider if current else ""
    blocks = sorted(data.blocks, key=lambda b: (b.inicio, b.fim))
    return _to_day(_save(session, user_id, day, blocks, "reviewed", provider))
