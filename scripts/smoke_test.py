"""Smoke test for the backend pipeline in mock mode.

Runs OCR (mock) plus PII (mock heuristics) plus mapper end to end against an
in memory image, and prints the resulting entities and bboxes. Useful for
validating the data shapes without spinning up the full Docker stack.

Usage:
    XDIAG_MOCK=1 python scripts/smoke_test.py
"""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

os.environ.setdefault("XDIAG_MOCK", "1")
os.environ.setdefault("XDIAG_EAGER_LOAD", "0")

from PIL import Image  # noqa: E402

from app.mapper import build_entities, build_ocr_blocks, deidentify_text, stats_by_label  # noqa: E402
from app.ocr import get_engine as get_ocr  # noqa: E402
from app.pii import get_engine as get_pii  # noqa: E402


def main() -> int:
    img = Image.new("RGB", (1240, 1754), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw = buf.getvalue()

    ocr = get_ocr()
    ocr.warmup()
    pii = get_pii()
    pii.warmup()

    ocr_result = ocr.run(raw, "image/png")
    pii_entities = pii.detect(ocr_result.text, threshold=0.5)
    blocks = build_ocr_blocks(ocr_result)
    entities = build_entities(pii_entities, ocr_result.lines)
    deident = deidentify_text(ocr_result.text, pii_entities)

    out = {
        "image_dimensions": {"w": ocr_result.width, "h": ocr_result.height},
        "ocr_lines": len(blocks),
        "entities": [
            {
                "label": e.label,
                "text": e.text,
                "score": round(e.score, 3),
                "char_span": e.char_span,
                "n_bboxes": len(e.bboxes),
            }
            for e in entities
        ],
        "stats": {"total_entities": len(entities), "by_label": stats_by_label(entities)},
        "deidentified_text": deident,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if entities else 2


if __name__ == "__main__":
    sys.exit(main())
