"""OCR por Tesseract, para o perfil leve (xdiag-privacy-VPS).

Chama o binario `tesseract` como subprocesso e le a saida TSV, que traz cada
palavra com a posicao na imagem. As palavras sao agrupadas por linha e cada
linha vira uma (bbox, texto, confianca), o mesmo formato que o resto do
pipeline ja recebe do PaddleOCR. Nada sai da maquina e nada e gravado em
disco: a imagem vai por stdin e o resultado volta por stdout.
"""

from __future__ import annotations

import csv
import io
import os
import shutil
import subprocess
from typing import Any

from PIL import Image

from .config import Settings

# Idioma do Tesseract para o `ocr_lang` do projeto.
_LANG = {"pt": "por", "por": "por", "en": "eng"}
_TIMEOUT_S = 120


def _binary(settings: Settings) -> str:
    cmd = settings.tesseract_cmd or shutil.which("tesseract") or ""
    if not cmd:
        raise RuntimeError(
            "tesseract nao encontrado: instale o Tesseract (com o idioma por) "
            "ou aponte XDIAG_TESSERACT_CMD"
        )
    return cmd


def _env(settings: Settings) -> dict[str, str]:
    env = dict(os.environ)
    if settings.tessdata_dir is not None:
        env["TESSDATA_PREFIX"] = str(settings.tessdata_dir)
    return env


def check_available(settings: Settings) -> None:
    """Falha cedo, com mensagem clara, se o binario ou o idioma faltam."""
    cmd = _binary(settings)
    lang = _LANG.get(settings.ocr_lang, settings.ocr_lang)
    out = subprocess.run(
        [cmd, "--list-langs"],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_S,
        env=_env(settings),
    )
    langs = set(out.stdout.split()) | set(out.stderr.split())
    if lang not in langs:
        raise RuntimeError(
            f"idioma '{lang}' do Tesseract nao instalado "
            "(aponte XDIAG_TESSDATA_DIR para a pasta com o .traineddata)"
        )


def run_lines(
    image: Image.Image, settings: Settings
) -> list[tuple]:
    """Retorna [(quadrilatero, texto, confianca 0..1, palavras)], uma por linha.

    `palavras` e [(inicio, fim, quadrilatero)], em caracteres dentro do texto da linha.
    """
    cmd = _binary(settings)
    lang = _LANG.get(settings.ocr_lang, settings.ocr_lang)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    proc = subprocess.run(
        [cmd, "stdin", "stdout", "-l", lang, "--psm", "4", "-c", "tessedit_create_tsv=1"],
        input=buf.getvalue(),
        capture_output=True,
        timeout=_TIMEOUT_S,
        env=_env(settings),
    )
    if proc.returncode != 0:
        raise RuntimeError(f"tesseract falhou: {proc.stderr.decode('utf-8', 'replace')[:300]}")
    return _tsv_to_lines(proc.stdout.decode("utf-8", "replace"))


def _tsv_to_lines(tsv: str) -> list[tuple]:
    rows = csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE)
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for r in rows:
        if r.get("level") != "5":  # nivel 5 = palavra
            continue
        text = (r.get("text") or "").strip()
        if not text:
            continue
        key = (r["block_num"], r["par_num"], r["line_num"])
        groups.setdefault(key, []).append(
            {
                "t": text,
                "l": float(r["left"]),
                "top": float(r["top"]),
                "w": float(r["width"]),
                "h": float(r["height"]),
                "c": max(float(r["conf"]), 0.0) / 100.0,
            }
        )
    out: list[tuple] = []
    for words in groups.values():
        words.sort(key=lambda w: w["l"])
        x0 = min(w["l"] for w in words)
        y0 = min(w["top"] for w in words)
        x1 = max(w["l"] + w["w"] for w in words)
        y1 = max(w["top"] + w["h"] for w in words)
        bbox = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
        text = " ".join(w["t"] for w in words)
        conf = sum(w["c"] for w in words) / len(words)
        spans = []
        pos = 0
        for w in words:
            n = len(w["t"])
            wb = [
                [w["l"], w["top"]],
                [w["l"] + w["w"], w["top"]],
                [w["l"] + w["w"], w["top"] + w["h"]],
                [w["l"], w["top"] + w["h"]],
            ]
            spans.append((pos, pos + n, wb))
            pos += n + 1  # um espaco entre palavras
        out.append((bbox, text, conf, spans))
    return out
