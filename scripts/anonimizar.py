"""Anonimiza UM documento pela linha de comando, sem interface (modo headless).

Le uma imagem (PNG, JPG, WEBP) ou um PDF de uma pagina, acha os dados pessoais,
apaga o pixel de cada um (preto puro, nao uma camada por cima) e grava uma
imagem nova, sem EXIF e com nome novo. Escreve na saida padrao UM objeto JSON
com o resumo, SEM os valores encontrados.

Feito para rodar fora do computador do usuario (por exemplo numa VPS, chamado
por um agente no WhatsApp), onde a interface web nao serve.

PRIVACIDADE. No perfil leve com a camada LLM (`--perfil vps`), o TEXTO lido do
documento e enviado a um servico externo (Anthropic). O sigilo absoluto da
anonimizacao 100% local, que e a promessa do aplicativo desktop, NAO se aplica.
Quem envia decide se esse caminho serve para o documento.

Codigos de saida:
  0  ok, arquivo gravado
  2  qualidade ruim: nao entrega (use --forcar para ignorar)
  3  entidade achada no texto mas sem posicao na imagem: nao entrega
  4  formato nao suportado (PDF com mais de uma pagina, tipo desconhecido)
  5  erro (OCR, camada LLM, arquivo ilegivel)

Uso:
    python scripts/anonimizar.py FOTO.jpg --saida ./saida --perfil vps
    python scripts/anonimizar.py FOTO.jpg --saida ./saida --apagar-entrada
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}

# Portao de qualidade. Calibrado no corpus limpo e nos corpora degradados
# (scripts/degrade_corpus.py): pega o pior caso, nao todos. Nenhum indicador
# sem gabarito separou com seguranca "leu bem" de "leu mal": a conferencia da
# pessoa na imagem devolvida continua obrigatoria.
GATE_CONF_MIN = 0.65  # confianca media do OCR, ponderada pelo tamanho da linha
GATE_CHARS_MIN = 20  # texto lido, sem espacos
GATE_SIDE_MIN = 800  # menor lado da imagem, em pixels


def emit(obj: dict, code: int) -> int:
    print(json.dumps(obj, ensure_ascii=False))
    return code


def quality(page_results, widths) -> dict:
    chars = 0
    weighted = 0.0
    total_len = 0
    for res in page_results:
        for ln in res.lines:
            n = len(ln.text)
            total_len += n
            weighted += ln.confidence * n
            chars += len(ln.text.replace(" ", ""))
    conf = weighted / total_len if total_len else 0.0
    return {"caracteres": chars, "confianca": round(conf, 2), "menor_lado_px": min(widths)}


def gate_reasons(q: dict) -> list[str]:
    out = []
    if q["menor_lado_px"] < GATE_SIDE_MIN:
        out.append("foto pequena demais (menos de %d px no menor lado)" % GATE_SIDE_MIN)
    if q["caracteres"] < GATE_CHARS_MIN:
        out.append("quase nenhum texto foi lido")
    elif q["confianca"] < GATE_CONF_MIN:
        out.append("o texto saiu com baixa confianca (foto escura, tremida ou torta)")
    return out


def burn(png_bytes: bytes, boxes: list) -> "object":
    """Pinta de preto puro cada caixa e devolve uma imagem NOVA, so de pixels.

    Reconstruir a partir do array descarta EXIF e qualquer metadado. As
    coordenadas arredondam PARA FORA, para que todo pixel tocado pela deteccao
    seja apagado.
    """
    import io
    import math

    import numpy as np
    from PIL import Image

    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    a = np.array(img)
    h, w = a.shape[:2]
    for quad in boxes:
        xs = [p[0] for p in quad]
        ys = [p[1] for p in quad]
        x0 = max(int(math.floor(min(xs))), 0)
        y0 = max(int(math.floor(min(ys))), 0)
        x1 = min(int(math.ceil(max(xs))), w)
        y1 = min(int(math.ceil(max(ys))), h)
        if x1 > x0 and y1 > y0:
            a[y0:y1, x0:x1] = 0
    return Image.fromarray(a)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entrada", type=Path)
    ap.add_argument("--saida", type=Path, default=Path("saida"), help="pasta do arquivo anonimizado")
    ap.add_argument("--perfil", choices=["vps"], help="vps: Tesseract + regras + camada LLM (claude -p)")
    ap.add_argument("--apagar-entrada", action="store_true", help="apaga o arquivo de entrada ao terminar, em qualquer resultado")
    ap.add_argument("--forcar", action="store_true", help="entrega mesmo com o portao de qualidade barrando")
    ap.add_argument("--limite", type=float, default=0.5, help="confianca minima da deteccao")
    args = ap.parse_args()

    if args.perfil == "vps":
        os.environ.setdefault("XDIAG_OCR_ENGINE", "tesseract")
        os.environ.setdefault("XDIAG_PII_ENGINE", "rules")
        os.environ.setdefault("XDIAG_PII_LLM", "claude")

    src: Path = args.entrada
    try:
        return run(args, src)
    finally:
        if args.apagar_entrada:
            try:
                src.unlink()
            except OSError:
                pass


def run(args, src: Path) -> int:
    mime = MIME.get(src.suffix.lower())
    if mime is None:
        return emit({"ok": False, "motivo": "formato_nao_suportado", "detalhe": "use PNG, JPG, WEBP ou PDF de uma pagina"}, 4)
    try:
        data = src.read_bytes()
    except OSError:
        return emit({"ok": False, "motivo": "erro", "detalhe": "arquivo de entrada ilegivel"}, 5)

    from app.config import get_settings

    s = get_settings()
    if len(data) == 0 or len(data) > s.max_upload_bytes:
        return emit({"ok": False, "motivo": "erro", "detalhe": "arquivo vazio ou acima do limite de tamanho"}, 5)

    try:
        from app import ocr as ocr_mod
        from app import pii as pii_mod
        from app.mapper import build_entities

        ocr_results = ocr_mod.get_engine().run(data, mime)
        if len(ocr_results) != 1:
            return emit(
                {"ok": False, "motivo": "formato_nao_suportado", "detalhe": "so documento de uma pagina; o export multipagina esta bloqueado de proposito"},
                4,
            )
        res = ocr_results[0]
        q = quality(ocr_results, [min(res.width, res.height)])
        reasons = gate_reasons(q)
        avisos: list[str] = []
        if reasons and not args.forcar:
            return emit(
                {"ok": False, "motivo": "qualidade_baixa", "detalhe": reasons, "qualidade": q,
                 "orientacao": "mande outra foto: reta, de perto, com boa luz, sem sombra e sem tremer"},
                2,
            )
        if reasons:
            avisos.append("entregue com --forcar apesar de: " + "; ".join(reasons))

        pii = pii_mod.get_engine()
        detected = pii.detect(res.text, threshold=args.limite)
        entities = build_entities(detected, res.lines)
    except Exception as exc:  # noqa: BLE001
        # Sem o texto da excecao: pode carregar trecho do documento.
        detail = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        return emit({"ok": False, "motivo": "erro", "detalhe": detail}, 5)

    unmapped = [e for e in entities if e.unmapped]
    if unmapped:
        return emit(
            {"ok": False, "motivo": "entidade_sem_posicao", "quantidade": len(unmapped),
             "detalhe": "achei dado pessoal no texto que nao consegui localizar na imagem; nao entrego"},
            3,
        )

    boxes = [bb for e in entities for bb in e.bboxes]
    out_img = burn(res.image_png, boxes)

    args.saida.mkdir(parents=True, exist_ok=True)
    name = f"anonimizado_{dt.date.today().isoformat()}_{secrets.token_hex(3)}.png"
    dest = args.saida / name
    out_img.save(dest, format="PNG")  # so IHDR, IDAT e IEND; sem EXIF nem nome original

    por_tipo: dict[str, int] = {}
    for e in entities:
        por_tipo[e.redacted] = por_tipo.get(e.redacted, 0) + 1
    if not entities:
        avisos.append("nenhum dado pessoal encontrado: confira a imagem, pode ser leitura falha")
    avisos.append("a ferramenta auxilia e nao garante: confira a imagem antes de compartilhar")

    return emit(
        {"ok": True, "arquivo": str(dest.resolve()), "cobertos": len(entities), "por_tipo": por_tipo,
         "qualidade": q, "avisos": avisos},
        0,
    )


if __name__ == "__main__":
    raise SystemExit(main())
