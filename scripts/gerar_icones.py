"""Gera os ícones do app (PWA) em frontend/icons/.

    python -m uv run python scripts/gerar_icones.py

Desenho: uma folha de caderno branca sobre fundo azul, com linhas de texto e um
ponto verde de "gravando". Feito em código (Pillow) para ninguém precisar de
programa de design para ajustar.
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "frontend" / "icons"
BLUE = (47, 111, 222)
BLUE_DARK = (31, 78, 170)
WHITE = (255, 255, 255)
LINE = (200, 212, 235)
GREEN = (31, 157, 85)

# Desenhamos grande e reduzimos: as bordas ficam suaves (antialiasing)
BASE = 1024


def draw_icon(maskable: bool) -> Image.Image:
    image = Image.new("RGB", (BASE, BASE), BLUE)
    draw = ImageDraw.Draw(image)

    # Degradê simples de cima (azul) para baixo (azul escuro)
    for y in range(BASE):
        t = y / BASE
        color = tuple(round(a + (b - a) * t) for a, b in zip(BLUE, BLUE_DARK, strict=True))
        draw.line([(0, y), (BASE, y)], fill=color)

    # Ícones "maskable" podem ser recortados em círculo pelo Android: mantemos
    # o desenho dentro da "zona segura" (80% centrais)
    scale = 0.62 if maskable else 0.74
    w, h = BASE * scale * 0.78, BASE * scale
    x0, y0 = (BASE - w) / 2, (BASE - h) / 2
    draw.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=BASE * 0.05, fill=WHITE)

    # Linhas de texto da folha
    margin = w * 0.16
    for i, length in enumerate((0.95, 0.8, 0.9, 0.6)):
        y = y0 + h * (0.3 + i * 0.15)
        draw.rounded_rectangle(
            [x0 + margin, y, x0 + margin + (w - 2 * margin) * length, y + h * 0.05],
            radius=h * 0.025,
            fill=LINE,
        )

    # Ponto verde de "gravando", no canto da folha
    r = w * 0.13
    cx, cy = x0 + w - margin * 0.9, y0 + margin * 0.9
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GREEN, outline=WHITE, width=round(r * 0.3))
    return image


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    regular, maskable = draw_icon(maskable=False), draw_icon(maskable=True)
    for size in (192, 512):
        regular.resize((size, size), Image.LANCZOS).save(OUT / f"icon-{size}.png")
        maskable.resize((size, size), Image.LANCZOS).save(OUT / f"icon-maskable-{size}.png")
    regular.resize((180, 180), Image.LANCZOS).save(OUT / "apple-touch-icon.png")  # iPhone
    regular.resize((48, 48), Image.LANCZOS).save(OUT / "favicon.png")
    print(f"Ícones gerados em {OUT}")


if __name__ == "__main__":
    main()
