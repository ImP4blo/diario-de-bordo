"""Gera o PDF de instruções de uso (frontend/instrucoes.pdf).

Rode sempre que o app ganhar uma função nova:
    python -m uv run python scripts/gerar_instrucoes.py

O conteúdo fica em SECTIONS, separado do layout: para mudar o texto, não é
preciso entender o código de desenho do PDF.

Obs.: as fontes padrão do PDF (Helvetica) só têm os caracteres "latin-1".
Acentos do português funcionam, mas símbolos como "•", "–" ou "◀" não.
"""

from datetime import date
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

OUTPUT = Path(__file__).resolve().parent.parent / "frontend" / "instrucoes.pdf"

ACCENT = (47, 111, 222)
TEXT = (28, 31, 36)
MUTED = (100, 107, 118)
TIP_BG = (255, 246, 214)

# Cada bloco é (tipo, conteúdo):  "p" parágrafo | "ul" lista | "ol" passos | "tip" dica
# **texto** fica em negrito.
SECTIONS = [
    (
        "O que é",
        [
            (
                "p",
                "O Diário de Bordo ouve o seu microfone durante o expediente, transcreve o que "
                "você fala com o horário e ajuda a montar o diário de bordo da semana.",
            ),
        ],
    ),
    (
        "Antes de começar",
        [
            (
                "ul",
                [
                    "Use o **Google Chrome** no computador: o reconhecimento de voz só "
                    "funciona nele.",
                    "Com o servidor rodando, abra **http://localhost:8000**.",
                    "Na primeira vez, o Chrome pede acesso ao microfone: clique em **Permitir**.",
                ],
            ),
        ],
    ),
    (
        "Gravando o seu dia",
        [
            (
                "ol",
                [
                    'Clique em **Iniciar**. O indicador fica **verde** ("Gravando").',
                    "Fale normalmente. O texto aparece em cinza enquanto você fala.",
                    "Depois de alguns segundos de silêncio (padrão: 5), a fala é salva na "
                    "lista com o horário em que você **começou** a falar.",
                    "Almoço ou intervalo? Clique em **Pausar** (amarelo). Na volta, clique em "
                    "**Retomar**: a pausa fica registrada com início e fim.",
                    "No fim do expediente, clique em **Encerrar dia**.",
                ],
            ),
            (
                "tip",
                "Se o reconhecimento cair (internet, silêncio longo), o app religa sozinho. "
                "Se o servidor sair do ar, as falas ficam guardadas no navegador e são "
                "enviadas quando ele voltar.",
            ),
        ],
    ),
    (
        "Cores do indicador",
        [
            (
                "ul",
                [
                    "**Verde:** gravando.",
                    "**Amarelo:** pausado.",
                    "**Vermelho:** parado ou com erro (a mensagem aparece logo abaixo).",
                ],
            ),
        ],
    ),
    (
        'A palavra-chave "Diário"',
        [
            (
                "p",
                'Para registrar o que você está fazendo, comece a frase com **"Diário"**:',
            ),
            (
                "ul",
                [
                    '"Diário, comecei o refinamento do card 1234 com o PO."',
                    '"Diário, reunião de alinhamento com o time de QA."',
                ],
            ),
            (
                "p",
                "A frase vira uma **anotação** (destacada em amarelo na lista) e passa a ser "
                "a sua **atividade atual**. Não dá para falar? Digite no campo de anotação "
                "e clique em **Anotar**.",
            ),
        ],
    ),
    (
        "Atividade atual",
        [
            (
                "ul",
                [
                    "Aparece na caixa amarela, com o horário de início.",
                    "Uma nova anotação substitui a anterior.",
                    "Terminou e ainda não começou outra? Clique em **Finalizar atividade**: "
                    "a caixa deixa de ficar amarela e o horário de fim fica registrado.",
                ],
            ),
        ],
    ),
    (
        "Alerta de inatividade",
        [
            (
                "p",
                "Se você passar **15 minutos** (configurável) gravando sem nenhum registro, o app "
                'pergunta: "Você ainda está em: **sua atividade**?"',
            ),
            (
                "ul",
                [
                    "**Sim:** registra que você continua na mesma atividade.",
                    '**Não:** pede a nova atividade (digite ou fale "Diário, ...").',
                    "Pausado, parado, fora do expediente ou durante um bloco da rotina fixa "
                    "(ex.: daily), o alerta não aparece.",
                    "Clique em **Ativar notificações** para receber o alerta mesmo com o "
                    "Chrome minimizado, com os botões Sim e Não na própria notificação.",
                ],
            ),
            ("tip", "Para mudar o tempo, use INACTIVITY_MINUTES no arquivo .env (1 a 240)."),
        ],
    ),
    (
        "Rotina fixa e expediente",
        [
            (
                "p",
                "Em **Ajustes** (no topo da página) você define o seu expediente e os blocos "
                "que se repetem todo dia útil, como daily e intervalo.",
            ),
            (
                "ul",
                [
                    "Os blocos entram automaticamente na transcrição exportada, marcados "
                    "como [Rotina].",
                    "Durante um bloco, e fora do expediente, o alerta de inatividade fica "
                    "pausado. A página mostra o aviso logo abaixo dos botões.",
                    "Clique em **+ Adicionar bloco**, preencha início, fim e atividade e "
                    "clique em **Salvar**.",
                ],
            ),
        ],
    ),
    (
        "A lista do dia",
        [
            (
                "ul",
                [
                    "Use as setas para ver outros dias e **Hoje** para voltar.",
                    "O botão acima da lista alterna entre **mais recentes** e **mais antigas** "
                    "primeiro.",
                    "Passe o mouse sobre um item para **Editar** ou **Apagar**.",
                ],
            ),
        ],
    ),
    (
        "Exportando a transcrição",
        [
            (
                "ul",
                [
                    "**Dia (.md)**, **Semana (.md)** ou **Semana (.txt)**, no fim da lista.",
                    "O arquivo .md já traz um pedido pronto no topo: cole o arquivo inteiro "
                    "numa conversa com uma IA (como o Claude) para montar o diário em tabela.",
                ],
            ),
        ],
    ),
    (
        "Privacidade",
        [
            (
                "ul",
                [
                    "O reconhecimento de voz do Chrome envia o áudio para servidores do Google.",
                    "A transcrição fica salva só no seu computador (pasta data/).",
                    "Antes de usar no trabalho, confirme se as políticas da empresa permitem.",
                    "Quer salvar só as anotações? Use **SAVE_MODE=notes_only** no arquivo .env.",
                ],
            ),
        ],
    ),
    (
        "Problemas comuns",
        [
            (
                "ul",
                [
                    '**"Servidor fora do ar":** abra o terminal na pasta do projeto e rode o '
                    "servidor (veja o README).",
                    '**"Microfone bloqueado":** clique no cadeado ao lado do endereço e '
                    "permita o microfone.",
                    "**Falas picadas ou juntas demais:** ajuste **PHRASE_GAP_SECONDS** no .env.",
                ],
            ),
        ],
    ),
]


class InstructionsPDF(FPDF):
    def header(self) -> None:
        if self.page_no() == 1:
            return  # a primeira página tem a faixa de título
        self.set_font("Helvetica", size=8)
        self.set_text_color(*MUTED)
        self.cell(0, 6, "Diário de Bordo - Instruções de uso", align="R")
        self.ln(10)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", size=8)
        self.set_text_color(*MUTED)
        self.cell(0, 10, f"Página {self.page_no()}/{{nb}}", align="C")

    def title_block(self) -> None:
        self.set_fill_color(*ACCENT)
        self.rect(0, 0, self.w, 44, style="F")
        self.set_text_color(255, 255, 255)
        self.set_xy(self.l_margin, 12)
        self.set_font("Helvetica", "B", 24)
        self._line("Diário de Bordo", 11)
        self.set_font("Helvetica", size=12)
        self._line("Instruções de uso", 7)
        self.set_font("Helvetica", size=9)
        self._line(
            f"Ferramenta desenvolvida por Pablo Mateus de Melo - atualizado em {date.today():%d/%m/%Y}",  # noqa: E501
            6,
        )
        self.set_y(54)

    def _line(self, text: str, height: float) -> None:
        self.cell(0, height, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def section(self, number: int, title: str) -> None:
        self.ln(3)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(*ACCENT)
        self._line(f"{number}. {title}", 8)
        self.set_draw_color(*ACCENT)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

    def paragraph(self, text: str) -> None:
        self._body_font()
        self.multi_cell(0, 5.5, text, markdown=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1.5)

    def items(self, items: list[str], numbered: bool) -> None:
        self._body_font()
        for i, item in enumerate(items, start=1):
            self.set_x(self.l_margin + 3)
            self.cell(6, 5.5, f"{i}." if numbered else "-")
            self.multi_cell(0, 5.5, item, markdown=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.ln(0.8)
        self.ln(1)

    def tip(self, text: str) -> None:
        self._body_font()
        self.set_fill_color(*TIP_BG)
        self.multi_cell(
            0, 5.5, f"**Dica:** {text}", markdown=True, fill=True, padding=3,
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )  # fmt: skip
        self.ln(2)

    def _body_font(self) -> None:
        self.set_font("Helvetica", size=10.5)
        self.set_text_color(*TEXT)


def build() -> Path:
    pdf = InstructionsPDF(format="A4")
    pdf.set_title("Diário de Bordo - Instruções de uso")
    pdf.set_author("Pablo Mateus de Melo")
    pdf.set_margins(18, 15, 18)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.title_block()

    renderers = {
        "p": pdf.paragraph,
        "ul": lambda items: pdf.items(items, numbered=False),
        "ol": lambda items: pdf.items(items, numbered=True),
        "tip": pdf.tip,
    }
    for number, (title, blocks) in enumerate(SECTIONS, start=1):
        pdf.section(number, title)
        for kind, content in blocks:
            renderers[kind](content)

    pdf.output(str(OUTPUT))
    return OUTPUT


if __name__ == "__main__":
    print(f"PDF gerado em {build()}")
