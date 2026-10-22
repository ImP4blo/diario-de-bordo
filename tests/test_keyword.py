import pytest

from app.services.keyword import extract_note


@pytest.mark.parametrize(
    ("fala", "esperado"),
    [
        ("Diário, comecei o refinamento do card 1234", "Comecei o refinamento do card 1234"),
        ("diário comecei os testes", "Comecei os testes"),
        ("Diario: reunião com o PO", "Reunião com o PO"),  # sem acento
        ("DIÁRIO - almoço", "Almoço"),  # maiúsculas e travessão
        ("  Diário.   pausa pro café", "Pausa pro café"),  # espaços e ponto
    ],
)
def test_reconhece_anotacao(fala, esperado):
    assert extract_note(fala) == esperado


@pytest.mark.parametrize(
    "fala",
    [
        "bom dia pessoal",
        "vou abrir o diário depois",  # "diário" no meio não conta
        "Diariamente a gente faz a daily",  # começa com "Diari", mas é outra palavra
        "Diários de bordo são obrigatórios",
        "Diário",  # palavra-chave sozinha não tem conteúdo
        "Diário, ",
    ],
)
def test_ignora_o_que_nao_e_anotacao(fala):
    assert extract_note(fala) is None
