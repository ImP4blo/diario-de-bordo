"""Formatos de entrada e saída da API (o "contrato" com o frontend).

Separar isso das tabelas (models.py) evita que o cliente mande campos que só o
servidor deve controlar, como user_id, local_date ou created_at.
"""

from datetime import date, datetime, time
from typing import Annotated, Self

from pydantic import BaseModel, Field, PlainSerializer, field_validator, model_validator

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


# Horário que entra como "09:15" (ou "09:15:00") e sai sempre como "09:15"
ClockTime = Annotated[time, PlainSerializer(lambda t: t.strftime("%H:%M"), return_type=str)]


class RoutineBlockData(BaseModel):
    start: ClockTime
    end: ClockTime
    activity: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _inicio_antes_do_fim(self) -> Self:
        if self.start >= self.end:
            raise ValueError(f"O bloco '{self.activity}' termina antes de começar")
        return self


class RoutineData(BaseModel):
    """Rotina completa: usada para ler (GET) e para substituir tudo de uma vez (PUT)."""

    work_start: ClockTime
    work_end: ClockTime
    blocks: list[RoutineBlockData] = []

    @model_validator(mode="after")
    def _expediente_valido(self) -> Self:
        if self.work_start >= self.work_end:
            raise ValueError("O expediente termina antes de começar")
        # Guardamos sempre em ordem de horário
        self.blocks.sort(key=lambda block: block.start)
        return self


class DiaryBlock(BaseModel):
    """Um bloco do diário: "das 10:05 às 10:40, refinamento com o PO".

    Os nomes ficam em português porque são exatamente as chaves que pedimos à IA.
    """

    inicio: ClockTime
    fim: ClockTime
    atividade: str = Field(min_length=1, max_length=200)
    descricao: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def _inicio_antes_do_fim(self) -> Self:
        if self.inicio > self.fim:
            raise ValueError(f"O bloco '{self.atividade}' termina antes de começar")
        return self


class DiaryResult(BaseModel):
    """Formato que a IA deve devolver."""

    blocos: list[DiaryBlock]


class DiaryDay(BaseModel):
    day: date
    blocks: list[DiaryBlock]
    status: str = "draft"
    provider: str = ""


class CurrentActivity(BaseModel):
    activity: str | None = None
    since: datetime | None = None  # quando a atividade começou
    last_explicit_at: datetime | None = None  # último registro explícito (nota/confirmação)

    @field_validator("since", "last_explicit_at")
    @classmethod
    def _garante_utc(cls, value: datetime | None) -> datetime | None:
        return as_utc(value) if value else value
