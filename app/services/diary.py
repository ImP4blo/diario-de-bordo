"""Geração do diário com IA.

Fluxo para cada dia:
1. Monta o texto do dia (mesmas linhas da transcrição exportada).
2. Se o dia for longo, divide em partes (chunking) e pede blocos para cada parte.
3. Valida a resposta com Pydantic; se vier inválida, pede de novo UMA vez,
   mostrando o erro para a IA corrigir.
4. Consolida em Python (sem IA): ordena, junta blocos vizinhos da mesma atividade,
   garante os blocos da rotina e marca lacunas do expediente como "Sem registro".

Por que consolidar em Python? É determinístico, grátis e testável. A IA faz o
que só ela sabe (entender a fala); o código faz o resto.
"""

from datetime import date, datetime, time, timedelta
from typing import Any

from pydantic import ValidationError

from app.llm.base import LLMError, LLMProvider
from app.schemas import DiaryBlock, DiaryResult, RoutineData
from app.services.transcript import ROUTINE_LABEL, Line, format_day

# ~12 mil caracteres ≈ 3 a 4 mil tokens: cabe com folga no limite por minuto do
# plano gratuito do Groq e mantém a IA focada.
MAX_CHUNK_CHARS = 12_000
# Lacunas menores que isso são só "respiros" entre atividades, não "sem registro"
MIN_GAP = timedelta(minutes=15)
NO_RECORD = "Sem registro"
# Uma fala até 5 min depois do fim de um bloco ainda conta como parte dele
COVERAGE_TOLERANCE = timedelta(minutes=5)

# Escrito à mão (em vez de gerado pelo Pydantic) para ficar simples e aceito por
# qualquer provedor. A validação de verdade é feita pelo DiaryResult.
DIARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "blocos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "inicio": {"type": "string", "description": "HH:MM"},
                    "fim": {"type": "string", "description": "HH:MM"},
                    "atividade": {"type": "string"},
                    "descricao": {"type": "string"},
                },
                "required": ["inicio", "fim", "atividade", "descricao"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["blocos"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """\
Você organiza o diário de bordo de um profissional de TI a partir da transcrição \
de voz do dia de trabalho dele.

Cada linha da transcrição tem o formato "HH:MM [Tipo] texto". Tipos:
- Fala: o que a pessoa disse (pode ter ruído e erros de reconhecimento de voz).
- ANOTAÇÃO: registro explícito do que a pessoa estava fazendo. Tem prioridade.
- Confirmação / Nova atividade / Fim da atividade: marcam continuidade, troca ou fim.
- Pausa: intervalo intencional (não é trabalho).
- Rotina: compromisso fixo do dia (ex.: daily).

Devolva os blocos de atividade do trecho, em ordem de horário. Regras:
- Português profissional, frases curtas e objetivas.
- Use apenas os horários reais da transcrição. Não invente atividades nem horários.
- Junte falas da mesma atividade num bloco só.
- Ignore conversa irrelevante, assuntos pessoais e ruído de transcrição.
- Anotações explícitas definem o nome da atividade; resuma-as (máximo ~8 palavras).
- Inclua cada bloco de Rotina com o mesmo horário e nome; use as falas que \
caírem dentro dele para preencher a descrição.
- Não crie blocos para pausas nem para períodos sem informação.
- "atividade" é um título curto; "descricao" diz o que foi feito em 1 ou 2 frases \
(pode ficar vazia se não houver detalhe).
- O "fim" de um bloco é o início da próxima atividade ou o horário da última fala dela."""


def _to_time(value: str) -> time:
    return time.fromisoformat(value)


def chunk_lines(lines: list[Line], max_chars: int = MAX_CHUNK_CHARS) -> list[list[Line]]:
    """Divide as linhas do dia em partes de até `max_chars`, sem quebrar uma linha."""
    chunks: list[list[Line]] = [[]]
    size = 0
    for line in lines:
        length = len(str(line)) + 1
        if chunks[-1] and size + length > max_chars:
            chunks.append([])
            size = 0
        chunks[-1].append(line)
        size += length
    return [chunk for chunk in chunks if chunk]


def build_prompt(
    day: date, lines: list[Line], routine: RoutineData | None, part: int, parts: int
) -> str:
    header = [f"Dia: {format_day(day)}"]
    if routine:
        header.append(f"Expediente: {routine.work_start:%H:%M} às {routine.work_end:%H:%M}")
    if parts > 1:
        header.append(f"Parte {part} de {parts} do dia (organize só este trecho).")
    return "\n".join([*header, "", "Transcrição:", *map(str, lines)])


def ask_for_blocks(llm: LLMProvider, prompt: str) -> list[DiaryBlock]:
    """Pede os blocos à IA e valida. Uma segunda chance se a resposta vier inválida."""
    raw = llm.generate_json(SYSTEM_PROMPT, prompt, DIARY_SCHEMA)
    try:
        return DiaryResult.model_validate_json(raw).blocos
    except ValidationError as first_error:
        retry_prompt = (
            f"{prompt}\n\nSua resposta anterior foi rejeitada pela validação:\n"
            f"{first_error}\nResponda de novo seguindo exatamente o formato pedido."
        )
        raw = llm.generate_json(SYSTEM_PROMPT, retry_prompt, DIARY_SCHEMA)
        try:
            return DiaryResult.model_validate_json(raw).blocos
        except ValidationError as err:
            raise LLMError("A IA devolveu um formato inválido duas vezes seguidas.") from err


def merge_blocks(blocks: list[DiaryBlock]) -> list[DiaryBlock]:
    """Ordena e junta blocos seguidos da mesma atividade (comum entre partes do chunking)."""
    merged: list[DiaryBlock] = []
    for block in sorted(blocks, key=lambda b: (b.inicio, b.fim)):
        last = merged[-1] if merged else None
        same_activity = last and last.atividade.strip().lower() == block.atividade.strip().lower()
        if last and same_activity and block.inicio <= _add(last.fim, MIN_GAP):
            descriptions = [d for d in (last.descricao, block.descricao) if d]
            merged[-1] = DiaryBlock(
                inicio=last.inicio,
                fim=max(last.fim, block.fim),
                atividade=last.atividade,
                descricao=" ".join(dict.fromkeys(descriptions)),  # sem repetir frase igual
            )
        else:
            merged.append(block)
    return merged


def ensure_routine(blocks: list[DiaryBlock], routine: RoutineData | None) -> list[DiaryBlock]:
    """Garante que todo bloco da rotina aparece uma vez, com o nome oficial.

    A IA às vezes reescreve o nome ("Almoco" em vez de "Almoço"). Por isso o bloco
    é reconhecido pelo horário de início, não pelo nome.
    """
    if not routine:
        return blocks
    result = list(blocks)
    for item in routine.blocks:
        index = next((i for i, b in enumerate(result) if b.inicio == item.start), None)
        if index is None:
            result.append(DiaryBlock(inicio=item.start, fim=item.end, atividade=item.activity))
        else:
            found = result[index]
            result[index] = found.model_copy(update={"atividade": item.activity})
    return sorted(result, key=lambda b: (b.inicio, b.fim))


def uncovered_times(blocks: list[DiaryBlock], lines: list[Line]) -> list[str]:
    """Horários de anotações (e da última fala) que ficaram fora de todos os blocos.

    A IA às vezes "esquece" um trecho inteiro. Conferir a cobertura é barato e
    pega esse erro sem depender dela.
    """
    spoken = [line for line in lines if line.label in ("Fala", "ANOTAÇÃO")]
    must_cover = [line for line in spoken if line.label == "ANOTAÇÃO"]
    if spoken and spoken[-1] not in must_cover:
        must_cover.append(spoken[-1])

    def covered(moment: time) -> bool:
        return any(b.inicio <= moment <= _add(b.fim, COVERAGE_TOLERANCE) for b in blocks)

    return [line.time for line in must_cover if not covered(_to_time(line.time[:5]))]


def fill_gaps(
    blocks: list[DiaryBlock], routine: RoutineData | None, last_activity_at: time | None
) -> list[DiaryBlock]:
    """Marca como "Sem registro" os buracos do expediente (sem inventar nada).

    Só até o último registro do dia: depois dele a pessoa pode simplesmente ter ido
    embora mais cedo, e isso não é "sem registro".
    """
    if not routine or not blocks:
        return blocks
    end_limit = min(routine.work_end, max(last_activity_at or routine.work_start, blocks[-1].fim))

    filled: list[DiaryBlock] = []
    cursor = routine.work_start
    for block in blocks:
        if _gap(cursor, block.inicio) >= MIN_GAP and block.inicio <= end_limit:
            filled.append(DiaryBlock(inicio=cursor, fim=block.inicio, atividade=NO_RECORD))
        filled.append(block)
        cursor = max(cursor, block.fim)
    return filled


def generate_day(
    llm: LLMProvider, day: date, lines: list[Line], routine: RoutineData | None
) -> list[DiaryBlock]:
    """Diário de um dia: IA por partes + consolidação em Python."""
    spoken = [line for line in lines if line.label != ROUTINE_LABEL]
    if not spoken:
        return ensure_routine([], routine)

    chunks = chunk_lines(lines)
    blocks: list[DiaryBlock] = []
    for index, chunk in enumerate(chunks, start=1):
        prompt = build_prompt(day, chunk, routine, index, len(chunks))
        chunk_blocks = ask_for_blocks(llm, prompt)
        if missing := uncovered_times(chunk_blocks, chunk):
            # Segunda chance dizendo exatamente o que faltou; se ainda faltar, segue
            # com o que veio (a pessoa completa na tela de revisão)
            chunk_blocks = ask_for_blocks(
                llm,
                f"{prompt}\n\nSua resposta anterior deixou sem bloco as falas destes "
                f"horários: {', '.join(missing)}. Refaça incluindo todas elas.",
            )
        blocks += chunk_blocks

    last_activity_at = _to_time(spoken[-1].time.split("–")[-1])
    blocks = ensure_routine(merge_blocks(blocks), routine)
    return fill_gaps(blocks, routine, last_activity_at)


def _add(moment: time, delta: timedelta) -> time:
    shifted = datetime.combine(date.min, moment) + delta
    return shifted.time() if shifted.date() == date.min else time.max


def _gap(start: time, end: time) -> timedelta:
    return datetime.combine(date.min, end) - datetime.combine(date.min, start)
