"""Login (modo public): tokens assinados de verdade, com chaves de teste."""

import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.config import Settings, get_settings
from app.deps import get_token_verifier
from app.main import app
from app.services.auth import TokenVerifier

SUPABASE_URL = "https://projeto-teste.supabase.co"
ISSUER = f"{SUPABASE_URL}/auth/v1"
CHAVE_PRIVADA = ec.generate_private_key(ec.SECP256R1())  # o "Supabase de mentira"


class FakeJWKClient:
    """Faz o papel das chaves públicas que o Supabase publica (JWKS)."""

    def get_signing_key_from_jwt(self, token):
        return SimpleNamespace(key=CHAVE_PRIVADA.public_key())


def token(sub="pessoa-1", chave=CHAVE_PRIVADA, **mudancas):
    claims = {
        "sub": sub,
        "aud": "authenticated",
        "iss": ISSUER,
        "exp": int(time.time()) + 3600,
        "email": f"{sub}@exemplo.com",
        "user_metadata": {"full_name": f"Nome de {sub}"},
        **mudancas,
    }
    return jwt.encode(claims, chave, algorithm="ES256")


def auth(t):
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture
def modo_publico(client):
    settings = Settings(_env_file=None, app_mode="public", supabase_url=SUPABASE_URL)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_token_verifier] = lambda: TokenVerifier(
        SUPABASE_URL, jwk_client=FakeJWKClient()
    )
    return client


def test_sem_login_e_barrado(modo_publico):
    response = modo_publico.get("/api/entries")
    assert response.status_code == 401
    assert response.json()["detail"] == "Faça login para continuar."


def test_com_login_valido_entra_e_sabe_quem_e(modo_publico):
    me = modo_publico.get("/api/me", headers=auth(token("pessoa-1"))).json()
    assert me == {"id": "pessoa-1", "name": "Nome de pessoa-1", "email": "pessoa-1@exemplo.com"}


def test_sem_nome_no_google_usa_o_comeco_do_email(modo_publico):
    t = token("pessoa-1", user_metadata={})
    assert modo_publico.get("/api/me", headers=auth(t)).json()["name"] == "pessoa-1"


@pytest.mark.parametrize(
    "token_ruim",
    [
        token(exp=int(time.time()) - 10),  # vencido
        token(aud="anon"),  # não é de usuário logado
        token(iss="https://outro-projeto.supabase.co/auth/v1"),  # de outro projeto
        token(chave=ec.generate_private_key(ec.SECP256R1())),  # assinatura falsa
        "isso-nem-e-um-token",
    ],
)
def test_token_invalido_e_barrado(modo_publico, token_ruim):
    assert modo_publico.get("/api/me", headers=auth(token_ruim)).status_code == 401


def test_cada_pessoa_ve_so_o_proprio_diario(modo_publico):
    def falar(pessoa, texto):
        entrada = {"text": texto, "ts": "2026-10-26T10:00:00-03:00"}
        modo_publico.post("/api/entries", json=entrada, headers=auth(token(pessoa)))

    def ver(pessoa):
        resposta = modo_publico.get("/api/entries?day=2026-10-26", headers=auth(token(pessoa)))
        return [e["text"] for e in resposta.json()]

    falar("ana", "da Ana")
    falar("bia", "da Bia")
    assert ver("ana") == ["da Ana"]
    assert ver("bia") == ["da Bia"]


def test_projeto_antigo_com_segredo_hs256_tambem_funciona(modo_publico):
    segredo = "segredo-de-teste-com-pelo-menos-32-caracteres!"
    app.dependency_overrides[get_token_verifier] = lambda: TokenVerifier(
        SUPABASE_URL, jwt_secret=segredo, jwk_client=FakeJWKClient()
    )
    t = jwt.encode(
        {"sub": "antigo", "aud": "authenticated", "iss": ISSUER, "exp": int(time.time()) + 60},
        segredo,
        algorithm="HS256",
    )
    assert modo_publico.get("/api/me", headers=auth(t)).json()["id"] == "antigo"


def test_rotas_publicas_continuam_abertas(modo_publico):
    assert modo_publico.get("/api/health").status_code == 200
    config = modo_publico.get("/api/config").json()
    assert config["app_mode"] == "public"
    assert config["supabase_url"] == SUPABASE_URL


def test_modo_local_nao_pede_login(client):
    assert client.get("/api/me").json()["id"] == "local"
