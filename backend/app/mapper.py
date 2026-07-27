"""Map PII character spans back to image space bboxes.

The OCR module already gives us, for every line, a quadrilateral bbox plus
the inclusive char_start and exclusive char_end of that line in the
continuous text stream. To map a PII span [s, e] we:

1. Find every line whose char range overlaps [s, e].
2. For each line, clip [s, e] to that line and compute the proportional
   horizontal slice along the top and bottom edges of the line bbox.
3. Emit one sub bbox per line so a single entity can produce multiple
   highlights when it wraps.
"""

from __future__ import annotations

from .models import BBox, Entity, OCRBlock
from .ocr import OCRLine, OCRResult
from .pii import PIIEntity, label_placeholder


def _interp(p1: list[float], p2: list[float], t: float) -> list[float]:
    return [p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t]


def _line_subbox(line: OCRLine, char_a: int, char_b: int) -> BBox | None:
    """Return the proportional sub bbox covering chars [char_a, char_b)."""
    length = max(line.length(), 1)
    a = max(0, char_a - line.char_start)
    b = min(line.length(), char_b - line.char_start)
    if b <= a:
        return None
    t_a = a / length
    t_b = b / length
    # bbox order from PaddleOCR: TL, TR, BR, BL
    tl, tr, br, bl = line.bbox[0], line.bbox[1], line.bbox[2], line.bbox[3]
    top_a = _interp(tl, tr, t_a)
    top_b = _interp(tl, tr, t_b)
    bot_a = _interp(bl, br, t_a)
    bot_b = _interp(bl, br, t_b)
    return [top_a, top_b, bot_b, bot_a]


def span_to_bboxes(span: tuple[int, int], lines: list[OCRLine]) -> list[BBox]:
    s, e = span
    if e <= s:
        return []
    out: list[BBox] = []
    for line in lines:
        if line.char_end <= s or line.char_start >= e:
            continue
        sub = _line_subbox(line, s, e)
        if sub is not None:
            out.append(sub)
    return out


def build_ocr_blocks(result: OCRResult) -> list[OCRBlock]:
    return [
        OCRBlock(
            text=line.text,
            bbox=line.bbox,
            confidence=line.confidence,
            char_start=line.char_start,
            char_end=line.char_end,
        )
        for line in result.lines
    ]


def build_entities(
    pii: list[PIIEntity],
    lines: list[OCRLine],
) -> list[Entity]:
    out: list[Entity] = []
    for e in pii:
        bboxes = span_to_bboxes((e.start, e.end), lines)
        if not bboxes:
            # entity exists in text but mapped to no visible region; skip,
            # since the frontend has no way to render it.
            continue
        out.append(
            Entity(
                label=e.label,
                text=e.text,
                score=e.score,
                char_span=(e.start, e.end),
                bboxes=bboxes,
                redacted=label_placeholder(e.label),
            )
        )
    return out


def deidentify_text(text: str, pii: list[PIIEntity]) -> str:
    """Replace each PII span with its redaction placeholder.

    Operates in reverse so character offsets earlier in the string remain
    valid as we mutate later positions.
    """
    if not pii:
        return text
    sorted_pii = sorted(pii, key=lambda x: x.start, reverse=True)
    out = text
    for e in sorted_pii:
        out = out[: e.start] + label_placeholder(e.label) + out[e.end :]
    return out


def stats_by_label(entities: list[Entity]) -> dict[str, int]:
    by_label: dict[str, int] = {}
    for e in entities:
        by_label[e.label] = by_label.get(e.label, 0) + 1
    return by_label
