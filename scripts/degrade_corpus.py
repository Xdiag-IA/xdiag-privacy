"""Gera versoes degradadas do corpus, para medir o recall em foto de celular.

O corpus de `tests/corpus/` e imagem limpa e sintetica. Documento que chega por
WhatsApp vem torto, escuro, comprimido e as vezes pequeno. Este script copia o
corpus aplicando degradacoes deterministicas (semente fixa) e ajusta o gabarito:

- rotacao: as caixas do gabarito sao giradas junto, e cada uma vira o menor
  retangulo que contem os quatro cantos girados (o que torna a medida um pouco
  mais dura, nunca mais branda);
- reducao de resolucao: o avaliador ja usa a escala largura_da_imagem /
  largura_do_gabarito, entao o gabarito nao muda.

Perfis (cumulativos dentro de cada um):
  whatsapp  reduz para 900 px de largura, JPEG qualidade 45
  sombra    escurece, sombra em degrade, ruido, JPEG 60
  inclinado gira 3 graus, desfoque leve, JPEG 60
  pior      gira -4 graus, desfoque, sombra, ruido, 60% da resolucao, JPEG 35

PDF e ignorado (a degradacao aqui e de foto).

Uso:
    python scripts/degrade_corpus.py --out ../xdiag-privacy-degradado
    python scripts/evaluate.py --level full --corpus ../xdiag-privacy-degradado/pior
"""

from __future__ import annotations

import argparse
import io
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]


def rotate(img: Image.Image, deg: float) -> tuple[Image.Image, tuple[float, ...]]:
    """Gira `deg` graus (sentido horario na tela), mesmo tamanho, fundo branco.

    Devolve a imagem e o centro, para transformar as caixas do gabarito.
    """
    th = math.radians(deg)
    c, s = math.cos(th), math.sin(th)
    w, h = img.size
    cx, cy = w / 2, h / 2
    # transform() recebe o mapa INVERSO (saida -> entrada).
    coeffs = (c, s, cx - cx * c - cy * s, -s, c, cy + cx * s - cy * c)
    out = img.transform(img.size, Image.AFFINE, coeffs, Image.BICUBIC, fillcolor=(255, 255, 255))
    return out, (cx, cy)


def rotate_box(box: list[float], deg: float, cx: float, cy: float) -> list[float]:
    th = math.radians(deg)
    c, s = math.cos(th), math.sin(th)
    x0, y0, x1, y1 = box
    xs, ys = [], []
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        dx, dy = x - cx, y - cy
        xs.append(cx + dx * c - dy * s)
        ys.append(cy + dx * s + dy * c)
    return [min(xs), min(ys), max(xs), max(ys)]


def shade(img: Image.Image, strength: float, rng: np.random.Generator) -> Image.Image:
    """Escurece e aplica uma sombra em degrade da esquerda para a direita."""
    a = np.asarray(img).astype(np.float32)
    h, w = a.shape[:2]
    ramp = np.linspace(1.0 - strength, 1.0, w, dtype=np.float32)[None, :, None]
    a = a * ramp * (1.0 - strength / 3)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def noise(img: Image.Image, sigma: float, rng: np.random.Generator) -> Image.Image:
    a = np.asarray(img).astype(np.float32)
    a = a + rng.normal(0, sigma, a.shape).astype(np.float32)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def jpeg(img: Image.Image, quality: int) -> Image.Image:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def apply(profile: str, img: Image.Image, rng: np.random.Generator):
    """Devolve (imagem, angulo, centro, qualidade_jpeg)."""
    angle, center = 0.0, (img.width / 2, img.height / 2)
    if profile == "whatsapp":
        h = round(img.height * 900 / img.width)
        img = img.resize((900, h), Image.LANCZOS)
        return img, angle, center, 45
    if profile == "sombra":
        img = shade(img, 0.45, rng)
        img = noise(img, 10, rng)
        return img, angle, center, 60
    if profile == "inclinado":
        img, center = rotate(img, 3.0)
        img = img.filter(ImageFilter.GaussianBlur(0.8))
        return img, 3.0, center, 60
    if profile == "pior":
        img, center = rotate(img, -4.0)
        img = img.filter(ImageFilter.GaussianBlur(1.2))
        img = shade(img, 0.35, rng)
        img = noise(img, 12, rng)
        h = round(img.height * 0.6)
        img = img.resize((round(img.width * 0.6), h), Image.LANCZOS)
        return img, -4.0, center, 35
    raise SystemExit(f"perfil desconhecido: {profile}")


PROFILES = ["whatsapp", "sombra", "inclinado", "pior"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", type=Path, default=ROOT / "tests" / "corpus")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--profiles", nargs="*", default=PROFILES)
    args = ap.parse_args()

    for profile in args.profiles:
        dest = args.out / profile
        dest.mkdir(parents=True, exist_ok=True)
        n = 0
        for jf in sorted(args.corpus.glob("*.json")):
            raw = json.loads(jf.read_text(encoding="utf-8"))
            if raw.get("schema_version") != 1 or "pages" in raw:
                continue  # multipagina/PDF fica de fora
            src = args.corpus / raw["image"]
            if src.suffix.lower() == ".pdf":
                continue
            rng = np.random.default_rng(sum(map(ord, raw["doc_id"])))
            img = Image.open(src).convert("RGB")
            out, angle, (cx, cy), q = apply(profile, img, rng)
            # Gabarito: a rotacao foi feita na imagem ORIGINAL (antes da reducao),
            # com o centro dela; a reducao e tratada pela escala do avaliador.
            if angle:
                page = raw["page"]
                for key in ("spans", "optional_spans", "regions"):
                    for item in page.get(key, []):
                        item["bbox_px"] = rotate_box(item["bbox_px"], angle, cx, cy)
            name = Path(raw["image"]).with_suffix(".jpg").name
            jpeg(out, q).save(dest / name, format="JPEG", quality=q)
            raw["image"] = name
            (dest / jf.name).write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
            n += 1
        print(f"{profile}: {n} documentos em {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
