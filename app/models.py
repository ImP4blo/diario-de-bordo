"""Tabelas do banco.

Todas têm user_id: no modo local ele é sempre "local"; online é o id da conta
logada no Supabase, e PC e celular passam a ler o mesmo diário.

Mudou alguma tabela? Gere a migração (veja migrations/README):
    python -m uv run alembic revision --autogenerate -m "descrição"
"""

from datetime import UTC, date, datetime, time
from enum import StrEnum

from sqlalchemy import DateTime, Enum
from sqlmodel import Field, SQLModel

# Data e hora COM fuso: no Postgres vira "timestamptz" (no SQLite tanto faz)
UTC_DATETIME = DateTime(timezone=True)


def utcnow() -> datetime:
    return datetime.now(UTC)


class EntryKind(StrEnum):
    SPEECH = "speech"  # fala reconhecida pelo microfone
    NOTE = "note"  # anotação explícita ("Diário, ...") falada ou digitada
    PAUSE = "pause"  # pausa intencional: ts = início, ends_at = retomada
    CONFIRM = "confirm"  # "Sim, continuo em X" no alerta de inatividade
    ACTIVITY_CHANGE = "activity_change"  # "Não, agora estou em Y" no alerta
    ACTIVITY_END = "activity_end"  # botão "Finalizar atividade": fica sem atividade atual


class Entry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)

    # Horários sempre em UTC. O "dia" do diário fica pré-calculado em local_date,
    # no fuso configurado, para buscar por dia sem fazer conta de fuso no SQL.
    ts: datetime = Field(sa_type=UTC_DATETIME)
    ends_at: datetime | None = Field(default=None, sa_type=UTC_DATETIME)
    local_date: date = Field(index=True)

    # native_enum=False: guarda como texto. Um "enum nativo" do Postgres exigiria
    # uma migração especial a cada tipo novo de entrada
    kind: EntryKind = Field(
        default=EntryKind.SPEECH, sa_type=Enum(EntryKind, native_enum=False, length=32)
    )
    text: str = ""
    is_note: bool = False
    activity: str | None = None  # atividade atual que a entrada define/confirma

    created_at: datetime = Field(default_factory=utcnow, sa_type=UTC_DATETIME)
    updated_at: datetime = Field(default_factory=utcnow, sa_type=UTC_DATETIME)


class GeneratedDiary(SQLModel, table=True):
    """Diário de um dia gerado pela IA (e depois revisado pela pessoa).

    Os blocos ficam como JSON em texto: são lidos e salvos sempre juntos, então
    não vale a pena uma tabela só para eles.
    """

    user_id: str = Field(primary_key=True)
    local_date: date = Field(primary_key=True)
    blocks_json: str
    status: str = "draft"  # draft = saiu da IA | reviewed = revisado pela pessoa
    provider: str = ""  # quem gerou (ex.: "groq / openai/gpt-oss-120b")
    updated_at: datetime = Field(default_factory=utcnow, sa_type=UTC_DATETIME)


class WorkSchedule(SQLModel, table=True):
    """Expediente da pessoa. Ter esta linha também indica que a rotina já foi
    carregada do arquivo de configuração (assim, apagar todos os blocos não faz
    a rotina de exemplo "voltar" sozinha)."""

    user_id: str = Field(primary_key=True)
    work_start: time
    work_end: time


class RoutineBlock(SQLModel, table=True):
    """Bloco fixo que se repete todo dia útil (daily, intervalo...).

    Horários "de relógio" (sem data nem fuso): 09:15 é 09:15 no fuso configurado.
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    start: time
    end: time
    activity: str
