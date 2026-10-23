"""Limite diário da IA do app e uso da chave própria."""

import json

import pytest
from fastapi import HTTPException
from google.genai import errors

from app.config import Settings, get_settings
from app.deps import get_current_user
from app.llm.base import LLMError
from app.llm.gemini_provider import GeminiProvider
from app.main import app
from app.routers.diary import LLMChoice, get_llm
from app.services.auth import CurrentUser

RESPOSTA = json.dumps(
    {"blocos": [{"inicio": "10:00", "fim": "10:30", "atividade": "Teste", "descricao": ""}]}
)


class IASempreOk:
    name, model = "fake", "teste"

    def generate_json(self, system, prompt, schema):
        return RESPOSTA


class IAQuebrada(IASempreOk):
    def generate_json(self, system, prompt, schema):
        raise LLMError("fora do ar")


def como(pessoa):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=pessoa, name=pessoa)


def usar_ia(ia=None, own_key=False):
    app.dependency_overrides[get_llm] = lambda: LLMChoice(ia or IASempreOk(), own_key=own_key)


@pytest.fixture
def online(client):
    """Modo public com limites pequenos: 2 por pessoa, 3 no total."""
    settings = Settings(
        _env_file=None,
        app_mode="public",
        supabase_url="https://x.supabase.co",
        daily_refinements_per_user=2,
        daily_refinements_total=3,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    como("ana")
    usar_ia()
    return client


def falar(client, dia):
    client.post("/api/entries", json={"text": "trabalhando", "ts": f"{dia}T10:00:00-03:00"})


def gerar(client, inicio, fim=None):
    return client.post(f"/api/diary/generate?start={inicio}&end={fim or inicio}")


def uso(client):
    return client.get("/api/diary/usage").json()


def test_pessoa_usa_ate_o_limite_e_depois_recebe_429(online):
    for dia in ("2026-10-26", "2026-10-27", "2026-10-28"):
        falar(online, dia)

    assert gerar(online, "2026-10-26").status_code == 200
    assert gerar(online, "2026-10-27").status_code == 200
    bloqueado = gerar(online, "2026-10-28")

    assert bloqueado.status_code == 429
    assert bloqueado.json()["detail"] == {
        "code": "quota_exhausted",
        "message": "Você usou seus refinamentos de hoje.",
        "remaining": 0,
    }


def test_periodo_maior_que_o_saldo_e_recusado_sem_gastar_nada(online):
    for dia in ("2026-10-26", "2026-10-27", "2026-10-28"):
        falar(online, dia)

    resposta = gerar(online, "2026-10-26", "2026-10-30")  # 3 dias com registro, saldo 2

    assert resposta.status_code == 429
    assert "precisa de 3" in resposta.json()["detail"]["message"]
    assert uso(online)["used"] == 0


def test_limite_total_do_app_vale_para_todo_mundo(online):
    for pessoa, dias in (
        ("ana", ["2026-10-26", "2026-10-27"]),
        ("bia", ["2026-10-26", "2026-10-27"]),
    ):  # noqa: E501
        como(pessoa)
        for dia in dias:
            falar(online, dia)

    como("ana")
    assert gerar(online, "2026-10-26", "2026-10-27").status_code == 200  # total: 2 de 3
    como("bia")
    resposta = gerar(online, "2026-10-26", "2026-10-27")  # bia tem saldo, mas o app não
    assert resposta.status_code == 429
    assert "limite diário do app" in resposta.json()["detail"]["message"]


def test_chave_propria_nao_tem_limite_nem_gasta_a_cota(online):
    usar_ia(own_key=True)
    for dia in ("2026-10-26", "2026-10-27", "2026-10-28"):
        falar(online, dia)
        assert gerar(online, dia).status_code == 200
    assert uso(online)["used"] == 0


def test_falha_da_ia_nao_gasta_refinamento(online):
    usar_ia(IAQuebrada())
    falar(online, "2026-10-26")
    assert gerar(online, "2026-10-26").status_code == 502
    assert uso(online) == {"enabled": True, "limit": 2, "used": 0, "remaining": 2}


def test_no_modo_local_nao_ha_limite(client):
    assert client.get("/api/diary/usage").json()["enabled"] is False


# --- Chave própria (Gemini) ----------------------------------------------------

CHAVE = "AIzaSyFAKE-chave-de-teste-1234567890"


def test_cabecalho_com_chave_usa_o_gemini_da_pessoa():
    escolha = get_llm(Settings(_env_file=None), x_user_ai_key=f"  {CHAVE}  ")
    assert escolha.own_key is True
    assert isinstance(escolha.llm, GeminiProvider)


def test_chave_curta_demais_e_recusada():
    with pytest.raises(HTTPException) as erro:
        get_llm(Settings(_env_file=None), x_user_ai_key="abc")
    assert erro.value.status_code == 400


@pytest.mark.parametrize(
    ("codigo", "mensagem_do_google", "esperado"),
    [
        (400, f"API key not valid: {CHAVE}", "chave do Gemini é inválida"),
        (429, "Quota exceeded", "limite gratuito"),
        (500, f"falha interna ao usar {CHAVE}", "[chave oculta]"),
    ],
)
def test_erros_do_gemini_nunca_mostram_a_chave(codigo, mensagem_do_google, esperado):
    provedor = GeminiProvider(CHAVE)
    erro = errors.APIError(codigo, {"error": {"code": codigo, "message": mensagem_do_google}})

    def falha(**_):
        raise erro

    provedor.client.models.generate_content = falha
    with pytest.raises(LLMError) as capturado:
        provedor.generate_json("sistema", "prompt", {})

    assert esperado in str(capturado.value)
    assert CHAVE not in str(capturado.value)
    assert capturado.value.__cause__ is None  # o erro original (com a chave) foi descartado
