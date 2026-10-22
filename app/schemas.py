"""Formatos de entrada e saída da API (o "contrato" com o frontend).

Separar isso das tabelas (models.py) evita que o cliente mande campos que só o
servidor deve controlar, como user_id, local_date ou created_at.
"""

from datetime import date, datetime

from pydantic import BaseModel, field_validator

from app.models import EntryKind
from app.services.days import as_utc


class EntryCreate(BaseModel):
    text: str = ""
    kind: EntryKind = EntryKind.SPEECH
    ts: datetime | None = None  # vazio = agora
    ends_at: datetime | None = None
    activity: str | None = None


class EntryUpdate(BaseModel):
    """Todos opcionais: só o que vier preenchido é alterado (PATCH)."""

    text: str | None = None
    kind: EntryKind | None = None
    ts: datetime | None = None
    ends_at: datetime | None = None
    activity: str | None = None


class EntryRead(BaseModel):
    id: int
    ts: datetime
    ends_at: datetime | None
    local_date: date
    kind: EntryKind
    text: str
    is_note: bool
    activity: str | None

    @field_validator("ts", "ends_at")
    @classmethod
    def _garante_utc(cls, value: datetime | None) -> datetime | None:
        return as_utc(value) if value else value


class CurrentActivity(BaseModel):
    activity: str | None = None
    since: datetime | None = None  # quando a atividade começou
    last_explicit_at: datetime | None = None  # último registro explícito (nota/confirmação)

    @field_validator("since", "last_explicit_at")
    @classmethod
    def _garante_utc(cls, value: datetime | None) -> datetime | None:
        return as_utc(value) if value else value
