"""Anonimiza UM documento pela linha de comando, sem interface (modo headless).

Le uma imagem (PNG, JPG, WEBP) ou um PDF de ate 10 paginas, acha os dados
pessoais, apaga o pixel de cada um (preto puro, nao uma camada por cima) e grava
um arquivo novo, sem EXIF e com nome novo: PNG para imagem, PDF (so imagem, sem
camada de texto) para PDF. Escreve na saida padrao UM objeto JSON com o resumo,
SEM os valores encontrados.

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
  4  formato nao suportado (tipo desconhecido, PDF acima do limite de paginas)
  5  erro (OCR, camada LLM, arquivo ilegivel)

Uso:
    python scripts/anonimizar.py FOTO.jpg --saida ./saida --perfil vps
    python scripts/anonimizar.py LAUDO.pdf --saida ./saida --perfil vps --apagar-entrada
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import secrets
import sys
from concurrent.futures import ThreadPoolExecutor
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

# Limite de paginas de um PDF. Acima disso o comando recusa (codigo 4), em vez
# de processar so uma parte em silencio.
MAX_PAGINAS = 10
# Quantas paginas detectam ao mesmo tempo (cada uma e uma chamada a camada LLM).
PARALELO = 4
# Resolucao das paginas de PDF renderizadas pelo backend (escala 2 de 72 dpi).
DPI_PDF = 144.0

# Portao de qualidade. Calibrado no corpus limpo e nos corpora degradados
# (scripts/degrade_corpus.py): pega o pior caso, nao todos. Nenhum indicador
# sem gabarito separou com seguranca "leu bem" de "leu mal": a conferencia da
# pessoa na imagem devolvida continua obrigatoria. Em PDF, vale para o
# documento inteiro (uma pagina em branco ou so de imagem nao o barra).
GATE_CONF_MIN = 0.65  # confianca media do OCR, ponderada pelo tamanho da linha
GATE_CHARS_MIN = 20  # texto lido, sem espacos
GATE_SIDE_MIN = 800  # menor lado da imagem, em pixels
PAGINA_POUCO_TEXTO = 20  # abaixo disso, a pagina entra nos avisos


def emit(obj: dict, code: int) -> int:
    print(json.dumps(obj, ensure_ascii=False))
    return code


def quality(page_results, sides) -> dict:
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
    return {"caracteres": chars, "confianca": round(conf, 2), "menor_lado_px": min(sides)}


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
    ap.add_argument("--max-paginas", type=int, default=MAX_PAGINAS, help="limite de paginas de um PDF (padrao %d)" % MAX_PAGINAS)
    args = ap.parse_args()

    if args.perfil == "vps":
        os.environ.setdefault("XDIAG_OCR_ENGINE", "tesseract")
        os.environ.setdefault("XDIAG_PII_ENGINE", "rules")
        os.environ.setdefault("XDIAG_PII_LLM", "claude")
    # O backend recusa PDF acima deste limite (PageLimitExceeded).
    os.environ["XDIAG_MAX_PDF_PAGES"] = str(max(args.max_paginas, 1))

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
        return emit({"ok": False, "motivo": "formato_nao_suportado", "detalhe": "use PNG, JPG, WEBP ou PDF"}, 4)
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

        try:
            pages = ocr_mod.get_engine().run(data, mime)
        except ocr_mod.PageLimitExceeded as exc:
            return emit(
                {"ok": False, "motivo": "limite_de_paginas", "paginas": exc.pages, "limite": exc.limit,
                 "detalhe": "o PDF tem %d paginas e o limite e %d: mande em partes" % (exc.pages, exc.limit)},
                4,
            )

        q = quality(pages, [min(p.width, p.height) for p in pages])
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

        def detect(res):
            return pii.detect(res.text, threshold=args.limite)

        # Cada pagina e uma chamada independente a camada LLM: em paralelo.
        if len(pages) > 1:
            with ThreadPoolExecutor(max_workers=min(PARALELO, len(pages))) as ex:
                detected = list(ex.map(detect, pages))
        else:
            detected = [detect(pages[0])]
        per_page = [build_entities(d, res.lines) for d, res in zip(detected, pages)]
    except Exception as exc:  # noqa: BLE001
        # Sem o texto da excecao: pode carregar trecho do documento.
        detail = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        return emit({"ok": False, "motivo": "erro", "detalhe": detail}, 5)

    sem_posicao = [(i + 1, sum(1 for e in ents if e.unmapped)) for i, ents in enumerate(per_page)]
    sem_posicao = [(p, n) for p, n in sem_posicao if n]
    if sem_posicao:
        return emit(
            {"ok": False, "motivo": "entidade_sem_posicao", "quantidade": sum(n for _, n in sem_posicao),
             "paginas": [p for p, _ in sem_posicao],
             "detalhe": "achei dado pessoal no texto que nao consegui localizar na imagem; nao entrego"},
            3,
        )

    images = [burn(res.image_png, [bb for e in ents for bb in e.bboxes]) for res, ents in zip(pages, per_page)]

    args.saida.mkdir(parents=True, exist_ok=True)
    stem = f"anonimizado_{dt.date.today().isoformat()}_{secrets.token_hex(3)}"
    if mime == "application/pdf":
        dest = args.saida / (stem + ".pdf")
        # PDF so de imagem: sem camada de texto e sem metadado do original.
        images[0].save(dest, format="PDF", save_all=True, append_images=images[1:], resolution=DPI_PDF)
    else:
        dest = args.saida / (stem + ".png")
        images[0].save(dest, format="PNG")  # so IHDR, IDAT e IEND; sem EXIF nem nome original

    por_tipo: dict[str, int] = {}
    for ents in per_page:
        for e in ents:
            por_tipo[e.redacted] = por_tipo.get(e.redacted, 0) + 1
    total = sum(len(ents) for ents in per_page)

    if len(pages) > 1:
        for i, res in enumerate(pages):
            n = sum(len(ln.text.replace(" ", "")) for ln in res.lines)
            if n < PAGINA_POUCO_TEXTO:
                avisos.append(f"pagina {i + 1}: pouco texto lido (em branco, so imagem ou ilegivel?): confira")
    if not total:
        avisos.append("nenhum dado pessoal encontrado: confira a imagem, pode ser leitura falha")
    avisos.append("a ferramenta auxilia e nao garante: confira o arquivo antes de compartilhar")

    out = {"ok": True, "arquivo": str(dest.resolve()), "paginas": len(pages), "cobertos": total,
           "por_tipo": por_tipo, "qualidade": q, "avisos": avisos}
    if len(pages) > 1:
        out["por_pagina"] = [{"pagina": i + 1, "cobertos": len(ents)} for i, ents in enumerate(per_page)]
    return emit(out, 0)


if __name__ == "__main__":
    raise SystemExit(main())
