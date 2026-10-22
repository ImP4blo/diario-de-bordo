"""Download da transcrição bruta (.md ou .txt)."""

from datetime import date

from fastapi import APIRouter, HTTPException, Response
from sqlmodel import select

from app.deps import SessionDep, SettingsDep, UserIdDep
from app.models import Entry
from app.services.days import get_tz, today, week_bounds
from app.services.routine import get_routine
from app.services.transcript import ExportFormat, build_transcript

router = APIRouter(prefix="/api/export", tags=["export"])

MEDIA_TYPES = {"md": "text/markdown", "txt": "text/plain"}


@router.get("/transcript")
def export_transcript(
    user_id: UserIdDep,
    session: SessionDep,
    settings: SettingsDep,
    start: date | None = None,
    end: date | None = None,
    fmt: ExportFormat = "md",
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
        .where(Entry.user_id == user_id, Entry.local_date >= start, Entry.local_date <= end)
        .order_by(Entry.ts)
    )
    routine = get_routine(session, user_id, settings.routine_file)
    content = build_transcript(
        session.exec(query), start, end, settings.display_name, get_tz(), fmt, routine
    )

    name = f"transcricao_{start}" + ("" if start == end else f"_a_{end}") + f".{fmt}"
    return Response(
        content,
        media_type=f"{MEDIA_TYPES[fmt]}; charset=utf-8",
        # "attachment" faz o navegador baixar o arquivo em vez de abrir na aba
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
