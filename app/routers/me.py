"""Dados da pessoa logada e exclusão da conta."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.deps import CurrentUserDep, SessionDep, SettingsDep
from app.services import account

router = APIRouter(prefix="/api/me", tags=["me"])


class Me(BaseModel):
    id: str
    name: str
    email: str | None


class DeletionResult(BaseModel):
    deleted: dict[str, int]  # linhas apagadas por tabela
    login_deleted: bool  # a conta de login também foi apagada?
    message: str


@router.get("", response_model=Me)
def read_me(user: CurrentUserDep) -> Me:
    return Me(id=user.id, name=user.name, email=user.email)


@router.delete("", response_model=DeletionResult)
def delete_me(user: CurrentUserDep, session: SessionDep, settings: SettingsDep) -> DeletionResult:
    """Apaga TODOS os dados da pessoa e, se possível, a conta de login. Não tem volta."""
    if settings.app_mode == "local":
        raise HTTPException(status_code=400, detail="No modo local não há conta para apagar.")

    deleted = account.delete_user_data(session, user.id)

    key = settings.supabase_service_role_key
    if key is None:
        return DeletionResult(
            deleted=deleted,
            login_deleted=False,
            message="Seus dados foram apagados. A conta de login continua existindo.",
        )
    try:
        account.delete_auth_user(settings.supabase_url, key.get_secret_value(), user.id)
    except account.AccountError as err:
        return DeletionResult(
            deleted=deleted,
            login_deleted=False,
            message=f"Seus dados foram apagados, mas a conta de login não: {err}",
        )
    return DeletionResult(
        deleted=deleted,
        login_deleted=True,
        message="Sua conta e todos os seus dados foram apagados.",
    )
