"""Tabelas do banco.

Todas têm user_id desde já: na Etapa 1 ele é sempre "local"; na Etapa 2 vira o id
do usuário logado no Supabase, e PC e celular passam a ler o mesmo diário.
"""

from datetime import UTC, date, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class EntryKind(StrEnum):
    SPEECH = "speech"  # fala reconhecida pelo microfone
    NOTE = "note"  # anotação explícita ("Diário, ...") falada ou digitada
    PAUSE = "pause"  # pausa intencional: ts = início, ends_at = retomada
    CONFIRM = "confirm"  # "Sim, continuo em X" no alerta de inatividade
    ACTIVITY_CHANGE = "activity_change"  # "Não, agora estou em Y" no alerta


class Entry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)

    # Horários sempre em UTC. O "dia" do diário fica pré-calculado em local_date,
    # no fuso configurado, para buscar por dia sem fazer conta de fuso no SQL.
    ts: datetime
    ends_at: datetime | None = None
    local_date: date = Field(index=True)

    kind: EntryKind = EntryKind.SPEECH
    text: str = ""
    is_note: bool = False
    activity: str | None = None  # atividade atual que a entrada define/confirma

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
