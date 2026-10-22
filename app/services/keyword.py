"""Detecção da palavra-chave "Diário".

Frases que começam com "Diário" viram anotações explícitas: têm destaque na tela,
prioridade para a IA e definem a atividade atual.

Exemplos aceitos (a transcrição do Chrome varia bastante):
    "Diário, comecei o refinamento"   "diario: reunião com o PO"
    "DIÁRIO - almoço"                 "Diário comecei os testes"
"""

import re

# ^\s*        espaços no começo
# di[aá]rio   com ou sem acento (IGNORECASE cobre maiúsculas, inclusive "Á")
# \b          a palavra termina ali: "Diariamente" ou "Diários" não contam
# [\s,:;.!?\-–—]*  pontuação/espaço entre a palavra-chave e o texto
_KEYWORD = re.compile(r"^\s*di[aá]rio\b[\s,:;.!?\-–—]*", re.IGNORECASE)


def extract_note(text: str) -> str | None:
    """Se o texto começar com "Diário", devolve o resto da frase; senão, None.

    >>> extract_note("Diário, comecei o refinamento")
    'Comecei o refinamento'
    >>> extract_note("bom dia pessoal") is None
    True
    """
    match = _KEYWORD.match(text)
    if not match:
        return None

    rest = text[match.end() :].strip()
    if not rest:
        return None  # só "Diário" sozinho não diz nada
    return rest[0].upper() + rest[1:]
