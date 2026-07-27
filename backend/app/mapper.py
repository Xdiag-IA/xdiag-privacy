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

from .config import get_settings
from .models import BBox, Entity, OCRBlock
from .ocr import OCRLine, OCRResult
from .pii import PIIEntity, label_placeholder


def _interp(p1: list[float], p2: list[float], t: float) -> list[float]:
    return [p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t]


# Larguras de avanco aproximadas, relativas a uma minuscula media (1.0).
# Interpolar por CONTAGEM de caracteres assume fonte monoespacada e produz
# deriva acumulada em fonte proporcional: num laudo em italico, o span
# correto "ANA CAROLINA" era desenhado sobre "NA CAROLINA F". A tabela nao
# precisa ser exata, so precisa distinguir estreito de largo, o que derruba
# a deriva de ~1 caractere para bem abaixo da folga de seguranca.
_CHAR_WIDTH: dict[str, float] = {}
for _c in "ilj|!.,;:'`":
    _CHAR_WIDTH[_c] = 0.40
for _c in "ftrI()[]{}/\\- \"":
    _CHAR_WIDTH[_c] = 0.60
for _c in "mw@":
    _CHAR_WIDTH[_c] = 1.65
for _c in "MW":
    _CHAR_WIDTH[_c] = 1.80


def _char_width(c: str) -> float:
    w = _CHAR_WIDTH.get(c)
    if w is not None:
        return w
    return 1.30 if c.isupper() else 1.0


def _cumulative_widths(s: str) -> list[float]:
    """Soma prefixa das larguras: cum[i] e a largura de s[:i]."""
    cum = [0.0]
    total = 0.0
    for c in s:
        total += _char_width(c)
        cum.append(total)
    return cum


def _line_subbox(line: OCRLine, char_a: int, char_b: int) -> BBox | None:
    """Sub bbox cobrindo os chars [char_a, char_b) da linha.

    A posicao horizontal e estimada por largura de avanco acumulada, nao por
    contagem de caracteres, e depois recebe uma folga fail-closed: cobrir um
    caractere vizinho e inofensivo, deixar meia letra do nome para fora da
    tarja preta na imagem exportada e vazamento.
    """
    length = max(line.length(), 1)
    a = max(0, char_a - line.char_start)
    b = min(line.length(), char_b - line.char_start)
    if b <= a:
        return None

    text = line.text
    if len(text) == length:
        cum = _cumulative_widths(text)
        total = cum[-1] or 1.0
        t_a = cum[a] / total
        t_b = cum[b] / total
        avg = total / length
    else:
        # Comprimento divergente (nao deveria acontecer): cai no proporcional
        # simples, que e pior mas nunca pior do que nao mapear.
        t_a = a / length
        t_b = b / length
        avg = 1.0
        total = float(length)

    settings = get_settings()
    pad = settings.bbox_pad_chars * avg / total
    t_a = max(0.0, t_a - pad)
    t_b = min(1.0, t_b + pad)

    # bbox order from PaddleOCR: TL, TR, BR, BL
    tl, tr, br, bl = line.bbox[0], line.bbox[1], line.bbox[2], line.bbox[3]
    top_a = _interp(tl, tr, t_a)
    top_b = _interp(tl, tr, t_b)
    bot_a = _interp(bl, br, t_a)
    bot_b = _interp(bl, br, t_b)

    # Folga vertical simetrica, na direcao da propria altura da linha (o
    # bbox do OCR pode vir inclinado, entao usa o vetor topo->base).
    vpad = settings.bbox_pad_lines
    if vpad > 0:
        out: list[list[float]] = []
        for top, bot in ((top_a, bot_a), (top_b, bot_b)):
            dx = bot[0] - top[0]
            dy = bot[1] - top[1]
            out.append([top[0] - dx * vpad, top[1] - dy * vpad])
            out.append([bot[0] + dx * vpad, bot[1] + dy * vpad])
        # out = [TL, BL, TR, BR] -> reordena para TL, TR, BR, BL
        return [out[0], out[2], out[3], out[1]]

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
        # Entidade sem regiao mapeada NUNCA e descartada: descartar aqui e
        # fail-open (o texto mostra [CPF] mas a imagem exportada mostra o
        # CPF). Ela segue na resposta com unmapped=True e o frontend bloqueia
        # o export ate o usuario resolver.
        out.append(
            Entity(
                label=e.label,
                text=e.text,
                score=e.score,
                char_span=(e.start, e.end),
                bboxes=bboxes,
                redacted=label_placeholder(e.label),
                unmapped=not bboxes,
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
