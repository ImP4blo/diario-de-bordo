"""Apagar a conta: some tudo da pessoa, e nada de mais ninguém."""

import pytest

from app.config import Settings, get_settings
from app.deps import get_current_user
from app.main import app
from app.services import account
from app.services.auth import CurrentUser

ANA = "11111111-1111-1111-1111-111111111111"
BIA = "22222222-2222-2222-2222-222222222222"


def como(pessoa):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=pessoa, name=pessoa)


@pytest.fixture
def online(client):
    def configurar(**extra):
        settings = Settings(
            _env_file=None, app_mode="public", supabase_url="https://x.supabase.co", **extra
        )
        app.dependency_overrides[get_settings] = lambda: settings

    configurar()
    client.configurar = configurar
    return client


def criar_dados(client, pessoa):
    como(pessoa)
    client.post(
        "/api/entries", json={"text": f"fala de {pessoa}", "ts": "2026-10-26T10:00:00-03:00"}
    )
    client.put(
        "/api/routine",
        json={
            "work_start": "09:00",
            "work_end": "18:00",
            "blocks": [{"start": "09:15", "end": "09:30", "activity": "Daily"}],
        },
    )
    client.put(
        "/api/diary/2026-10-26",
        json={"blocks": [{"inicio": "10:00", "fim": "11:00", "atividade": "X", "descricao": ""}]},
    )


def test_apaga_tudo_da_pessoa_e_nada_dos_outros(online):
    criar_dados(online, ANA)
    criar_dados(online, BIA)

    como(ANA)
    resposta = online.delete("/api/me").json()
    assert resposta["deleted"]["falas"] == 1
    assert resposta["deleted"]["diarios"] == 1
    assert resposta["deleted"]["blocos_da_rotina"] == 1
    assert online.get("/api/entries?day=2026-10-26").json() == []

    como(BIA)
    assert [e["text"] for e in online.get("/api/entries?day=2026-10-26").json()] == [
        f"fala de {BIA}"
    ]
    assert len(online.get("/api/diary?start=2026-10-26").json()) == 1


def test_sem_chave_administrativa_apaga_os_dados_e_avisa(online):
    criar_dados(online, ANA)
    como(ANA)
    resposta = online.delete("/api/me").json()
    assert resposta["login_deleted"] is False
    assert "conta de login continua" in resposta["message"]


def test_com_chave_administrativa_apaga_tambem_o_login(online, monkeypatch):
    chamadas = []
    monkeypatch.setattr(account, "delete_auth_user", lambda *args: chamadas.append(args))
    online.configurar(supabase_service_role_key="segredo-de-teste")
    como(ANA)

    resposta = online.delete("/api/me").json()

    assert resposta["login_deleted"] is True
    assert chamadas == [("https://x.supabase.co", "segredo-de-teste", ANA)]


def test_falha_ao_apagar_o_login_ainda_apaga_os_dados(online, monkeypatch):
    def falha(*_):
        raise account.AccountError("O Supabase recusou a exclusão (403).")

    monkeypatch.setattr(account, "delete_auth_user", falha)
    online.configurar(supabase_service_role_key="segredo-de-teste")
    criar_dados(online, ANA)
    como(ANA)

    resposta = online.delete("/api/me").json()
    assert resposta["login_deleted"] is False
    assert resposta["deleted"]["falas"] == 1
    assert "403" in resposta["message"]


def test_no_modo_local_nao_ha_conta_para_apagar(client):
    assert client.delete("/api/me").status_code == 400


def test_id_que_nao_e_uuid_nao_monta_endereco():
    with pytest.raises(account.AccountError, match="inválido"):
        account.delete_auth_user("https://x.supabase.co", "chave", "../../admin")
