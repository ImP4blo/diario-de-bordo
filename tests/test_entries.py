from datetime import UTC, date, datetime

from app.models import Entry

SEGUNDA_10H_SP = "2026-10-26T10:00:00-03:00"


def criar(client, **dados):
    response = client.post("/api/entries", json={"ts": SEGUNDA_10H_SP, **dados})
    assert response.status_code == 201
    return response.json()


def test_cria_entrada_em_utc_e_calcula_dia_local(client):
    entrada = criar(client, text="  falando com o PO  ")
    assert entrada["ts"] == "2026-10-26T13:00:00Z"
    assert entrada["local_date"] == "2026-10-26"
    assert entrada["text"] == "falando com o PO"
    assert entrada["is_note"] is False


def test_anotacao_e_marcada_como_nota(client):
    entrada = criar(client, text="refinamento", kind="note")
    assert entrada["is_note"] is True


def test_lista_so_o_dia_pedido_em_ordem(client):
    criar(client, text="segunda", ts="2026-10-26T15:00:00-03:00")
    criar(client, text="segunda cedo", ts="2026-10-26T09:00:00-03:00")
    criar(client, text="terça", ts="2026-10-27T09:00:00-03:00")

    textos = [e["text"] for e in client.get("/api/entries?day=2026-10-26").json()]
    assert textos == ["segunda cedo", "segunda"]


def test_pausa_guarda_inicio_e_fim(client):
    pausa = criar(client, kind="pause", ts="2026-10-26T12:02:00-03:00")
    editada = client.patch(
        f"/api/entries/{pausa['id']}", json={"ends_at": "2026-10-26T13:05:00-03:00"}
    ).json()
    assert editada["ends_at"] == "2026-10-26T16:05:00Z"


def test_editar_horario_muda_o_dia(client):
    entrada = criar(client, text="x")
    editada = client.patch(
        f"/api/entries/{entrada['id']}", json={"ts": "2026-10-27T09:00:00-03:00"}
    ).json()
    assert editada["local_date"] == "2026-10-27"


def test_apaga_entrada(client):
    entrada = criar(client, text="apagar")
    assert client.delete(f"/api/entries/{entrada['id']}").status_code == 204
    assert client.get("/api/entries?day=2026-10-26").json() == []


def test_nao_mexe_em_entrada_de_outro_usuario(client, session):
    alheia = Entry(
        user_id="outra-pessoa",
        ts=datetime(2026, 10, 26, 13, tzinfo=UTC),
        local_date=date(2026, 10, 26),
    )
    session.add(alheia)
    session.commit()

    assert client.patch(f"/api/entries/{alheia.id}", json={"text": "hack"}).status_code == 404
    assert client.delete(f"/api/entries/{alheia.id}").status_code == 404
    assert client.get("/api/entries?day=2026-10-26").json() == []
