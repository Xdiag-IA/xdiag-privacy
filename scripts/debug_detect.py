"""Depuracao pontual: saida crua do modelo e resultado final de detect().

Uso: docker compose run --rm --entrypoint python eval /app/scripts/debug_detect.py <doc_id> <trecho>
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

if Path("/app/app").exists():
    sys.path.insert(0, "/app")
    CORPUS = Path("/app/tests/corpus")
else:
    ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(ROOT / "backend"))
    CORPUS = ROOT / "tests" / "corpus"

os.environ.setdefault("XDIAG_EAGER_LOAD", "0")

from app.pii import get_engine  # noqa: E402


def main() -> int:
    doc_id = sys.argv[1]
    needle = sys.argv[2]
    raw = json.loads((CORPUS / f"{doc_id}.json").read_text(encoding="utf-8"))
    page = raw["pages"][0] if "pages" in raw else raw["page"]
    text = page["canonical_text"]
    pos = text.find(needle)
    print(f"trecho em [{pos}, {pos + len(needle)})")

    eng = get_engine()
    eng.warmup()

    if eng._pipe is not None:
        lo, hi = max(0, pos - 60), pos + len(needle) + 60
        print("--- saida crua do modelo perto do trecho ---")
        for r in eng._pipe(text) or []:
            s, e = int(r.get("start", -1)), int(r.get("end", -1))
            if e >= lo and s <= hi:
                print(f"  {r.get('entity_group') or r.get('entity')}  score={float(r.get('score', 0)):.3f}  [{s},{e})  {text[s:e]!r}")

    print("--- detect() final perto do trecho ---")
    for ent in eng.detect(text, threshold=0.5):
        if ent.end >= pos - 60 and ent.start <= pos + len(needle) + 60:
            print(f"  {ent.label}  score={ent.score:.3f}  [{ent.start},{ent.end})  {ent.text!r}  origin={ent.origin} validated={ent.validated} strong={ent.strong}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
