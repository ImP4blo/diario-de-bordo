"""CRUD das entradas do diário (falas, anotações, pausas, confirmações)."""

from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Response
from sqlmodel import Session, select

from app.deps import SessionDep, SettingsDep, UserIdDep
from app.models import Entry, EntryKind, utcnow
from app.schemas import CurrentActivity, EntryCreate, EntryRead, EntryUpdate
from app.services.days import local_date_of, to_utc, today
from app.services.keyword import extract_note

# Entradas que mostram que a pessoa registrou o que está fazendo
_EXPLICIT_KINDS = (EntryKind.NOTE, EntryKind.CONFIRM, EntryKind.ACTIVITY_CHANGE)

router = APIRouter(prefix="/api/entries", tags=["entries"])


def _get_own_entry(entry_id: int, user_id: str, session: Session) -> Entry:
    """Busca a entrada garantindo que ela pertence ao usuário (senão, 404)."""
    entry = session.get(Entry, entry_id)
    if entry is None or entry.user_id != user_id:
        raise HTTPException(status_code=404, detail="Entrada não encontrada")
    return entry


def _optional_utc(dt: datetime | None) -> datetime | None:
    return to_utc(dt) if dt else None


@router.post(
    "",
    response_model=EntryRead,
    status_code=201,
    responses={204: {"description": "Fala descartada (SAVE_MODE=notes_only)"}},
)
def create_entry(
    data: EntryCreate,
    user_id: UserIdDep,
    session: SessionDep,
    settings: SettingsDep,
) -> Entry | Response:
    ts = to_utc(data.ts) if data.ts else utcnow()
    kind, text, activity = data.kind, data.text.strip(), data.activity

    # "Diário, ..." no começo transforma a fala em anotação explícita
    # (numa anotação digitada, só tira a palavra-chave do texto)
    if kind in (EntryKind.SPEECH, EntryKind.NOTE) and (note := extract_note(text)):
        kind, text = EntryKind.NOTE, note

    if kind == EntryKind.SPEECH and settings.save_mode == "notes_only":
        return Response(status_code=204)

    # Uma anotação define a atividade atual (se o cliente não mandou outra)
    if kind == EntryKind.NOTE and activity is None:
        activity = text

    entry = Entry(
        user_id=user_id,
        ts=ts,
        ends_at=_optional_utc(data.ends_at),
        local_date=local_date_of(ts),
        kind=kind,
        text=text,
        is_note=kind == EntryKind.NOTE,
        activity=activity,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


@router.get("", response_model=list[EntryRead])
def list_entries(
    user_id: UserIdDep,
    session: SessionDep,
    day: date | None = None,
) -> list[Entry]:
    """Lista as entradas de um dia (padrão: hoje), em ordem cronológica."""
    query = (
        select(Entry)
        .where(Entry.user_id == user_id, Entry.local_date == (day or today()))
        .order_by(Entry.ts)
    )
    return list(session.exec(query))


@router.get("/current-activity", response_model=CurrentActivity)
def current_activity(
    user_id: UserIdDep,
    session: SessionDep,
    day: date | None = None,
) -> CurrentActivity:
    """Atividade atual do dia: definida pela anotação (ou troca) mais recente."""
    query = (
        select(Entry)
        .where(
            Entry.user_id == user_id,
            Entry.local_date == (day or today()),
            Entry.kind.in_(_EXPLICIT_KINDS),
            Entry.activity.is_not(None),
        )
        .order_by(Entry.ts.desc())
    )
    explicit = list(session.exec(query))
    if not explicit:
        return CurrentActivity()

    latest = explicit[0]
    # "desde": quando a atividade foi DEFINIDA (confirmações não reiniciam)
    since = next((e.ts for e in explicit if e.kind != EntryKind.CONFIRM), latest.ts)
    return CurrentActivity(activity=latest.activity, since=since, last_explicit_at=latest.ts)


@router.patch("/{entry_id}", response_model=EntryRead)
def update_entry(
    entry_id: int,
    data: EntryUpdate,
    user_id: UserIdDep,
    session: SessionDep,
) -> Entry:
    entry = _get_own_entry(entry_id, user_id, session)
    # exclude_unset: só os campos que o cliente realmente mandou
    changes = data.model_dump(exclude_unset=True)

    if "ts" in changes and changes["ts"] is not None:
        changes["ts"] = to_utc(changes["ts"])
        changes["local_date"] = local_date_of(changes["ts"])
    if "ends_at" in changes:
        changes["ends_at"] = _optional_utc(changes["ends_at"])
    if changes.get("kind") is not None:
        changes["is_note"] = changes["kind"] == EntryKind.NOTE

    for field, value in changes.items():
        setattr(entry, field, value)
    entry.updated_at = utcnow()

    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=204)
def delete_entry(
    entry_id: int,
    user_id: UserIdDep,
    session: SessionDep,
) -> Response:
    entry = _get_own_entry(entry_id, user_id, session)
    session.delete(entry)
    session.commit()
    return Response(status_code=204)
