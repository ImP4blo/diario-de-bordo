"""CRUD das entradas do diário (falas, anotações, pausas, confirmações)."""

from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Response
from sqlmodel import Session, select

from app.deps import SessionDep, UserIdDep
from app.models import Entry, EntryKind, utcnow
from app.schemas import EntryCreate, EntryRead, EntryUpdate
from app.services.days import local_date_of, to_utc, today

router = APIRouter(prefix="/api/entries", tags=["entries"])


def _get_own_entry(entry_id: int, user_id: str, session: Session) -> Entry:
    """Busca a entrada garantindo que ela pertence ao usuário (senão, 404)."""
    entry = session.get(Entry, entry_id)
    if entry is None or entry.user_id != user_id:
        raise HTTPException(status_code=404, detail="Entrada não encontrada")
    return entry


def _optional_utc(dt: datetime | None) -> datetime | None:
    return to_utc(dt) if dt else None


@router.post("", response_model=EntryRead, status_code=201)
def create_entry(
    data: EntryCreate,
    user_id: UserIdDep,
    session: SessionDep,
) -> Entry:
    ts = to_utc(data.ts) if data.ts else utcnow()
    entry = Entry(
        user_id=user_id,
        ts=ts,
        ends_at=_optional_utc(data.ends_at),
        local_date=local_date_of(ts),
        kind=data.kind,
        text=data.text.strip(),
        is_note=data.kind == EntryKind.NOTE,
        activity=data.activity,
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
