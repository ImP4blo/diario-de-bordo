"""Download da transcrição bruta (.txt, .docx ou .md)."""

from datetime import date

from fastapi import APIRouter, HTTPException, Response
from sqlmodel import select

from app.deps import CurrentUserDep, SessionDep, SettingsDep
from app.models import Entry
from app.services.days import get_tz, today, week_bounds
from app.services.routine import get_routine, seed_file
from app.services.transcript import ExportFormat, collect, render_docx, render_text

router = APIRouter(prefix="/api/export", tags=["export"])

MEDIA_TYPES = {
    "txt": "text/plain; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.get("/transcript")
def export_transcript(
    user: CurrentUserDep,
    session: SessionDep,
    settings: SettingsDep,
    start: date | None = None,
    end: date | None = None,
    fmt: ExportFormat = "txt",
) -> Response:
    """Sem datas, exporta a semana atual (segunda a sexta)."""
    if start is None:
        start, default_end = week_bounds(today())
        end = end or default_end
    end = end or start
    if end < start:
        raise HTTPException(status_code=422, detail="A data final é anterior à inicial")

    query = (
        select(Entry)
        .where(Entry.user_id == user.id, Entry.local_date >= start, Entry.local_date <= end)
        .order_by(Entry.ts)
    )
    routine = get_routine(session, user.id, seed_file(settings))
    transcript = collect(session.exec(query), start, end, user.name, get_tz(), routine)
    content = render_docx(transcript) if fmt == "docx" else render_text(transcript, fmt)

    name = f"transcricao_{start}" + ("" if start == end else f"_a_{end}") + f".{fmt}"
    return Response(
        content,
        media_type=MEDIA_TYPES[fmt],
        # "attachment" faz o navegador baixar o arquivo em vez de abrir na aba
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
