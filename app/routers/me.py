"""Dados da pessoa logada (usado no cabeçalho da página)."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.deps import CurrentUserDep

router = APIRouter(prefix="/api/me", tags=["me"])


class Me(BaseModel):
    id: str
    name: str
    email: str | None


@router.get("", response_model=Me)
def read_me(user: CurrentUserDep) -> Me:
    return Me(id=user.id, name=user.name, email=user.email)
