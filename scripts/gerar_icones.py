"""Gera os ícones PNG do app (PWA e favicon) em frontend/icons/.

    python -m uv run python scripts/gerar_icones.py

Desenha o mesmo símbolo de frontend/icons/logo-mark.svg (folha com onda sonora e o
ponto verde de "gravando"), usando as mesmas coordenadas: o SVG tem 64x64 unidades
e aqui cada unidade vira 16 pixels de uma imagem 1024x1024.
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "frontend" / "icons"

BG_TOP = (59, 123, 240)  # #3b7bf0
BG_BOTTOM = (28, 70, 163)  # #1c46a3
WHITE = (255, 255, 255)
WAVE = (47, 111, 222)  # #2f6fde
LINE = (200, 212, 235)  # #c8d4eb
GREEN = (31, 157, 85)  # #1f9d55

BASE = 1024  # desenhamos grande e reduzimos: bordas suaves (antialiasing)
UNIT = BASE / 64

# Elementos do símbolo, nas coordenadas do SVG (x, y, largura, altura, raio)
PAGE = (15, 11, 34, 43, 6)
WAVE_BARS = [(21.3, 29, 3.4, 8), (27.3, 23, 3.4, 20), (33.3, 19, 3.4, 28), (39.3, 26, 3.4, 14)]
TEXT_LINE = (21.3, 48, 16, 2.6)
DOT = (47, 13, 7, 2.5)  # centro x, centro y, raio, borda branca


def draw_icon(maskable: bool) -> Image.Image:
    image = Image.new("RGB", (BASE, BASE), BG_TOP)
    draw = ImageDraw.Draw(image)

    # Degradê na diagonal (de cima à esquerda para baixo à direita), como no SVG
    for i in range(2 * BASE):
        t = i / (2 * BASE)
        color = tuple(round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM, strict=True))
        draw.line([(i, 0), (0, i)], fill=color, width=2)

    # Ícones "maskable" podem ser recortados em círculo pelo Android: o desenho
    # encolhe para caber na "zona segura" (os 80% centrais)
    scale = 0.8 if maskable else 1.0
    offset = BASE * (1 - scale) / 2

    def box(x, y, w, h):
        k = UNIT * scale
        return [offset + x * k, offset + y * k, offset + (x + w) * k, offset + (y + h) * k]

    def radius(r):
        return r * UNIT * scale

    x, y, w, h, r = PAGE
    draw.rounded_rectangle(box(x, y, w, h), radius=radius(r), fill=WHITE)
    for x, y, w, h in WAVE_BARS:
        draw.rounded_rectangle(box(x, y, w, h), radius=radius(w / 2), fill=WAVE)
    x, y, w, h = TEXT_LINE
    draw.rounded_rectangle(box(x, y, w, h), radius=radius(h / 2), fill=LINE)

    cx, cy, r, border = DOT
    draw.ellipse(
        box(cx - r - border, cy - r - border, 2 * (r + border), 2 * (r + border)), fill=WHITE
    )
    draw.ellipse(box(cx - r, cy - r, 2 * r, 2 * r), fill=GREEN)
    return image


def rounded(image: Image.Image) -> Image.Image:
    """Cantos arredondados (raio 15 de 64, como no SVG) com fundo transparente."""
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, *image.size], radius=15 * UNIT, fill=255)
    result = image.convert("RGBA")
    result.putalpha(mask)
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    regular, maskable = draw_icon(maskable=False), draw_icon(maskable=True)
    # Ícones normais com cantos arredondados; o "maskable" é quadrado (o sistema recorta)
    for size in (192, 512):
        rounded(regular).resize((size, size), Image.LANCZOS).save(OUT / f"icon-{size}.png")
        maskable.resize((size, size), Image.LANCZOS).save(OUT / f"icon-maskable-{size}.png")
    # O iPhone arredonda sozinho e não aceita transparência: quadrado mesmo
    regular.resize((180, 180), Image.LANCZOS).save(OUT / "apple-touch-icon.png")
    rounded(regular).resize((48, 48), Image.LANCZOS).save(OUT / "favicon.png")
    # Logo da tela de consentimento do Google (OAuth > Branding): 120x120, quadrado
    regular.resize((120, 120), Image.LANCZOS).save(OUT / "logo-120.png")
    print(f"Ícones gerados em {OUT}")


if __name__ == "__main__":
    main()
