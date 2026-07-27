"""Gera o icone do aplicativo a partir da marca do Xdiag Privacy.

Desenha a mesma geometria de frontend/src/components/BrandMark.tsx (variante
x-bar): o X da familia Xdiag com uma tarja cobrindo o cruzamento.

Roda com o Python do runtime empacotado, que ja tem Pillow e numpy:

    desktop\\build\\runtime\\python\\python.exe desktop\\scripts\\make_icon.py

Sai em desktop/build-assets/icon.png, que o electron-builder converte para
.ico sozinho.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

# Tudo e desenhado num canvas grande e reduzido no fim: e o antialiasing do
# pobre, e suficiente para arte simples como esta.
SUPER = 4
SIZE = 512
S = SIZE * SUPER

# Escala do sistema de coordenadas da marca (viewBox 0 0 64 64) para pixels.
K = S / 64.0


def u(v: float) -> float:
    """Converte unidade da marca em pixel do canvas ampliado."""
    return v * K


def linear_gradient(size: int, c0: tuple[int, int, int], c1: tuple[int, int, int]) -> Image.Image:
    """Gradiente diagonal, do canto superior esquerdo ao inferior direito."""
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    t = ((x + y) / (2.0 * (size - 1)))[..., None]
    a = np.array(c0, dtype=np.float32)
    b = np.array(c1, dtype=np.float32)
    arr = (a + (b - a) * t).astype(np.uint8)
    return Image.fromarray(arr, mode="RGB")


def stroke_gradient(size: int) -> Image.Image:
    """Gradiente do traco do X: claro em cima, ciano no meio, escuro embaixo."""
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    t = np.clip((x * 0.15 + y * 0.85) / (size - 1), 0.0, 1.0)
    stops = [(0.00, (125, 237, 251)), (0.52, (34, 211, 238)), (1.00, (8, 145, 178))]
    arr = np.zeros((size, size, 3), dtype=np.float32)
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        m = (t >= t0) & (t <= t1)
        local = np.where(m, (t - t0) / max(t1 - t0, 1e-6), 0.0)[..., None]
        arr += m[..., None] * (np.array(c0, np.float32) + (np.array(c1, np.float32) - np.array(c0, np.float32)) * local)
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), mode="RGB")


def radial_glow(size: int) -> Image.Image:
    """Halo ciano suave, centrado um pouco acima do meio."""
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    cx, cy, r = size * 0.5, size * 0.38, size * 0.62
    d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / r
    alpha = (np.clip(1.0 - d, 0.0, 1.0) * 0.26 * 255).astype(np.uint8)
    glow = Image.new("RGB", (size, size), (34, 211, 238))
    glow.putalpha(Image.fromarray(alpha, mode="L"))
    return glow


def round_cap_line(draw: ImageDraw.ImageDraw, p0, p1, width: float, fill=255) -> None:
    """Linha com ponta arredondada. O ImageDraw nao tem cap redondo nativo,
    entao a ponta e um circulo desenhado por cima."""
    draw.line([p0, p1], fill=fill, width=int(round(width)))
    r = width / 2.0
    for (px, py) in (p0, p1):
        draw.ellipse([px - r, py - r, px + r, py + r], fill=fill)


def build() -> Image.Image:
    radius = u(15)

    # 1. Base com gradiente, recortada no formato de quadrado arredondado.
    base = linear_gradient(S, (13, 28, 48), (3, 10, 22)).convert("RGBA")
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=radius, fill=255)

    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    canvas.paste(base, (0, 0), mask)

    # 2. Halo ciano.
    glow = radial_glow(S)
    glow.putalpha(Image.fromarray(
        (np.array(glow.getchannel("A"), dtype=np.float32) * (np.array(mask, dtype=np.float32) / 255.0)).astype(np.uint8),
        mode="L",
    ))
    canvas = Image.alpha_composite(canvas, glow)

    # 3. Fio ciano na borda.
    borda = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(borda).rounded_rectangle(
        [u(0.75), u(0.75), S - 1 - u(0.75), S - 1 - u(0.75)],
        radius=radius - u(0.75),
        outline=(34, 211, 238, 56),
        width=int(round(u(1.5))),
    )
    canvas = Image.alpha_composite(canvas, borda)

    # 4. O X, com gradiente aplicado via mascara.
    xmask = Image.new("L", (S, S), 0)
    dx = ImageDraw.Draw(xmask)
    w = u(8.4)
    round_cap_line(dx, (u(15.5), u(14.5)), (u(48.5), u(49.5)), w)
    round_cap_line(dx, (u(48.5), u(14.5)), (u(15.5), u(49.5)), w)
    xlayer = stroke_gradient(S).convert("RGBA")
    xlayer.putalpha(xmask)
    canvas = Image.alpha_composite(canvas, xlayer)

    # 5. A tarja por cima do cruzamento, que e o gesto que define o produto.
    tarja = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    dt = ImageDraw.Draw(tarja)
    box = [u(9), u(26.6), u(9) + u(46), u(26.6) + u(10.8)]
    dt.rounded_rectangle(box, radius=u(5.4), fill=(9, 23, 40, 255),
                         outline=(34, 211, 238, 230), width=int(round(u(1.7))))
    canvas = Image.alpha_composite(canvas, tarja)

    return canvas.resize((SIZE, SIZE), Image.LANCZOS)


def main() -> None:
    out_dir = Path(__file__).resolve().parent.parent / "build-assets"
    out_dir.mkdir(parents=True, exist_ok=True)
    icon = build()
    png = out_dir / "icon.png"
    icon.save(png)
    # .ico multi resolucao para o Windows nao reamostrar sozinho nos tamanhos
    # pequenos, onde a tarja e o que precisa continuar legivel.
    icon.save(out_dir / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"icone gerado: {png} ({png.stat().st_size // 1024} KB)")
    print(f"icone gerado: {out_dir / 'icon.ico'}")


if __name__ == "__main__":
    main()
