from app.config import Settings, get_settings
from app.main import app


def falar(client, text, ts="2026-10-26T10:00:00-03:00", **extra):
    return client.post("/api/entries", json={"text": text, "ts": ts, **extra})


def atividade(client):
    return client.get("/api/entries/current-activity?day=2026-10-26").json()


def test_fala_com_diario_vira_anotacao_e_define_atividade(client):
    entrada = falar(client, "Diário, refinamento do card 1234 com o PO").json()
    assert entrada["kind"] == "note"
    assert entrada["is_note"] is True
    assert entrada["text"] == "Refinamento do card 1234 com o PO"
    assert entrada["activity"] == "Refinamento do card 1234 com o PO"


def test_fala_comum_continua_fala(client):
    entrada = falar(client, "vamos abrir a tela de cadastro").json()
    assert entrada["kind"] == "speech"
    assert entrada["activity"] is None


def test_anotacao_digitada_define_atividade(client):
    entrada = falar(client, "Testes da API de sinistros", kind="note").json()
    assert entrada["activity"] == "Testes da API de sinistros"


def test_anotacao_digitada_com_diario_perde_a_palavra_chave(client):
    entrada = falar(client, "Diário, almoço", kind="note").json()
    assert entrada["text"] == "Almoço"


def test_sem_anotacao_nao_ha_atividade(client):
    falar(client, "só conversa")
    assert atividade(client) == {"activity": None, "since": None, "last_explicit_at": None}


def test_anotacao_mais_recente_define_a_atividade_atual(client):
    falar(client, "Diário, daily", ts="2026-10-26T09:15:00-03:00")
    falar(client, "Diário, refinamento", ts="2026-10-26T10:00:00-03:00")
    falar(client, "conversa qualquer", ts="2026-10-26T10:05:00-03:00")

    resultado = atividade(client)
    assert resultado["activity"] == "Refinamento"
    assert resultado["since"] == "2026-10-26T13:00:00Z"


def test_confirmacao_atualiza_ultimo_registro_mas_nao_o_inicio(client):
    falar(client, "Diário, refinamento", ts="2026-10-26T10:00:00-03:00")
    falar(
        client,
        "Continua em: Refinamento",
        ts="2026-10-26T10:15:00-03:00",
        kind="confirm",
        activity="Refinamento",
    )

    resultado = atividade(client)
    assert resultado["since"] == "2026-10-26T13:00:00Z"
    assert resultado["last_explicit_at"] == "2026-10-26T13:15:00Z"


def test_modo_so_anotacoes_descarta_falas_comuns(client):
    app.dependency_overrides[get_settings] = lambda: Settings(save_mode="notes_only")

    assert falar(client, "conversa com o time").status_code == 204
    assert falar(client, "Diário, reunião com o PO").status_code == 201
    textos = [e["text"] for e in client.get("/api/entries?day=2026-10-26").json()]
    assert textos == ["Reunião com o PO"]
