"""Diário gerado pela IA: gerar, consultar e salvar a revisão."""

import json
from dataclasses import dataclass
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from app.deps import CurrentUserDep, SessionDep, SettingsDep, UserIdDep
from app.llm.base import LLMError, LLMNotConfiguredError, LLMProvider
from app.llm.factory import create_llm
from app.llm.gemini_provider import GeminiProvider
from app.models import Entry, GeneratedDiary, utcnow
from app.schemas import DiaryBlock, DiaryDay
from app.services.days import get_tz, today, week_bounds
from app.services.diary import generate_day
from app.services.diary_docx import diary_filename, render_diary_docx
from app.services.routine import get_routine, seed_file
from app.services.transcript import collect
from app.services.usage import QuotaExceededError, UsageLimiter

router = APIRouter(prefix="/api/diary", tags=["diary"])


@dataclass
class LLMChoice:
    llm: LLMProvider
    own_key: bool  # True = chave da própria pessoa: não conta no limite do app


def get_llm(
    settings: SettingsDep, x_user_ai_key: Annotated[str | None, Header()] = None
) -> LLMChoice:
    """IA do app (com limite) ou a da pessoa, se ela mandou a própria chave.

    A chave chega no cabeçalho X-User-AI-Key, vale só para esta requisição e não
    é salva nem registrada em lugar nenhum.
    """
    if x_user_ai_key and x_user_ai_key.strip():
        key = x_user_ai_key.strip()
        if len(key) < 20:
            raise HTTPException(status_code=400, detail="Essa chave parece incompleta.")
        return LLMChoice(GeminiProvider(key, settings.gemini_model), own_key=True)
    try:
        return LLMChoice(create_llm(settings), own_key=False)
    except LLMNotConfiguredError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


LLMDep = Annotated[LLMChoice, Depends(get_llm)]


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
    user: CurrentUserDep,
    session: SessionDep,
    settings: SettingsDep,
    choice: LLMDep,
    start: date | None = None,
    end: date | None = None,
) -> list[DiaryDay]:
    """Gera (ou gera de novo) o diário de cada dia do período que tenha registros."""
    llm = choice.llm
    start, end = _period(start, end)
    entries = session.exec(
        select(Entry)
        .where(Entry.user_id == user.id, Entry.local_date >= start, Entry.local_date <= end)
        .order_by(Entry.ts)
    )
    routine = get_routine(session, user.id, seed_file(settings))
    transcript = collect(entries, start, end, user.name, get_tz(), routine)
    if not transcript.days:
        raise HTTPException(status_code=404, detail="Nenhum registro no período para gerar.")

    limiter = UsageLimiter(session, settings)
    if not choice.own_key:
        try:
            limiter.check(user.id, needed=len(transcript.days))
        except QuotaExceededError as err:
            # 429 = "muitas requisições". O "code" deixa a tela saber que é o limite
            # diário e mostrar as opções (usar a própria chave ou só transcrição)
            raise HTTPException(
                status_code=429,
                detail={"code": "quota_exhausted", "message": str(err), "remaining": err.remaining},
            ) from err

    provider = f"{llm.name} / {llm.model}"
    result = []
    for day, lines in transcript.days:
        day_routine = routine if day.weekday() < 5 else None
        try:
            blocks = generate_day(llm, day, lines, day_routine)
        except LLMError as err:
            # 502: o problema foi no serviço de IA, não no pedido do usuário
            raise HTTPException(status_code=502, detail=str(err)) from err
        result.append(_to_day(_save(session, user.id, day, blocks, "draft", provider)))
        if not choice.own_key:
            limiter.consume(user.id)  # só conta o que deu certo
    return result


class UsageInfo(BaseModel):
    enabled: bool  # False no modo local (sem limite)
    limit: int
    used: int
    remaining: int


@router.get("/usage", response_model=UsageInfo)
def read_usage(user_id: UserIdDep, session: SessionDep, settings: SettingsDep) -> UsageInfo:
    """Quantos refinamentos com a IA do app a pessoa ainda tem hoje."""
    limiter = UsageLimiter(session, settings)
    usage = limiter.usage(user_id)
    return UsageInfo(
        enabled=limiter.enabled, limit=usage.limit, used=usage.used, remaining=usage.remaining
    )


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
    user: CurrentUserDep,
    session: SessionDep,
    start: date | None = None,
    end: date | None = None,
) -> Response:
    """Baixa o diário salvo (revisado ou não) do período em Word."""
    start, end = _period(start, end)
    days = read_diary(user.id, session, start, end)
    if not days:
        raise HTTPException(status_code=404, detail="Nenhum diário gerado no período.")

    content = render_diary_docx(user.name, start, end, days)
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
