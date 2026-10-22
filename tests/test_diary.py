"""Geração do diário com IA, sempre com uma IA FALSA (sem rede e sem custo)."""

import json
from datetime import date, time

import pytest

from app.config import Settings, get_settings
from app.llm.base import LLMError
from app.main import app
from app.routers.diary import get_llm
from app.schemas import DiaryBlock, RoutineBlockData, RoutineData
from app.services.diary import (
    NO_RECORD,
    ask_for_blocks,
    chunk_lines,
    ensure_routine,
    fill_gaps,
    merge_blocks,
)
from app.services.transcript import Line


class FakeLLM:
    """Devolve as respostas da lista, na ordem, e guarda os prompts recebidos."""

    name = "fake"
    model = "teste"

    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.prompts: list[str] = []

    def generate_json(self, system, prompt, schema):
        self.prompts.append(prompt)
        return self.responses.pop(0)


def resposta(*blocos: tuple[str, str, str]) -> str:
    return json.dumps(
        {"blocos": [{"inicio": i, "fim": f, "atividade": a, "descricao": ""} for i, f, a in blocos]}
    )


def bloco(inicio: str, fim: str, atividade: str, descricao: str = "") -> DiaryBlock:
    return DiaryBlock(inicio=inicio, fim=fim, atividade=atividade, descricao=descricao)


ROTINA = RoutineData(
    work_start=time(9),
    work_end=time(18),
    blocks=[RoutineBlockData(start=time(9, 15), end=time(9, 30), activity="Daily")],
)

# --- Validação e segunda chance --------------------------------------------


def test_resposta_valida_vira_blocos():
    llm = FakeLLM(resposta(("10:00", "10:40", "Refinamento com o PO")))
    assert ask_for_blocks(llm, "prompt") == [bloco("10:00", "10:40", "Refinamento com o PO")]


def test_resposta_invalida_ganha_segunda_chance_com_o_erro():
    invalida = json.dumps({"blocos": [{"inicio": "10:40", "fim": "10:00", "atividade": "X"}]})
    llm = FakeLLM(invalida, resposta(("10:00", "10:40", "X")))

    assert ask_for_blocks(llm, "prompt") == [bloco("10:00", "10:40", "X")]
    assert "rejeitada pela validação" in llm.prompts[1]


def test_duas_respostas_invalidas_viram_erro():
    llm = FakeLLM("isso não é json", '{"blocos": "também não"}')
    with pytest.raises(LLMError):
        ask_for_blocks(llm, "prompt")


# --- Consolidação em Python ------------------------------------------------


def test_chunking_respeita_o_limite_sem_quebrar_linhas():
    linhas = [Line(f"10:{i:02d}", "Fala", "x" * 40) for i in range(10)]
    partes = chunk_lines(linhas, max_chars=170)  # cada linha tem 54 caracteres
    assert [len(p) for p in partes] == [3, 3, 3, 1]
    assert sum(partes, []) == linhas


def test_junta_blocos_seguidos_da_mesma_atividade():
    blocos = [
        bloco("10:00", "10:30", "Refinamento", "Parte 1."),
        bloco("10:35", "11:00", "refinamento", "Parte 2."),  # outra parte do chunking
        bloco("11:00", "11:30", "Testes"),
    ]
    assert merge_blocks(blocos) == [
        bloco("10:00", "11:00", "Refinamento", "Parte 1. Parte 2."),
        bloco("11:00", "11:30", "Testes"),
    ]


def test_nao_junta_mesma_atividade_com_intervalo_grande():
    blocos = [bloco("10:00", "10:30", "Testes"), bloco("14:00", "15:00", "Testes")]
    assert len(merge_blocks(blocos)) == 2


def test_rotina_esquecida_pela_ia_e_incluida():
    resultado = ensure_routine([bloco("10:00", "11:00", "Refinamento")], ROTINA)
    assert resultado[0] == bloco("09:15", "09:30", "Daily")


def test_lacunas_do_expediente_viram_sem_registro_ate_o_ultimo_registro():
    blocos = [bloco("09:15", "09:30", "Daily"), bloco("11:00", "12:00", "Refinamento")]
    resultado = fill_gaps(blocos, ROTINA, last_activity_at=time(12))

    assert [(str(b.inicio)[:5], b.atividade) for b in resultado] == [
        ("09:00", NO_RECORD),
        ("09:15", "Daily"),
        ("09:30", NO_RECORD),
        ("11:00", "Refinamento"),
    ]  # depois das 12:00 não marca nada: a pessoa pode ter ido embora


# --- API --------------------------------------------------------------------


@pytest.fixture
def ia_falsa():
    llm = FakeLLM(resposta(("09:15", "09:30", "Daily"), ("10:00", "10:40", "Refinamento com o PO")))
    app.dependency_overrides[get_llm] = lambda: llm
    return llm


def registrar(client, ts, text):
    client.post("/api/entries", json={"ts": ts, "text": text})


def test_gera_salva_e_devolve_o_diario_do_dia(client, ia_falsa):
    registrar(client, "2026-10-26T10:00:00-03:00", "Diário, refinamento com o PO")

    dias = client.post("/api/diary/generate?start=2026-10-26").json()

    assert len(dias) == 1
    assert dias[0]["status"] == "draft"
    assert dias[0]["provider"] == "fake / teste"
    atividades = [b["atividade"] for b in dias[0]["blocks"]]
    assert "Refinamento com o PO" in atividades
    assert "10:00 [ANOTAÇÃO] Refinamento com o PO" in ia_falsa.prompts[0]
    # Ficou salvo: dá para buscar depois sem chamar a IA de novo
    assert client.get("/api/diary?start=2026-10-26").json() == dias


def test_revisao_salva_blocos_editados_em_ordem(client, ia_falsa):
    registrar(client, "2026-10-26T10:00:00-03:00", "olá")
    client.post("/api/diary/generate?start=2026-10-26")

    revisado = client.put(
        "/api/diary/2026-10-26",
        json={
            "blocks": [
                {"inicio": "11:00", "fim": "12:00", "atividade": "Testes", "descricao": ""},
                {"inicio": "10:00", "fim": "11:00", "atividade": "Refinamento", "descricao": "Ok"},
            ]
        },
    ).json()

    assert revisado["status"] == "reviewed"
    assert [b["inicio"] for b in revisado["blocks"]] == ["10:00", "11:00"]


def test_periodo_sem_registros_avisa(client, ia_falsa):
    response = client.post("/api/diary/generate?start=2026-10-26")
    assert response.status_code == 404


def test_sem_chave_da_ia_explica_o_que_configurar(client):
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, groq_api_key=None)
    registrar(client, "2026-10-26T10:00:00-03:00", "olá")

    response = client.post("/api/diary/generate?start=2026-10-26")
    assert response.status_code == 400
    assert "GROQ_API_KEY" in response.json()["detail"]


def test_falha_da_ia_vira_erro_502_com_mensagem(client):
    class IAForaDoAr(FakeLLM):
        def generate_json(self, system, prompt, schema):
            raise LLMError("Limite do plano gratuito do Groq atingido.")

    app.dependency_overrides[get_llm] = lambda: IAForaDoAr()
    registrar(client, "2026-10-26T10:00:00-03:00", "olá")

    response = client.post("/api/diary/generate?start=2026-10-26")
    assert response.status_code == 502
    assert "Groq" in response.json()["detail"]


def test_dia_util_sem_falas_so_tem_a_rotina():
    from app.services.diary import generate_day

    llm = FakeLLM()  # nenhuma resposta: se a IA for chamada, o teste quebra
    rotina_linha = [Line("09:15–09:30", "Rotina", "Daily")]
    assert generate_day(llm, date(2026, 10, 26), rotina_linha, ROTINA) == [
        bloco("09:15", "09:30", "Daily")
    ]
