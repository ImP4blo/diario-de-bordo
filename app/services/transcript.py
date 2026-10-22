"""Exportação da transcrição bruta em Markdown ou texto puro.

Serve para revisar o dia ou colar num chat de IA e montar o diário manualmente.
O arquivo Markdown já vem com um prompt sugerido no topo.
"""

from collections.abc import Iterable
from datetime import date, datetime
from itertools import groupby
from typing import Literal
from zoneinfo import ZoneInfo

from app.models import Entry, EntryKind
from app.schemas import RoutineData
from app.services.days import as_utc

ExportFormat = Literal["md", "txt"]

# Nomes fixos em vez do "locale" do sistema, que no Windows nem sempre está em pt-BR
WEEKDAYS = [
    "Segunda-feira",
    "Terça-feira",
    "Quarta-feira",
    "Quinta-feira",
    "Sexta-feira",
    "Sábado",
    "Domingo",
]

KIND_LABELS = {
    EntryKind.SPEECH: "Fala",
    EntryKind.NOTE: "ANOTAÇÃO",
    EntryKind.PAUSE: "Pausa",
    EntryKind.CONFIRM: "Confirmação",
    EntryKind.ACTIVITY_CHANGE: "Nova atividade",
    EntryKind.ACTIVITY_END: "Fim da atividade",
}

SUGGESTED_PROMPT = """\
> **Como usar:** cole este arquivo inteiro num chat de IA junto com o pedido abaixo.
>
> Monte meu diário de bordo a partir da transcrição abaixo. Devolva uma tabela por dia
> com as colunas Início | Fim | Atividade | Descrição. Regras: português profissional,
> frases curtas; use só os horários reais da transcrição, sem inventar atividades;
> agrupe falas da mesma atividade num bloco; ignore conversa irrelevante e ruído;
> linhas marcadas como ANOTAÇÃO têm prioridade; inclua os blocos [Rotina] como estão;
> marque lacunas dentro do expediente como "sem registro"."""


def format_day(day: date) -> str:
    """'Segunda-feira, 26/10/2026'"""
    return f"{WEEKDAYS[day.weekday()]}, {day:%d/%m/%Y}"


def _line(entry: Entry, tz: ZoneInfo) -> str:
    start = as_utc(entry.ts).astimezone(tz)
    time = f"{start:%H:%M}"
    if entry.ends_at:
        time += f"–{as_utc(entry.ends_at).astimezone(tz):%H:%M}"

    label = KIND_LABELS.get(entry.kind, entry.kind)
    text = entry.text or (entry.activity or "")
    return f"{time} [{label}] {text}".rstrip()


def _day_lines(
    day: date, entries: Iterable[Entry], routine: RoutineData | None, tz: ZoneInfo
) -> list[str]:
    """Linhas do dia: entradas + blocos da rotina (só em dias úteis), por horário."""
    timed = [(as_utc(e.ts).astimezone(tz).time(), _line(e, tz)) for e in entries]
    if routine and day.weekday() < 5:
        timed += [
            (b.start, f"{b.start:%H:%M}–{b.end:%H:%M} [Rotina] {b.activity}")
            for b in routine.blocks
        ]
    # sort é "estável": no mesmo horário, a ordem original se mantém
    timed.sort(key=lambda item: item[0])
    return [line for _, line in timed]


def build_transcript(
    entries: Iterable[Entry],
    start: date,
    end: date,
    person: str,
    tz: ZoneInfo,
    fmt: ExportFormat = "md",
    routine: RoutineData | None = None,
) -> str:
    """Monta o arquivo. `entries` deve vir ordenado por horário."""
    md = fmt == "md"
    period = f"{start:%d/%m/%Y}" if start == end else f"{start:%d/%m/%Y} a {end:%d/%m/%Y}"

    lines = [
        "# Transcrição: Diário de Bordo" if md else "TRANSCRIÇÃO: DIÁRIO DE BORDO",
        "",
        f"Pessoa: {person}",
        f"Período: {period}",
    ]
    if routine:
        lines.append(f"Expediente: {routine.work_start:%H:%M} às {routine.work_end:%H:%M}")
    lines.append(f"Gerado em: {datetime.now(tz):%d/%m/%Y %H:%M}")
    if md:
        lines += ["", SUGGESTED_PROMPT]

    by_day = groupby(entries, key=lambda e: e.local_date)
    has_any = False
    for day, day_entries in by_day:
        has_any = True
        lines += ["", f"## {format_day(day)}" if md else f"== {format_day(day)} ==", ""]
        day_lines = _day_lines(day, day_entries, routine, tz)
        lines += [f"- {line}" for line in day_lines] if md else day_lines

    if not has_any:
        lines += ["", "Nenhum registro no período."]

    return "\n".join(lines) + "\n"
