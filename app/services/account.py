"""Exclusão da conta e de todos os dados de uma pessoa (direito garantido pela LGPD).

Duas partes:
1. os dados do app (falas, rotina, diários, contador de uso), no nosso banco;
2. a conta de login, no Supabase Auth. Isso exige a "service role key", uma chave
   administrativa que fica só no servidor. Sem ela, só a parte 1 é feita.
"""

import urllib.error
import urllib.request
import uuid

from sqlmodel import Session, delete

from app.models import Entry, GeneratedDiary, RoutineBlock, UsageCounter, WorkSchedule


class AccountError(Exception):
    """Falha ao apagar a conta de login no Supabase."""


def delete_user_data(session: Session, user_id: str) -> dict[str, int]:
    """Apaga tudo o que pertence a `user_id`. Devolve quantas linhas saíram de cada tabela."""
    deleted = {}
    for name, model in (
        ("falas", Entry),
        ("diarios", GeneratedDiary),
        ("blocos_da_rotina", RoutineBlock),
        ("expediente", WorkSchedule),
    ):
        deleted[name] = session.exec(delete(model).where(model.user_id == user_id)).rowcount
    deleted["contador_de_uso"] = session.exec(
        delete(UsageCounter).where(UsageCounter.subject == f"user:{user_id}")
    ).rowcount
    session.commit()
    return deleted


def delete_auth_user(supabase_url: str, service_key: str, user_id: str) -> None:
    """Apaga a conta de login pela API administrativa do Supabase."""
    # O id vai dentro do endereço: conferir que é um UUID impede montar outro caminho
    try:
        safe_id = str(uuid.UUID(user_id))
    except ValueError as err:
        raise AccountError("Identificador de conta inválido.") from err

    request = urllib.request.Request(
        f"{supabase_url.rstrip('/')}/auth/v1/admin/users/{safe_id}",
        method="DELETE",
        headers={"apikey": service_key, "Authorization": f"Bearer {service_key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status not in (200, 204):
                raise AccountError(f"O Supabase respondeu {response.status}.")
    except urllib.error.HTTPError as err:
        raise AccountError(f"O Supabase recusou a exclusão ({err.code}).") from None
    except urllib.error.URLError:
        raise AccountError("Sem conexão com o Supabase.") from None
