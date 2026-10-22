"""Regras de data e fuso horário.

Por que isso merece um arquivo próprio? Porque "que dia é hoje" depende do fuso:
23:30 em São Paulo já é 02:30 do dia seguinte em UTC. Se errarmos aqui, a fala
da noite cai no dia errado do diário.
"""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import get_settings


def get_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def to_utc(dt: datetime, tz: ZoneInfo | None = None) -> datetime:
    """Converte para UTC. Horário sem fuso ("naive") é tratado como horário local."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz or get_tz())
    return dt.astimezone(UTC)


def as_utc(dt: datetime) -> datetime:
    """O SQLite devolve datas sem fuso; como gravamos sempre em UTC, só reanexamos."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def local_date_of(dt: datetime, tz: ZoneInfo | None = None) -> date:
    """Dia do diário (no fuso local) ao qual um instante pertence."""
    return to_utc(dt, tz).astimezone(tz or get_tz()).date()


def today(tz: ZoneInfo | None = None) -> date:
    return datetime.now(tz or get_tz()).date()


def week_bounds(day: date) -> tuple[date, date]:
    """Segunda e sexta da semana de trabalho que contém `day`."""
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=4)
