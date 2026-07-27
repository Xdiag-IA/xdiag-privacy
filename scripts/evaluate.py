"""Avaliador de recall/precisao do pipeline sobre o corpus de gabaritos.

Niveis:
  --level text   injeta o texto canonico do gabarito direto no PIIEngine
                 (isola pii.py; rapido; nao usa OCR)
  --level full   PNG/PDF -> OCR -> PII -> mapper; matching em pixel space,
                 imune a variacao de quebra de linha e erro de caractere
  --level both   (default) roda os dois

Politica: falso negativo e falha critica e vem PRIMEIRO no relatorio,
listado um a um; falso positivo e ruido aceitavel, reportado ao final.

Baseline: --save-baseline grava tests/baselines/baseline-<level>.json
(versionado). Execucoes seguintes comparam e imprimem REGRESSOES e
CORRIGIDOS. Exit code 1 quando ha regressao versus o baseline.

Execucao recomendada (modelo real ja cacheado no volume Docker):
    docker compose run --rm eval --level text
    docker compose run --rm eval --level full --save-baseline
No host, funciona em mock: XDIAG_MOCK=1 python scripts/evaluate.py --level text
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Import do backend nos dois mundos (container /app ou repo no host).
if Path("/app/app").exists():
    sys.path.insert(0, "/app")
    DEFAULT_CORPUS = Path("/app/tests/corpus")
    DEFAULT_BASELINES = Path("/app/tests/baselines")
else:
    ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(ROOT / "backend"))
    DEFAULT_CORPUS = ROOT / "tests" / "corpus"
    DEFAULT_BASELINES = ROOT / "tests" / "baselines"

os.environ.setdefault("XDIAG_EAGER_LOAD", "0")

from PIL import Image, ImageDraw, ImageStat  # noqa: E402


# --- Equivalencia de labels --------------------------------------------------

# Grupos que cada label PREDITO pelo pipeline pode satisfazer.
PRED_LABEL_GROUPS: dict[str, set[str]] = {
    "PERSON": {"NAME"},
    "PATIENT": {"NAME"},
    "PATIENT_NAME": {"NAME"},
    "DOCTOR": {"NAME"},
    "DOCTOR_NAME": {"NAME"},
    "PROFESSIONAL": {"NAME"},
    "BR_CPF": {"DOC_NUM"},
    "CPF": {"DOC_NUM"},
    "BR_RG": {"DOC_NUM"},
    "RG": {"DOC_NUM"},
    "BR_DOC": {"DOC_NUM", "ORG"},
    "ID": {"DOC_NUM"},
    "MEDICAL_RECORD": {"DOC_NUM"},
    "MEDICAL_RECORD_NUMBER": {"DOC_NUM"},
    "MRN": {"DOC_NUM"},
    "CRM": {"DOC_NUM"},
    "COREN": {"DOC_NUM"},
    "RQE": {"DOC_NUM"},
    "CNS": {"DOC_NUM"},
    "CNES": {"DOC_NUM"},
    "TISS_GUIDE": {"DOC_NUM"},
    "TISS_AUTH": {"DOC_NUM"},
    "INSURANCE_ID": {"DOC_NUM"},
    "NUMERO": {"DOC_NUM"},
    "BR_CNPJ": {"ORG", "DOC_NUM"},
    "CNPJ": {"ORG", "DOC_NUM"},
    "INSTITUTION": {"ORG"},
    "HOSPITAL": {"ORG"},
    "ORGANIZATION": {"ORG"},
    "PHONE": {"CONTACT"},
    "PHONE_NUMBER": {"CONTACT"},
    "EMAIL": {"CONTACT"},
    "ADDRESS": {"LOCATION"},
    "STREET_ADDRESS": {"LOCATION"},
    "CITY": {"LOCATION"},
    "STATE": {"LOCATION"},
    "ZIP": {"LOCATION"},
    "ZIPCODE": {"LOCATION"},
    "POSTAL_CODE": {"LOCATION"},
    "DATE": {"DATE"},
    "DATE_OF_BIRTH": {"DATE"},
    "DOB": {"DATE"},
    "AGE": {"AGE"},
}

# Labels de gabarito de natureza numerica exigem cobertura mais dura:
# meio CPF tarjado ainda vaza identidade.
NUMERIC_GOLD = {
    "CPF", "RG", "CNS", "CNES", "CARTEIRINHA", "PRONTUARIO", "ATENDIMENTO",
    "GUIA_NUM", "SENHA_AUT", "PHONE", "CEP", "CRM", "COREN", "RQE",
    "NUMERO", "CNPJ",
}

COVERAGE_DEFAULT = 0.6
COVERAGE_NUMERIC = 0.85
COVERAGE_LABEL_OK = 0.5
COVERAGE_REGION_REDACT = 0.8
IOU_REGION_CANDIDATE = 0.3
FP_MAX_GOLD_OVERLAP = 0.3
RASTER_SCALE = 0.5


# --- Corpus ------------------------------------------------------------------


@dataclass
class PageGab:
    width: int
    height: int
    canonical_text: str
    spans: list[dict]
    optional_spans: list[dict]
    regions: list[dict]


@dataclass
class DocGab:
    doc_id: str
    doc_type: str
    file: str  # png ou pdf
    pages: list[PageGab]
    dir: Path


def load_corpus(corpus_dir: Path, docs_filter: str | None) -> list[DocGab]:
    docs: list[DocGab] = []
    for jf in sorted(corpus_dir.glob("*.json")):
        raw = json.loads(jf.read_text(encoding="utf-8"))
        if raw.get("schema_version") != 1:
            raise SystemExit(f"schema_version invalido em {jf.name}")
        if docs_filter and docs_filter not in raw["doc_id"]:
            continue
        pages_raw = raw["pages"] if "pages" in raw else [raw["page"]]
        pages = [
            PageGab(
                width=p["width"],
                height=p["height"],
                canonical_text=p["canonical_text"],
                spans=p["spans"],
                optional_spans=p.get("optional_spans", []),
                regions=p.get("regions", []),
            )
            for p in pages_raw
        ]
        docs.append(
            DocGab(
                doc_id=raw["doc_id"],
                doc_type=raw["doc_type"],
                file=raw.get("image") or raw.get("file"),
                pages=pages,
                dir=corpus_dir,
            )
        )
    if not docs:
        raise SystemExit(f"nenhum gabarito encontrado em {corpus_dir}")
    return docs


def corpus_hash(docs: list[DocGab]) -> str:
    h = hashlib.sha256()
    for d in docs:
        h.update((d.dir / f"{d.doc_id}.json").read_bytes())
    return h.hexdigest()


# --- Normalizacao ------------------------------------------------------------


def norm_text(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.upper().split())


def digits_of(s: str) -> str:
    return "".join(c for c in s if c.isdigit())


def _window_within_1(needle: str, hay: str) -> bool:
    """True se needle aparece em hay com no maximo 1 caractere divergente."""
    n = len(needle)
    if n == 0 or n > len(hay):
        return False
    for i in range(len(hay) - n + 1):
        diff = 0
        for a, b in zip(needle, hay[i : i + n]):
            if a != b:
                diff += 1
                if diff > 1:
                    break
        if diff <= 1:
            return True
    return False


def gold_text_in_ocr(gold_text: str, ocr_text: str) -> bool:
    d = digits_of(gold_text)
    if len(d) >= 6:
        return _window_within_1(d, digits_of(ocr_text))
    return norm_text(gold_text) in norm_text(ocr_text)


# --- Matching em char space (nivel text) ------------------------------------


def interval_coverage(gold: tuple[int, int], preds: list[tuple[int, int]]) -> float:
    gs, ge = gold
    length = ge - gs
    if length <= 0:
        return 0.0
    merged: list[list[int]] = []
    for ps, pe in sorted(preds):
        s, e = max(ps, gs), min(pe, ge)
        if e <= s:
            continue
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return sum(e - s for s, e in merged) / length


def span_threshold(span: dict) -> float:
    if span.get("min_coverage") is not None:
        return float(span["min_coverage"])
    return COVERAGE_NUMERIC if span["label"] in NUMERIC_GOLD else COVERAGE_DEFAULT


def pred_groups(label: str) -> set[str]:
    return PRED_LABEL_GROUPS.get(label.upper(), set())


# --- Matching em pixel space (nivel full) -----------------------------------


class MaskSet:
    """Mascaras raster (escala 0.5) das predicoes, total e por grupo."""

    def __init__(self, width: int, height: int):
        self.w = max(1, int(width * RASTER_SCALE))
        self.h = max(1, int(height * RASTER_SCALE))
        self.total = Image.new("L", (self.w, self.h), 0)
        self.by_group: dict[str, Image.Image] = {}

    def add_polys(self, label: str, bboxes: list) -> None:
        pts_list = [
            [(x * RASTER_SCALE, y * RASTER_SCALE) for x, y in poly] for poly in bboxes
        ]
        d = ImageDraw.Draw(self.total)
        for pts in pts_list:
            d.polygon(pts, fill=255)
        for g in pred_groups(label):
            if g not in self.by_group:
                self.by_group[g] = Image.new("L", (self.w, self.h), 0)
            dg = ImageDraw.Draw(self.by_group[g])
            for pts in pts_list:
                dg.polygon(pts, fill=255)

    def _rect(self, bbox_px: list, scale: float) -> tuple[int, int, int, int]:
        x0, y0, x1, y1 = [v * scale * RASTER_SCALE for v in bbox_px]
        return (
            max(0, int(x0)),
            max(0, int(y0)),
            min(self.w, int(x1 + 0.5)),
            min(self.h, int(y1 + 0.5)),
        )

    def rect_coverage(self, bbox_px: list, scale: float = 1.0, group: str | None = None) -> float:
        rect = self._rect(bbox_px, scale)
        if rect[2] <= rect[0] or rect[3] <= rect[1]:
            return 0.0
        mask = self.total if group is None else self.by_group.get(group)
        if mask is None:
            return 0.0
        area = (rect[2] - rect[0]) * (rect[3] - rect[1])
        covered = ImageStat.Stat(mask.crop(rect)).sum[0] / 255.0
        return covered / area


def polygon_gold_overlap(bboxes: list, gold_rects: list[tuple[float, float, float, float]]) -> float:
    """Fracao da area dos poligonos preditos coberta por retangulos gold."""
    if not bboxes:
        return 1.0
    xs = [p[0] for poly in bboxes for p in poly]
    ys = [p[1] for poly in bboxes for p in poly]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    area = max(1.0, (maxx - minx) * (maxy - miny))
    inter = 0.0
    for gx0, gy0, gx1, gy1 in gold_rects:
        ix = max(0.0, min(maxx, gx1) - max(minx, gx0))
        iy = max(0.0, min(maxy, gy1) - max(miny, gy0))
        inter += ix * iy
    return min(1.0, inter / area)


# --- Resultado ---------------------------------------------------------------


@dataclass
class SpanResult:
    key: str
    doc_id: str
    span: dict
    outcome: str  # hit | hit_mislabel | miss
    coverage: float
    cause: str = ""


@dataclass
class RegionResult:
    key: str
    doc_id: str
    region: dict
    outcome: str  # hit | miss
    coverage: float
    cause: str = ""


@dataclass
class LevelReport:
    level: str
    span_results: list[SpanResult] = field(default_factory=list)
    region_results: list[RegionResult] = field(default_factory=list)
    fp: list[dict] = field(default_factory=list)


# --- Avaliacao nivel text ----------------------------------------------------


def eval_text(docs: list[DocGab], threshold: float) -> LevelReport:
    from app.pii import get_engine

    engine = get_engine()
    engine.warmup()
    rep = LevelReport(level="text")
    for doc in docs:
        for pi, page in enumerate(doc.pages):
            ents = engine.detect(page.canonical_text, threshold=threshold)
            preds = [(e.start, e.end, e.label) for e in ents]
            all_gold = page.spans + page.optional_spans
            gold_ivs = [(s["char_start"], s["char_end"]) for s in all_gold]
            for s in page.spans:
                gold = (s["char_start"], s["char_end"])
                cov = interval_coverage(gold, [(a, b) for a, b, _ in preds])
                cov_label = interval_coverage(
                    gold,
                    [(a, b) for a, b, lbl in preds if s["group"] in pred_groups(lbl)],
                )
                thr = span_threshold(s)
                if cov >= thr and cov_label >= COVERAGE_LABEL_OK:
                    outcome = "hit"
                elif cov >= thr:
                    outcome = "hit_mislabel"
                else:
                    outcome = "miss"
                rep.span_results.append(
                    SpanResult(
                        key=f"{doc.doc_id}#p{pi}#{s['id']}",
                        doc_id=doc.doc_id,
                        span=s,
                        outcome=outcome,
                        coverage=cov,
                        cause="" if outcome != "miss" else "model_miss",
                    )
                )
            for a, b, lbl in preds:
                overlap = interval_coverage((a, b), gold_ivs)
                if overlap < FP_MAX_GOLD_OVERLAP:
                    rep.fp.append(
                        {
                            "doc": doc.doc_id,
                            "label": lbl,
                            "text": page.canonical_text[a:b][:40],
                        }
                    )
    return rep


# --- Avaliacao nivel full ----------------------------------------------------


def _page_images(doc: DocGab) -> list[tuple[Image.Image, float]]:
    """Imagens da pagina + fator de escala gabarito -> imagem renderizada."""
    path = doc.dir / doc.file
    if doc.file.lower().endswith(".pdf"):
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(path))
        out = []
        for i in range(len(pdf)):
            pil = pdf[i].render(scale=2).to_pil().convert("RGB")
            scale = pil.width / doc.pages[i].width
            out.append((pil, scale))
        return out
    img = Image.open(path).convert("RGB")
    return [(img, img.width / doc.pages[0].width)]


def eval_full(docs: list[DocGab], threshold: float) -> LevelReport:
    import io

    from app.mapper import build_entities
    from app.ocr import get_engine as get_ocr
    from app.pii import get_engine as get_pii

    ocr = get_ocr()
    ocr.warmup()
    pii = get_pii()
    pii.warmup()
    rep = LevelReport(level="full")

    for doc in docs:
        images = _page_images(doc)
        for pi, (img, scale) in enumerate(images):
            page = doc.pages[pi]
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            ocr_out = ocr.run(buf.getvalue(), "image/png")
            # run() retorna lista de paginas desde o suporte a multipagina;
            # aceita tambem o formato antigo (objeto unico) por robustez.
            ocr_result = ocr_out[0] if isinstance(ocr_out, list) else ocr_out
            pii_entities = pii.detect(ocr_result.text, threshold=threshold)
            entities = build_entities(pii_entities, ocr_result.lines)

            masks = MaskSet(img.width, img.height)
            for e in entities:
                masks.add_polys(e.label, e.bboxes)

            all_gold_rects = [
                tuple(v * scale for v in s["bbox_px"])
                for s in page.spans + page.optional_spans
            ] + [tuple(v * scale for v in r["bbox_px"]) for r in page.regions]

            for s in page.spans:
                cov = masks.rect_coverage(s["bbox_px"], scale)
                cov_label = masks.rect_coverage(s["bbox_px"], scale, group=s["group"])
                thr = span_threshold(s)
                if cov >= thr and cov_label >= COVERAGE_LABEL_OK:
                    outcome, cause = "hit", ""
                elif cov >= thr:
                    outcome, cause = "hit_mislabel", ""
                else:
                    outcome = "miss"
                    if not gold_text_in_ocr(s["text"], ocr_result.text):
                        cause = "ocr_lost"
                    else:
                        covered_in_text = any(
                            gold_text_in_ocr(s["text"], ocr_result.text[e.start : e.end])
                            for e in pii_entities
                        )
                        cause = "mapping_loss" if covered_in_text else "model_miss"
                rep.span_results.append(
                    SpanResult(
                        key=f"{doc.doc_id}#p{pi}#{s['id']}",
                        doc_id=doc.doc_id,
                        span=s,
                        outcome=outcome,
                        coverage=cov,
                        cause=cause,
                    )
                )

            for r in page.regions:
                cov = masks.rect_coverage(r["bbox_px"], scale)
                need = COVERAGE_REGION_REDACT if r["expect"] == "redact" else IOU_REGION_CANDIDATE
                ok = cov >= need
                rep.region_results.append(
                    RegionResult(
                        key=f"{doc.doc_id}#p{pi}#{r['id']}",
                        doc_id=doc.doc_id,
                        region=r,
                        outcome="hit" if ok else "miss",
                        coverage=cov,
                        cause="" if ok else "detector_absent",
                    )
                )

            for e in entities:
                if polygon_gold_overlap(e.bboxes, all_gold_rects) < FP_MAX_GOLD_OVERLAP:
                    rep.fp.append({"doc": doc.doc_id, "label": e.label, "text": e.text[:40]})
    return rep


# --- Relatorio ---------------------------------------------------------------


def print_report(rep: LevelReport, baseline: dict | None) -> bool:
    """Imprime o relatorio; retorna True se houve regressao vs baseline."""
    misses = [r for r in rep.span_results if r.outcome == "miss"]
    region_misses = [r for r in rep.region_results if r.outcome == "miss"]

    print()
    print(f"== NIVEL {rep.level.upper()} " + "=" * 50)
    print(f"== FALSOS NEGATIVOS ({len(misses)}) " + "=" * 40)
    for r in sorted(misses, key=lambda x: (x.doc_id, x.key)):
        s = r.span
        hard = "  (hard)" if s.get("difficulty") == "hard" else ""
        print(
            f"[{r.doc_id}] {s['id']} {s['label']:<13} {s['text'][:38]!r:<42} "
            f"cov={r.coverage:.2f}  causa={r.cause}{hard}"
        )
    if region_misses:
        print(f"-- Regioes nao cobertas ({len(region_misses)}):")
        for r in region_misses:
            g = r.region
            print(
                f"[{r.doc_id}] {g['id']} {g['kind']:<16} expect={g['expect']:<9} "
                f"cov={r.coverage:.2f}  causa={r.cause}"
            )

    by_label: dict[str, dict[str, int]] = {}
    for r in rep.span_results:
        d = by_label.setdefault(r.span["label"], {"gold": 0, "hit": 0, "mislabel": 0, "miss": 0})
        d["gold"] += 1
        d["hit" if r.outcome == "hit" else "mislabel" if r.outcome == "hit_mislabel" else "miss"] += 1

    print()
    print("== RECALL POR LABEL " + "=" * 44)
    print(f"{'LABEL':<15}{'GOLD':>5}{'HIT':>5}{'MISLBL':>7}{'MISS':>6}{'R_LABEL':>9}{'R_COBERTO':>11}")
    total = {"gold": 0, "hit": 0, "mislabel": 0, "miss": 0}
    for label in sorted(by_label, key=lambda k: -by_label[k]["miss"]):
        d = by_label[label]
        for k in total:
            total[k] += d[k]
        r_lbl = d["hit"] / d["gold"]
        r_cov = (d["hit"] + d["mislabel"]) / d["gold"]
        print(f"{label:<15}{d['gold']:>5}{d['hit']:>5}{d['mislabel']:>7}{d['miss']:>6}{r_lbl:>9.2f}{r_cov:>11.2f}")
    if total["gold"]:
        r_lbl = total["hit"] / total["gold"]
        r_cov = (total["hit"] + total["mislabel"]) / total["gold"]
        print(f"{'TOTAL':<15}{total['gold']:>5}{total['hit']:>5}{total['mislabel']:>7}{total['miss']:>6}{r_lbl:>9.2f}{r_cov:>11.2f}")

    fp_by_label: dict[str, int] = {}
    for f in rep.fp:
        fp_by_label[f["label"]] = fp_by_label.get(f["label"], 0) + 1
    print()
    print(f"== PRECISAO (FP = ruido aceitavel): {len(rep.fp)} total " + "=" * 20)
    for lbl, n in sorted(fp_by_label.items(), key=lambda kv: -kv[1]):
        print(f"  {lbl}: {n}")

    regressed = False
    if baseline:
        old = baseline.get("outcomes", {})
        new = outcomes_dict(rep)
        covered = {"hit", "hit_mislabel"}
        regs = [k for k, v in new.items() if old.get(k) in covered and v == "miss"]
        fixed = [k for k, v in new.items() if old.get(k) == "miss" and v in covered]
        print()
        print(f"== DELTA vs baseline ({baseline.get('created', '?')}) " + "=" * 24)
        print(f"REGRESSOES ({len(regs)}):")
        for k in regs:
            print(f"  {k}")
        print(f"CORRIGIDOS ({len(fixed)}):")
        for k in fixed:
            print(f"  {k}")
        regressed = bool(regs)
    return regressed


def outcomes_dict(rep: LevelReport) -> dict[str, str]:
    out = {r.key: r.outcome for r in rep.span_results}
    out.update({r.key: r.outcome for r in rep.region_results})
    return out


def save_baseline(rep: LevelReport, docs: list[DocGab], baselines_dir: Path) -> None:
    baselines_dir.mkdir(parents=True, exist_ok=True)
    total = len(rep.span_results)
    hits = sum(1 for r in rep.span_results if r.outcome == "hit")
    covered = sum(1 for r in rep.span_results if r.outcome in ("hit", "hit_mislabel"))
    data = {
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "level": rep.level,
        "corpus_hash": corpus_hash(docs),
        "outcomes": outcomes_dict(rep),
        "metrics": {
            "gold": total,
            "recall_label": round(hits / total, 4) if total else None,
            "recall_coberto": round(covered / total, 4) if total else None,
            "fn": total - covered,
            "fp": len(rep.fp),
            "region_miss": sum(1 for r in rep.region_results if r.outcome == "miss"),
        },
    }
    path = baselines_dir / f"baseline-{rep.level}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nBaseline salvo em {path}")


def load_baseline(level: str, baselines_dir: Path, docs: list[DocGab]) -> dict | None:
    path = baselines_dir / f"baseline-{level}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("corpus_hash") != corpus_hash(docs):
        print(f"AVISO: corpus mudou desde o baseline {path.name}; delta nao e comparavel.")
    return data


# --- Main --------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--level", choices=["text", "full", "both"], default="both")
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--baselines", type=Path, default=DEFAULT_BASELINES)
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--docs", help="filtra doc_ids contendo esta substring")
    ap.add_argument("--save-baseline", action="store_true")
    args = ap.parse_args()

    try:
        docs = load_corpus(args.corpus, args.docs)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"erro de corpus: {exc}", file=sys.stderr)
        return 2

    from app.config import get_settings

    settings = get_settings()
    print(f"Corpus: {len(docs)} documentos em {args.corpus}")
    print(f"Modo: {'MOCK' if settings.mock_mode else 'modelo real'}  threshold={args.threshold}")

    levels = ["text", "full"] if args.level == "both" else [args.level]
    regressed = False
    for level in levels:
        rep = eval_text(docs, args.threshold) if level == "text" else eval_full(docs, args.threshold)
        baseline = None if args.save_baseline else load_baseline(level, args.baselines, docs)
        if print_report(rep, baseline):
            regressed = True
        if args.save_baseline:
            save_baseline(rep, docs, args.baselines)
    return 1 if regressed else 0


if __name__ == "__main__":
    sys.exit(main())
