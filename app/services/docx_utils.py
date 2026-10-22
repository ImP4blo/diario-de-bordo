"""Peças comuns para gerar documentos Word com o mesmo visual.

Usado pela transcrição exportada e pelo diário de bordo final.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from io import BytesIO

from docx import Document
from docx.document import Document as DocumentType
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Length, Pt, RGBColor

HEADER_BG = "2F6FDE"
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
MUTED = RGBColor(0x64, 0x6B, 0x76)


@dataclass
class CellStyle:
    bold: bool = False
    italic: bool = False
    muted: bool = False


def new_document() -> DocumentType:
    """Documento A4 com margens de 2cm e fonte Calibri 10,5."""
    doc = Document()
    for section in doc.sections:
        section.left_margin = section.right_margin = Cm(2)
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)
    return doc


def _shade(cell, hex_color: str) -> None:
    """python-docx não tem atalho para cor de fundo da célula: editamos o XML direto."""
    shading = OxmlElement("w:shd")
    shading.set(qn("w:val"), "clear")
    shading.set(qn("w:fill"), hex_color)
    cell._tc.get_or_add_tcPr().append(shading)


def add_table(
    doc: DocumentType,
    headers: Sequence[str],
    widths: Sequence[Length],
    rows: Iterable[tuple[Sequence[str], CellStyle]],
) -> None:
    """Tabela com cabeçalho azul. Cada linha vem com o estilo do texto dela."""
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    for cell, title in zip(table.rows[0].cells, headers, strict=True):
        _shade(cell, HEADER_BG)
        run = cell.paragraphs[0].add_run(title)
        run.bold = True
        run.font.color.rgb = WHITE

    for values, style in rows:
        for cell, value in zip(table.add_row().cells, values, strict=True):
            run = cell.paragraphs[0].add_run(value)
            run.bold = style.bold
            run.italic = style.italic
            if style.muted:
                run.font.color.rgb = MUTED

    # No Word, a largura precisa ser definida célula por célula
    for row in table.rows:
        for cell, width in zip(row.cells, widths, strict=True):
            cell.width = width


def to_bytes(doc: DocumentType) -> bytes:
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
