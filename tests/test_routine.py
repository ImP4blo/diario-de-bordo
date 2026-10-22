import pytest

from app.config import Settings, get_settings
from app.deps import get_current_user_id
from app.main import app
from app.services.routine import EXAMPLE_FILE, load_routine_file

ROTINA_TOML = """
[expediente]
inicio = "08:00"
fim = "17:00"

[[blocos]]
inicio = "10:00"
fim = "10:15"
atividade = "Café"

[[blocos]]
inicio = "08:30"
fim = "08:45"
atividade = "Daily"
"""


@pytest.fixture
def rotina_pessoal(tmp_path):
    """Aponta ROUTINE_FILE para um TOML temporário (tmp_path é uma pasta descartável)."""
    arquivo = tmp_path / "routine.toml"
    arquivo.write_text(ROTINA_TOML, encoding="utf-8")
    app.dependency_overrides[get_settings] = lambda: Settings(routine_file=arquivo)
    return arquivo


def test_arquivo_de_exemplo_e_valido():
    rotina = load_routine_file(EXAMPLE_FILE)
    assert rotina.work_start < rotina.work_end
    assert len(rotina.blocks) > 0


def test_primeiro_acesso_carrega_o_arquivo_em_ordem_de_horario(client, rotina_pessoal):
    rotina = client.get("/api/routine").json()
    assert rotina == {
        "work_start": "08:00",
        "work_end": "17:00",
        "blocks": [
            {"start": "08:30", "end": "08:45", "activity": "Daily"},
            {"start": "10:00", "end": "10:15", "activity": "Café"},
        ],
    }


def test_sem_arquivo_pessoal_usa_o_exemplo(client):
    assert client.get("/api/routine").json() == load_routine_file(EXAMPLE_FILE).model_dump(
        mode="json"
    )


def test_salvar_substitui_a_rotina_inteira(client):
    nova = {
        "work_start": "09:00",
        "work_end": "18:00",
        "blocks": [{"start": "13:00", "end": "14:00", "activity": "Almoço"}],
    }
    assert client.put("/api/routine", json=nova).status_code == 200
    assert client.get("/api/routine").json() == nova


def test_apagar_todos_os_blocos_nao_traz_o_exemplo_de_volta(client):
    vazia = {"work_start": "09:00", "work_end": "18:00", "blocks": []}
    client.put("/api/routine", json=vazia)
    assert client.get("/api/routine").json()["blocks"] == []


@pytest.mark.parametrize(
    "rotina",
    [
        {"work_start": "18:00", "work_end": "09:00", "blocks": []},
        {
            "work_start": "09:00",
            "work_end": "18:00",
            "blocks": [{"start": "10:00", "end": "09:30", "activity": "Ao contrário"}],
        },
        {
            "work_start": "09:00",
            "work_end": "18:00",
            "blocks": [{"start": "10:00", "end": "10:30", "activity": ""}],
        },
    ],
)
def test_rotina_invalida_e_rejeitada(client, rotina):
    assert client.put("/api/routine", json=rotina).status_code == 422


def test_cada_pessoa_tem_sua_rotina(client):
    minha = {"work_start": "07:00", "work_end": "16:00", "blocks": []}
    client.put("/api/routine", json=minha)

    app.dependency_overrides[get_current_user_id] = lambda: "outra-pessoa"
    assert client.get("/api/routine").json()["work_start"] != "07:00"


def test_exportacao_intercala_a_rotina_nos_dias_uteis(client, rotina_pessoal):
    for ts in ("2026-10-26T09:00:00-03:00", "2026-10-31T09:00:00-03:00"):  # segunda e sábado
        client.post("/api/entries", json={"ts": ts, "text": "trabalhando"})

    texto = client.get("/api/export/transcript?start=2026-10-26&end=2026-11-01&fmt=md").text

    assert "Expediente: 08:00 às 17:00" in texto
    segunda, sabado = texto.split("## Sábado")
    assert segunda.index("08:30–08:45 [Rotina] Daily") < segunda.index("09:00 [Fala]")
    assert segunda.index("09:00 [Fala]") < segunda.index("10:00–10:15 [Rotina] Café")
    assert "[Rotina]" not in sabado
