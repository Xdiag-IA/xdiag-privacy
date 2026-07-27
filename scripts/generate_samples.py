"""Gera o corpus sintetico de documentos medicos brasileiros com gabarito.

Duas saidas:
  tests/corpus/   17 PNGs + 1 PDF multipagina, cada um com um .json de
                  gabarito listando os spans de PII que DEVEM ser tarjados
                  (char offsets no texto canonico + bbox em pixels), spans
                  opcionais (sem penalidade) e regioes nao textuais
                  (barcode, QR, assinatura, faixa de ultrassom).
  samples/        3 PNGs de demonstracao para o frontend (sem gabarito).

Todos os identificadores sao ficticios mas passam nos validadores de
digito verificador (CPF, CNPJ, CNS), para exercitar o pipeline real.
Marca dagua SYNTHETIC em todas as paginas.

Uso (host, requer scripts/requirements-dev.txt):
    python scripts/generate_samples.py            # corpus + samples
    python scripts/generate_samples.py --corpus   # apenas tests/corpus/
    python scripts/generate_samples.py --samples  # apenas samples/
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = ROOT / "samples"
CORPUS_DIR = ROOT / "tests" / "corpus"

WIDTH = 1240
HEIGHT = 1754  # A4 aproximado a 150 DPI
SEED = 42

SCHEMA_VERSION = 1
SCRIPT_VERSION = "2"

# --- Labels do gabarito e grupos de equivalencia ----------------------------
# O gabarito usa granularidade brasileira; o campo group pre-computa o grupo
# usado pelo evaluate.py para aceitar labels equivalentes do pipeline.

LABEL_GROUP: dict[str, str] = {
    "PATIENT_NAME": "NAME",
    "DOCTOR_NAME": "NAME",
    "OTHER_NAME": "NAME",
    "CPF": "DOC_NUM",
    "RG": "DOC_NUM",
    "CNS": "DOC_NUM",
    "CNES": "DOC_NUM",
    "CRM": "DOC_NUM",
    "COREN": "DOC_NUM",
    "RQE": "DOC_NUM",
    "PRONTUARIO": "DOC_NUM",
    "ATENDIMENTO": "DOC_NUM",
    "CARTEIRINHA": "DOC_NUM",
    "GUIA_NUM": "DOC_NUM",
    "SENHA_AUT": "DOC_NUM",
    "NUMERO": "DOC_NUM",
    "PHONE": "CONTACT",
    "EMAIL": "CONTACT",
    "ADDRESS": "LOCATION",
    "CEP": "LOCATION",
    "DATE": "DATE",
    "DATE_OF_BIRTH": "DATE",
    "AGE": "AGE",
    "CNPJ": "ORG",
    "INSTITUTION": "ORG",
}


# --- Validadores geradores (espelham backend/app/pii.py) --------------------


def _cpf_dv(digits: list[int], n: int) -> int:
    s = sum((n + 1 - i) * digits[i] for i in range(n))
    r = (s * 10) % 11
    return 0 if r == 10 else r


def make_cpf(base9: str) -> str:
    """Completa 9 digitos com os 2 DVs e formata ###.###.###-##."""
    nums = [int(c) for c in base9]
    nums.append(_cpf_dv(nums, 9))
    nums.append(_cpf_dv(nums, 10))
    d = "".join(str(x) for x in nums)
    return f"{d[0:3]}.{d[3:6]}.{d[6:9]}-{d[9:11]}"


def make_cnpj(base12: str) -> str:
    nums = [int(c) for c in base12]
    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    w2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    r = sum(nums[i] * w1[i] for i in range(12)) % 11
    nums.append(0 if r < 2 else 11 - r)
    r = sum(nums[i] * w2[i] for i in range(13)) % 11
    nums.append(0 if r < 2 else 11 - r)
    d = "".join(str(x) for x in nums)
    return f"{d[0:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}"


def make_cns_definitivo(pis11: str) -> str:
    """CNS definitivo (inicia em 1 ou 2), algoritmo do PIS com DV proprio."""
    soma = sum(int(pis11[i]) * (15 - i) for i in range(11))
    resto = soma % 11
    dv = 11 - resto
    if dv == 11:
        dv = 0
    if dv == 10:
        soma2 = soma + 2
        dv = 11 - (soma2 % 11)
        if dv == 11:
            dv = 0
        return pis11 + "001" + str(dv)
    return pis11 + "000" + str(dv)


def make_cns_provisorio(prefix14: str) -> str:
    """CNS provisorio (inicia em 7, 8 ou 9): soma ponderada divisivel por 11."""
    digits = [int(c) for c in prefix14]
    while True:
        soma = sum(digits[i] * (15 - i) for i in range(14))
        d = (11 - soma % 11) % 11
        if d < 10:
            return "".join(str(x) for x in digits) + str(d)
        digits[13] = (digits[13] + 1) % 10


def fmt_cns(cns15: str) -> str:
    return f"{cns15[0:3]} {cns15[3:7]} {cns15[7:11]} {cns15[11:15]}"


# --- Fontes -----------------------------------------------------------------

_FONT_CANDIDATES: dict[tuple[bool, bool], list[str]] = {
    # (bold, mono) -> caminhos candidatos
    (False, False): [
        "C:\\Windows\\Fonts\\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial.ttf",
    ],
    (True, False): [
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    (False, True): [
        "C:\\Windows\\Fonts\\consola.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ],
    (True, True): [
        "C:\\Windows\\Fonts\\consolab.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    ],
}

_font_cache: dict[tuple[int, bool, bool], ImageFont.FreeTypeFont] = {}


def font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    key = (size, bold, mono)
    if key in _font_cache:
        return _font_cache[key]
    for path in _FONT_CANDIDATES[(bold, mono)] + _FONT_CANDIDATES[(False, False)]:
        if os.path.exists(path):
            f = ImageFont.truetype(path, size=size)
            _font_cache[key] = f
            return f
    raise RuntimeError("nenhuma fonte TTF encontrada; instale Arial ou DejaVu")


# --- Registros do gabarito --------------------------------------------------


@dataclass
class SpanRecord:
    id: str
    label: str
    text: str
    char_start: int
    char_end: int
    bbox_px: list[int]  # [x0, y0, x1, y1]
    optional: bool = False
    difficulty: str = "normal"
    min_coverage: float | None = None
    note: str = ""


@dataclass
class RegionRecord:
    id: str
    kind: str  # barcode_code128 | qrcode | signature | us_header
    bbox_px: list[int]
    payload: str | None
    contains_pii: bool
    expect: str  # redact | candidate


_MARKER_RE = re.compile(r"\{([A-Z_]+)(\??)(?:#(hard))?\|([^}]*)\}")


@dataclass
class Page:
    """Pagina sintetica que desenha texto e registra o gabarito.

    O texto canonico acumulado segue a mesma convencao do stream do OCR:
    uma linha por chamada de desenho, unidas por \n, e cada span conhece
    o offset em chars e a bbox em pixels da mesma fonte usada no desenho.
    """

    width: int = WIDTH
    height: int = HEIGHT
    bg: tuple[int, int, int] = (255, 255, 255)
    img: Image.Image = field(init=False)
    draw: ImageDraw.ImageDraw = field(init=False)
    x: int = 80
    y: int = 60
    line_height: int = 28
    _cursor_chars: int = field(default=0, init=False)
    _text_parts: list[str] = field(default_factory=list, init=False)
    spans: list[SpanRecord] = field(default_factory=list, init=False)
    regions: list[RegionRecord] = field(default_factory=list, init=False)
    _span_n: int = field(default=0, init=False)
    _region_n: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.img = Image.new("RGBA", (self.width, self.height), (*self.bg, 255))
        self.draw = ImageDraw.Draw(self.img)

    # -- API de layout --

    def at(self, x: int, y: int) -> "Page":
        self.x, self.y = x, y
        return self

    def gap(self, px: int) -> None:
        self.y += px

    def text_at(
        self,
        x: int,
        y: int,
        template: str,
        *,
        size: int = 20,
        bold: bool = False,
        mono: bool = False,
        color: tuple[int, int, int] = (20, 20, 20),
    ) -> tuple[str, int]:
        """Desenha uma linha com marcadores {LABEL|texto} e registra spans.

        Sufixo ? no label = span opcional; sufixo #hard = difficulty hard.
        Retorna (texto_limpo, largura_px).
        """
        f = font(size, bold=bold, mono=mono)
        clean_parts: list[str] = []
        markers: list[tuple[str, bool, str, str, int]] = []  # label, opt, diff, txt, off
        pos = 0
        offset = 0
        for m in _MARKER_RE.finditer(template):
            lit = template[pos : m.start()]
            clean_parts.append(lit)
            offset += len(lit)
            label, opt, hard, inner = m.group(1), m.group(2) == "?", m.group(3), m.group(4)
            markers.append((label, opt, "hard" if hard else "normal", inner, offset))
            clean_parts.append(inner)
            offset += len(inner)
            pos = m.end()
        clean_parts.append(template[pos:])
        clean = "".join(clean_parts)

        self.draw.text((x, y), clean, font=f, fill=color)
        line_bbox = self.draw.textbbox((x, y), clean, font=f)

        line_start = self._cursor_chars
        for label, opt, diff, inner, off in markers:
            if label not in LABEL_GROUP:
                raise ValueError(f"label desconhecido no gabarito: {label}")
            prefix = clean[:off]
            x0 = x + self.draw.textlength(prefix, font=f)
            x1 = x + self.draw.textlength(prefix + inner, font=f)
            self._span_n += 1
            self.spans.append(
                SpanRecord(
                    id=f"s{self._span_n:02d}",
                    label=label,
                    text=inner,
                    char_start=line_start + off,
                    char_end=line_start + off + len(inner),
                    bbox_px=[
                        int(x0) - 2,
                        line_bbox[1] - 2,
                        int(math.ceil(x1)) + 2,
                        line_bbox[3] + 2,
                    ],
                    optional=opt,
                    difficulty=diff,
                )
            )
        self._text_parts.append(clean)
        self._cursor_chars += len(clean) + 1  # newline separador
        return clean, int(self.draw.textlength(clean, font=f))

    def line(
        self,
        template: str,
        *,
        size: int = 20,
        bold: bool = False,
        mono: bool = False,
        color: tuple[int, int, int] = (20, 20, 20),
        advance: int | None = None,
    ) -> None:
        self.text_at(self.x, self.y, template, size=size, bold=bold, mono=mono, color=color)
        self.y += advance if advance is not None else self.line_height

    def center(
        self,
        template: str,
        y: int,
        *,
        size: int = 26,
        bold: bool = True,
        color: tuple[int, int, int] = (15, 23, 42),
    ) -> None:
        clean = _MARKER_RE.sub(lambda m: m.group(4), template)
        f = font(size, bold=bold)
        w = self.draw.textlength(clean, font=f)
        self.text_at(int((self.width - w) // 2), y, template, size=size, bold=bold, color=color)

    def separator(self, y: int | None = None, color=(148, 163, 184)) -> None:
        yy = self.y if y is None else y
        self.draw.line([(80, yy), (self.width - 80, yy)], fill=color, width=1)

    def header_bar(self, title: str, subtitle: str) -> None:
        self.draw.rectangle([(0, 0), (self.width, 110)], fill=(15, 23, 42))
        self.draw.rectangle([(0, 110), (self.width, 116)], fill=(220, 38, 38))
        self.text_at(80, 24, "Xdiag", size=32, bold=True, color=(248, 250, 252))
        self.text_at(80, 70, title, size=20, color=(203, 213, 225))
        clean = _MARKER_RE.sub(lambda m: m.group(4), subtitle)
        f = font(16)
        w = self.draw.textlength(clean, font=f)
        self.text_at(int(self.width - 80 - w), 78, subtitle, size=16, color=(148, 163, 184))

    # -- Regioes nao textuais --

    def add_region(
        self,
        kind: str,
        bbox: list[int],
        payload: str | None,
        expect: str,
        contains_pii: bool = True,
    ) -> None:
        self._region_n += 1
        self.regions.append(
            RegionRecord(
                id=f"r{self._region_n:02d}",
                kind=kind,
                bbox_px=bbox,
                payload=payload,
                contains_pii=contains_pii,
                expect=expect,
            )
        )

    def paste_barcode(self, payload: str, x: int, y: int, *, target_w: int = 420, expect: str = "redact") -> None:
        img = _render_code128(payload)
        scale = target_w / img.width
        img = img.resize((target_w, int(img.height * scale)), Image.NEAREST)
        self.img.paste(img, (x, y))
        self.add_region("barcode_code128", [x, y, x + img.width, y + img.height], payload, expect)

    def paste_qr(self, payload: str, x: int, y: int, *, box_size: int = 4, expect: str = "redact") -> None:
        img = _render_qr(payload, box_size=box_size)
        self.img.paste(img, (x, y))
        self.add_region("qrcode", [x, y, x + img.width, y + img.height], payload, expect)

    def draw_signature(self, x: int, y: int, w: int, h: int, rng: random.Random) -> None:
        """Assinatura simulada: tracos bezier continuos com tinta azul escura."""
        ink = (28, 32, 84)
        strokes = rng.randint(3, 5)
        for _ in range(strokes):
            px = x + rng.randint(0, w // 4)
            py = y + rng.randint(h // 4, 3 * h // 4)
            pts = [(px, py)]
            segs = rng.randint(3, 6)
            for s in range(segs):
                px += rng.randint(w // (segs * 2), w // segs)
                py = y + rng.randint(0, h)
                pts.append((px, py))
            path = _bezier_chain(pts, rng)
            self.draw.line(path, fill=ink, width=3, joint="curve")
        self.add_region("signature", [x - 6, y - 6, x + w + 6, y + h + 6], None, "candidate")

    # -- Finalizacao --

    def watermark(self, text: str = "SYNTHETIC") -> None:
        overlay = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        size = max(60, int(self.width / 9))
        f = font(size, bold=True)
        bbox = od.textbbox((0, 0), text, font=f)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        rotated = Image.new("RGBA", (tw + 40, th + 40), (0, 0, 0, 0))
        rd = ImageDraw.Draw(rotated)
        rd.text((20, 20), text, font=f, fill=(220, 38, 38, 70))
        rotated = rotated.rotate(30, expand=True, resample=Image.BICUBIC)
        rx = (self.img.width - rotated.width) // 2
        ry = (self.img.height - rotated.height) // 2
        overlay.paste(rotated, (rx, ry), rotated)
        self.img.alpha_composite(overlay)

    @property
    def canonical_text(self) -> str:
        return "\n".join(self._text_parts)

    def page_dict(self) -> dict:
        text = self.canonical_text
        for s in self.spans:
            got = text[s.char_start : s.char_end]
            if got != s.text:
                raise AssertionError(
                    f"gabarito inconsistente: esperado {s.text!r}, offsets dao {got!r}"
                )
        return {
            "width": self.width,
            "height": self.height,
            "canonical_text": text,
            "spans": [_span_json(s) for s in self.spans if not s.optional],
            "optional_spans": [_span_json(s) for s in self.spans if s.optional],
            "regions": [
                {
                    "id": r.id,
                    "kind": r.kind,
                    "bbox_px": r.bbox_px,
                    "payload": r.payload,
                    "contains_pii": r.contains_pii,
                    "expect": r.expect,
                }
                for r in self.regions
            ],
        }

    def save_png(self, out_dir: Path, doc_id: str, doc_type: str, *, gabarito: bool = True) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        rgb = self.img.convert("RGB")
        rgb.save(out_dir / f"{doc_id}.png", format="PNG", optimize=True)
        if not gabarito:
            return
        doc = {
            "schema_version": SCHEMA_VERSION,
            "doc_id": doc_id,
            "doc_type": doc_type,
            "image": f"{doc_id}.png",
            "generator": {"seed": SEED, "script_version": SCRIPT_VERSION},
            "page": self.page_dict(),
        }
        (out_dir / f"{doc_id}.json").write_text(
            json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8"
        )


def _span_json(s: SpanRecord) -> dict:
    out = {
        "id": s.id,
        "label": s.label,
        "group": LABEL_GROUP[s.label],
        "text": s.text,
        "char_start": s.char_start,
        "char_end": s.char_end,
        "bbox_px": s.bbox_px,
        "difficulty": s.difficulty,
    }
    if s.min_coverage is not None:
        out["min_coverage"] = s.min_coverage
    if s.note:
        out["note"] = s.note
    return out


def save_pdf(pages: list[Page], out_dir: Path, doc_id: str, doc_type: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    imgs = [p.img.convert("RGB") for p in pages]
    imgs[0].save(out_dir / f"{doc_id}.pdf", save_all=True, append_images=imgs[1:])
    doc = {
        "schema_version": SCHEMA_VERSION,
        "doc_id": doc_id,
        "doc_type": doc_type,
        "file": f"{doc_id}.pdf",
        "generator": {"seed": SEED, "script_version": SCRIPT_VERSION},
        "pages": [p.page_dict() for p in pages],
    }
    (out_dir / f"{doc_id}.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# --- Assets: barcode, QR, bezier, speckle ------------------------------------


def _render_code128(payload: str) -> Image.Image:
    try:
        import barcode
        from barcode.writer import ImageWriter
    except ImportError as exc:
        raise SystemExit(
            "python-barcode ausente; rode: pip install -r scripts/requirements-dev.txt"
        ) from exc
    code = barcode.get("code128", payload, writer=ImageWriter())
    img = code.render(writer_options={"write_text": False, "module_height": 9.0, "quiet_zone": 2.0})
    return img.convert("RGB")


def _render_qr(payload: str, box_size: int = 4) -> Image.Image:
    try:
        import qrcode
    except ImportError as exc:
        raise SystemExit(
            "qrcode ausente; rode: pip install -r scripts/requirements-dev.txt"
        ) from exc
    q = qrcode.make(payload, box_size=box_size, border=2)
    img = q.get_image() if hasattr(q, "get_image") else q
    return img.convert("RGB")


def _bezier_chain(pts: list[tuple[int, int]], rng: random.Random) -> list[tuple[int, int]]:
    """Interpola quadraticamente entre pontos de controle, 12 passos por trecho."""
    path: list[tuple[int, int]] = []
    for i in range(len(pts) - 1):
        p0 = pts[i]
        p2 = pts[i + 1]
        cx = (p0[0] + p2[0]) // 2 + rng.randint(-18, 18)
        cy = (p0[1] + p2[1]) // 2 + rng.randint(-24, 24)
        for t in range(13):
            u = t / 12.0
            bx = (1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * cx + u**2 * p2[0]
            by = (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * cy + u**2 * p2[1]
            path.append((int(bx), int(by)))
    return path


def _paste_speckle_fan(page: Page, apex: tuple[int, int], depth: int, half_angle_deg: float) -> None:
    """Leque de ultrassom: ruido cinza medio (speckle) mascarado em setor."""
    w, h = page.img.size
    noise = Image.effect_noise((w, h), 52).point(lambda p: 40 + (p * 140) // 255)
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    ax, ay = apex
    half = math.radians(half_angle_deg)
    poly = [(ax, ay)]
    steps = 24
    for i in range(steps + 1):
        ang = -half + (2 * half) * i / steps
        poly.append((ax + depth * math.sin(ang), ay + depth * math.cos(ang)))
    md.polygon(poly, fill=255)
    page.img.paste(noise.convert("RGBA"), (0, 0), mask)


# --- Pool de dados ficticios -------------------------------------------------

CPF_MARIA = make_cpf("529982247")          # 529.982.247-25
CPF_CARLOS = make_cpf("111444777")         # 111.444.777-35
CPF_ANA = make_cpf("935411347")            # 935.411.347-80
CPF_BEATRIZ = make_cpf("864213705")
CPF_JOSE = make_cpf("407156382")
CPF_TEREZA = make_cpf("218903476")
CNPJ_CLINICA = make_cnpj("112223330001")
CNPJ_HOSPITAL = make_cnpj("334445550001")
CNPJ_LAB = make_cnpj("219876540001")
CNS_MARIA = make_cns_definitivo("17033619550")
CNS_CARLOS = make_cns_definitivo("20456782310")
CNS_ANA = make_cns_provisorio("70012345678901")
CNS_JOSE = make_cns_provisorio("89876543210987")
CART_UNIMED = "0 049 912345678901 1"
CART_BRADESCO = "705049812345678"
CART_AMIL = "365498712"
CART_GENERICA = "0099 8877 6655 4433"


# --- Geradores do corpus -----------------------------------------------------


def gen_01_laudo_us_obstetrico() -> Page:
    p = Page()
    p.header_bar("Clinica Xdiag de Imagem", "CNPJ: {CNPJ?|" + CNPJ_CLINICA + "}")
    p.center("LAUDO DE ULTRASSONOGRAFIA OBSTETRICA", 150)
    p.center("Documento sintetico para teste, dados ficticios", 188, size=14, bold=False, color=(100, 116, 139))
    p.separator(230)
    p.at(80, 260)
    p.line("Paciente: {PATIENT_NAME|Maria Aparecida Pereira da Silva}", size=20, bold=True)
    p.line("CPF: {CPF|" + CPF_MARIA + "}                RG: {RG|12.345.678-9} SSP/SP")
    p.line("Data de nascimento: {DATE_OF_BIRTH|12/03/1991}                Idade: {AGE|34 anos}")
    p.line("Telefone: {PHONE|(11) 98765-4321}         Email: {EMAIL|maria.silva@example.com}")
    p.line("Endereco: {ADDRESS|Rua das Acacias, 245, apto 72, Vila Mariana, Sao Paulo, SP}, CEP {CEP|04101-000}")
    p.line("Convenio: Saude Plena            Carteirinha: {CARTEIRINHA|" + CART_GENERICA + "}")
    p.line("Data do exame: {DATE?|15/04/2026}                     Idade gestacional: 22 semanas e 4 dias")
    p.gap(18)
    p.separator()
    p.gap(18)
    p.line("EXAME REALIZADO", size=18, bold=True, color=(15, 23, 42))
    p.gap(4)
    for t in [
        "Realizada ultrassonografia obstetrica por via abdominal, com transdutor convexo.",
        "Feto unico, em apresentacao cefalica, dorso a esquerda materna.",
        "Batimentos cardiacos fetais presentes e ritmicos, com frequencia de 148 bpm.",
        "Movimentacao fetal ativa observada durante o exame.",
        "Placenta de insercao posterior, grau 1 de Grannum, sem sinais de descolamento.",
        "Liquido amniotico em quantidade normal (ILA estimado em 14 cm).",
        "Cordao umbilical com tres vasos (duas arterias e uma veia).",
    ]:
        p.line(t, size=16)
    p.gap(8)
    p.line("BIOMETRIA FETAL", size=18, bold=True, color=(15, 23, 42))
    p.line("DBP: 54 mm     CC: 198 mm     CA: 175 mm     CF: 38 mm", size=16)
    p.line("Peso fetal estimado: 540 gramas (percentil 52 para a idade gestacional).", size=16)
    p.gap(8)
    p.line("CONCLUSAO", size=18, bold=True, color=(15, 23, 42))
    p.line("Gestacao topica, unica, em evolucao normal para a idade gestacional referida.", size=16)
    p.gap(24)
    p.separator()
    p.gap(14)
    p.line("Medico responsavel: {DOCTOR_NAME|Dr. Joao Carlos Pereira}", size=18, bold=True)
    p.line("{CRM|CRM/SP 123456}                 {RQE|RQE 54321}")
    p.line("Telefone do consultorio: {PHONE|(11) 3000-1234}")
    p.line("Email: {EMAIL|joao.pereira@example.com}")
    p.line("Sao Paulo, {DATE?|15/04/2026}")
    p.watermark()
    return p


def gen_02_laudo_us_abdome() -> Page:
    p = Page()
    p.header_bar("Centro Diagnostico Xdiag", "CNES: {CNES?|2077485}")
    p.center("ULTRASSONOGRAFIA DE ABDOME TOTAL", 150)
    p.center("Documento sintetico para teste, dados ficticios", 188, size=14, bold=False, color=(100, 116, 139))
    p.separator(230)
    p.at(80, 262)
    p.line("Paciente: {PATIENT_NAME|Jose Roberto Nascimento Filho}", size=20, bold=True)
    p.line("CNS: {CNS|" + fmt_cns(CNS_JOSE) + "}        Prontuario: {PRONTUARIO|1049823}")
    p.line("Data de nascimento: {DATE_OF_BIRTH|02/09/1972}        Sexo: Masculino")
    p.line("Convenio: Vida Plena Saude")
    p.gap(16)
    p.separator()
    p.gap(16)
    p.line("ACHADOS", size=18, bold=True, color=(15, 23, 42))
    for t in [
        "Figado de dimensoes normais, contornos regulares, ecotextura homogenea.",
        "Lobo direito mede 132 mm; lobo esquerdo, 78 mm.",
        "Vesicula biliar normodistendida, paredes finas, sem calculos.",
        "Colédoco com calibre de 4,1 mm. Pancreas de aspecto habitual.",
        "Bacos com 98 mm no maior eixo. Rins topicos, com boa diferenciacao.",
        "Rim direito: 104 x 48 mm. Rim esquerdo: 108 x 51 mm.",
        "Aorta abdominal de calibre preservado (16 mm). Ausencia de liquido livre.",
    ]:
        p.line(t, size=16)
    p.gap(8)
    p.line("IMPRESSAO: exame dentro dos limites da normalidade.", size=16, bold=True)
    p.gap(28)
    p.separator()
    p.gap(14)
    p.line("Dra. {DOCTOR_NAME|Helena Castilho Braga}    {CRM|CRM/GO 45678}", size=18, bold=True)
    p.line("Assistente: {OTHER_NAME?|Tec. Marcos Vinicius Prado}")
    p.line("Goiania, {DATE?|03/05/2026}")
    p.watermark()
    return p


def gen_03_pedido_exame() -> Page:
    p = Page()
    p.header_bar("Consultorio Xdiag, Clinica Geral", "CNPJ: {CNPJ?|" + CNPJ_CLINICA + "}")
    p.center("PEDIDO DE EXAME / SOLICITACAO", 150)
    p.center("Documento sintetico para teste, dados ficticios", 188, size=14, bold=False, color=(100, 116, 139))
    p.separator(230)
    p.at(80, 262)
    p.line("Paciente: {PATIENT_NAME|Ana Beatriz Rodrigues Lima}", size=20, bold=True)
    p.line("CNS: {CNS|" + fmt_cns(CNS_ANA) + "}      Data de nascimento: {DATE_OF_BIRTH|30/11/1979}")
    p.line("Convenio: Amil            Carteirinha: {CARTEIRINHA|" + CART_AMIL + "}")
    p.gap(14)
    p.separator()
    p.gap(16)
    p.line("HIPOTESE DIAGNOSTICA", size=18, bold=True, color=(15, 23, 42))
    p.line("Nefrolitiase. CID-10: N20.0", size=16)
    p.gap(10)
    p.line("EXAMES SOLICITADOS", size=18, bold=True, color=(15, 23, 42))
    for t in [
        "1. Ultrassonografia de rins e vias urinarias",
        "2. Urina tipo I (EAS)",
        "3. Creatinina serica",
        "4. Acido urico serico",
    ]:
        p.line(t, size=17)
    p.gap(10)
    p.line("Observacoes: paciente em uso de losartana 50 mg. Jejum nao necessario.", size=16)
    p.gap(60)
    p.separator()
    p.gap(14)
    p.line("Solicitante: {DOCTOR_NAME|Dr. Rafael Antunes Sobrinho}", size=18, bold=True)
    p.line("{CRM|CRM 87654 GO}")
    p.line("Goiania, {DATE?|18/05/2026}")
    p.watermark()
    return p


def gen_04_guia_tiss_sadt() -> Page:
    p = Page()
    p.draw.rectangle([(0, 0), (WIDTH, 90)], fill=(30, 41, 59))
    p.text_at(80, 22, "GUIA DE SERVICO PROFISSIONAL / SERVICO AUXILIAR DE", size=22, bold=True, color=(248, 250, 252))
    p.text_at(80, 52, "DIAGNOSTICO E TERAPIA - SP/SADT (sintetica)", size=22, bold=True, color=(248, 250, 252))
    p.at(80, 120)
    p.line_height = 30
    p.line("1 - Registro ANS: {NUMERO?|123456}          2 - No da guia no prestador: {GUIA_NUM|20260415000123}")
    p.line("3 - Numero da guia principal: {GUIA_NUM|20260401000098}")
    p.gap(6)
    p.separator()
    p.gap(10)
    p.line("4 - Data da autorizacao: {DATE?|10/04/2026}     5 - Senha: {SENHA_AUT|784512}     6 - Validade: {DATE?|10/05/2026}")
    p.gap(6)
    p.separator()
    p.gap(10)
    p.line("DADOS DO BENEFICIARIO", size=18, bold=True, color=(15, 23, 42))
    p.line("8 - Numero da carteira: {CARTEIRINHA|" + CART_UNIMED + "}   (Unimed)")
    p.line("10 - Nome: {PATIENT_NAME|CARLOS EDUARDO MARQUES DE OLIVEIRA}", bold=True)
    p.line("11 - Cartao Nacional de Saude: {CNS|" + CNS_CARLOS + "}")
    p.gap(6)
    p.separator()
    p.gap(10)
    p.line("DADOS DO SOLICITANTE", size=18, bold=True, color=(15, 23, 42))
    p.line("13 - Codigo na operadora: {NUMERO|0045781}    14 - Nome do contratado: Clinica Xdiag")
    p.line("15 - Nome do profissional solicitante: {DOCTOR_NAME|PATRICIA SOUZA LIMA}", bold=True)
    p.line("16 - Conselho: CRM   17 - Numero no conselho: {CRM|098765}   18 - UF: RJ")
    p.gap(6)
    p.separator()
    p.gap(10)
    p.line("DADOS DO EXECUTANTE", size=18, bold=True, color=(15, 23, 42))
    p.line("19 - Codigo CNES: {CNES|2077485}    20 - CNPJ executante: {CNPJ?|" + CNPJ_HOSPITAL + "}")
    p.gap(6)
    p.separator()
    p.gap(10)
    p.line("PROCEDIMENTOS SOLICITADOS", size=18, bold=True, color=(15, 23, 42))
    p.line("40901220  US abdome total            Qtde: 1    Valor: 98,00", size=16)
    p.line("40901130  US rins e vias urinarias   Qtde: 1    Valor: 86,50", size=16)
    p.gap(20)
    p.line("Assinatura do beneficiario: ______________________________", size=16)
    p.gap(8)
    p.line("Data de emissao: {DATE?|15/04/2026}", size=16)
    p.watermark()
    return p


def gen_05_hemograma() -> Page:
    p = Page()
    p.header_bar("Laboratorio Xdiag Analises Clinicas", "CNPJ: {CNPJ?|" + CNPJ_LAB + "}")
    p.center("HEMOGRAMA COMPLETO", 150)
    p.center("Documento sintetico para teste, dados ficticios", 188, size=14, bold=False, color=(100, 116, 139))
    p.separator(230)
    p.at(80, 262)
    p.line("Paciente: {PATIENT_NAME|Tereza Cristina Fontes Amaral}    Registro: {ATENDIMENTO|20261578}", bold=True)
    p.line("Data de nascimento: {DATE_OF_BIRTH|22/01/1958}    Coleta: {DATE?|29/04/2026} 07:41")
    p.line("Solicitante: {DOCTOR_NAME|Dr. Felipe Ramos Cardoso}  {CRM|CRM/SP 224466}")
    p.gap(16)
    p.separator()
    p.gap(16)
    p.line("SERIE VERMELHA                     Resultado          Valores de referencia", size=16, bold=True)
    for t in [
        "Hemacias                            4,62 milhoes/mm3   4,0 a 5,5",
        "Hemoglobina                         13,8 g/dL          12,0 a 16,0",
        "Hematocrito                         41,5 %             36,0 a 48,0",
        "VCM                                 89,8 fL            80,0 a 100,0",
        "HCM                                 29,9 pg            26,0 a 34,0",
        "CHCM                                33,3 g/dL          31,0 a 36,0",
        "RDW                                 12,9 %             11,0 a 16,0",
    ]:
        p.line(t, size=15, mono=True, advance=24)
    p.gap(10)
    p.line("SERIE BRANCA", size=16, bold=True)
    for t in [
        "Leucocitos                          6.840 /mm3         4.000 a 11.000",
        "Neutrofilos                         58,2 %  3.981/mm3  40,0 a 70,0",
        "Linfocitos                          31,4 %  2.148/mm3  20,0 a 45,0",
        "Monocitos                           7,1 %   486/mm3    2,0 a 10,0",
        "Eosinofilos                         2,8 %   192/mm3    1,0 a 5,0",
        "Basofilos                           0,5 %   34/mm3     0,0 a 2,0",
    ]:
        p.line(t, size=15, mono=True, advance=24)
    p.gap(10)
    p.line("PLAQUETAS                           268.000 /mm3       150.000 a 450.000", size=15, mono=True)
    p.gap(24)
    p.separator()
    p.gap(14)
    p.line("Responsavel tecnico: {OTHER_NAME|Dra. Livia Quintela Matos}  CRBM {NUMERO|11223}")
    p.watermark()
    return p


def gen_06_bioquimica_qr() -> Page:
    p = Page()
    p.header_bar("Laboratorio Xdiag Analises Clinicas", "CNPJ: {CNPJ?|" + CNPJ_LAB + "}")
    p.center("BIOQUIMICA SERICA", 150)
    p.center("Documento sintetico para teste, dados ficticios", 188, size=14, bold=False, color=(100, 116, 139))
    p.separator(230)
    p.at(80, 262)
    p.line("Paciente: {PATIENT_NAME|Ana Beatriz Rodrigues Lima}    Protocolo: {ATENDIMENTO|LAB-2026-88452}", bold=True)
    p.line("Data de nascimento: {DATE_OF_BIRTH|30/11/1979}    Coleta: {DATE?|02/05/2026} 08:02")
    p.gap(16)
    p.separator()
    p.gap(16)
    for t in [
        "Glicose em jejum                    92 mg/dL           70 a 99",
        "Creatinina                          0,84 mg/dL         0,50 a 1,10",
        "Ureia                               31 mg/dL           15 a 45",
        "Colesterol total                    187 mg/dL          inferior a 190",
        "HDL colesterol                      52 mg/dL           superior a 40",
        "LDL colesterol (calculado)          112 mg/dL          inferior a 130",
        "Triglicerides                       114 mg/dL          inferior a 150",
        "TGO (AST)                           24 U/L             ate 34",
        "TGP (ALT)                           27 U/L             ate 36",
    ]:
        p.line(t, size=15, mono=True, advance=24)
    p.gap(20)
    p.line("Confira a autenticidade do laudo pelo QR code ao lado.", size=14)
    p.paste_qr("PROTO:LAB-2026-88452;PAC:ANA BEATRIZ RODRIGUES LIMA", 950, 640, box_size=4)
    p.gap(40)
    p.separator()
    p.gap(14)
    p.line("Responsavel tecnico: {OTHER_NAME|Dra. Livia Quintela Matos}")
    p.watermark()
    return p


def gen_07_receituario() -> Page:
    p = Page()
    p.header_bar("Consultorio Xdiag, Clinica Medica", "CNPJ: {CNPJ?|" + make_cnpj("123456780001") + "}")
    p.center("RECEITUARIO MEDICO", 150)
    p.center("Documento sintetico para teste, dados ficticios", 188, size=14, bold=False, color=(100, 116, 139))
    p.separator(230)
    p.at(80, 260)
    p.line("Paciente: {PATIENT_NAME|Ana Beatriz Rodrigues Lima}", size=20, bold=True)
    p.line("CPF: {CPF|" + CPF_ANA + "}              Data de nascimento: {DATE_OF_BIRTH|30/11/1979} ({AGE|46 anos})")
    p.line("Telefone: {PHONE|(31) 99988-1122}        Email: {EMAIL|ana.lima@example.com}")
    p.line("Endereco: {ADDRESS|Rua das Palmeiras, 88, Funcionarios, Belo Horizonte, MG}")
    p.line("Convenio: Plano Saude Mais       Carteirinha: {CARTEIRINHA|0001 2233 4455 6677}")
    p.gap(8)
    p.separator()
    p.gap(14)
    p.line("PRESCRICAO", size=20, bold=True, color=(15, 23, 42))
    p.gap(4)
    for t in [
        "1. Losartana potassica 50 mg",
        "   Tomar 1 comprimido pela manha, em jejum, por 30 dias.",
        "",
        "2. Atorvastatina 20 mg",
        "   Tomar 1 comprimido a noite, apos o jantar, por 30 dias.",
        "",
        "3. Acido acetilsalicilico 100 mg",
        "   Tomar 1 comprimido apos o almoco, uso continuo.",
        "",
        "4. Omeprazol 20 mg",
        "   Tomar 1 capsula em jejum, por 14 dias.",
    ]:
        if t == "":
            p.gap(6)
            continue
        p.line(t, size=18)
    p.gap(16)
    p.line("Orientacoes: dieta hipossodica, atividade fisica regular,", size=16)
    p.line("retorno em 30 dias com exames laboratoriais.", size=16)
    p.gap(18)
    p.separator()
    p.gap(18)
    p.line("Belo Horizonte, {DATE?|28/04/2026}", size=18)
    p.gap(18)
    p.line("{DOCTOR_NAME|Dr. Roberto Mendes Carvalho}", size=20, bold=True)
    p.line("{CRM|CRM/MG 045678}                {RQE|RQE 78901}", size=16)
    p.line("Telefone: {PHONE|(31) 3221-5500}         Email: {EMAIL|roberto.mendes@example.com}", size=16)
    p.watermark()
    return p


def gen_08_receita_controle_especial() -> Page:
    p = Page()
    p.header_bar("Consultorio Xdiag, Clinica Medica", "Receituario de Controle Especial")
    p.center("RECEITUARIO DE CONTROLE ESPECIAL", 150)
    p.center("Primeira via: farmacia / Segunda via: paciente (sintetico)", 188, size=14, bold=False, color=(100, 116, 139))
    p.separator(230)
    p.at(80, 262)
    p.line("Receita No: {NUMERO|B2 0012345}", size=18, bold=True)
    p.gap(8)
    p.line("IDENTIFICACAO DO EMITENTE", size=17, bold=True, color=(15, 23, 42))
    p.line("Nome: {DOCTOR_NAME|Dra. Camila Furtado Reis}    {CRM|CRM/SP 187654}")
    p.line("Endereco: {ADDRESS?|Av. Paulista, 1000, cj 84, Sao Paulo, SP}")
    p.gap(10)
    p.separator()
    p.gap(12)
    p.line("Paciente: {PATIENT_NAME|Jose Roberto Nascimento Filho}", size=19, bold=True)
    p.line("Endereco: {ADDRESS|Rua Itapeva, 210, ap 52, Bela Vista, Sao Paulo, SP}")
    p.gap(14)
    p.line("Prescricao:", size=17, bold=True)
    p.line("1. Clonazepam 2 mg ................ 1 caixa", size=17)
    p.line("   Tomar 1 comprimido a noite, ao deitar, por 30 dias.", size=16)
    p.gap(30)
    x_left, x_right = 80, 660
    p.text_at(x_left, p.y, "IDENTIFICACAO DO COMPRADOR", size=15, bold=True)
    p.text_at(x_right, p.y, "IDENTIFICACAO DO FORNECEDOR", size=15, bold=True)
    p.gap(30)
    p.text_at(x_left, p.y, "Nome: {OTHER_NAME|Beatriz Marques de Oliveira}", size=15)
    p.text_at(x_right, p.y, "Farmacia: ______________________", size=15)
    p.gap(28)
    p.text_at(x_left, p.y, "RG: {RG|22.333.444-5} SSP/SP", size=15)
    p.text_at(x_right, p.y, "CNPJ: __________________________", size=15)
    p.gap(28)
    p.text_at(x_left, p.y, "Telefone: {PHONE|(11) 97654-3210}", size=15)
    p.text_at(x_right, p.y, "Data: ____/____/________", size=15)
    p.gap(28)
    p.text_at(x_left, p.y, "Endereco: {ADDRESS|Rua Aurora, 155, Santa Cecilia, Sao Paulo, SP}", size=15)
    p.gap(40)
    p.line("Sao Paulo, {DATE?|05/05/2026}", size=16)
    p.watermark()
    return p


def gen_09_etiqueta_hospitalar() -> Page:
    p = Page(width=600, height=300, bg=(252, 252, 250))
    p.at(20, 16)
    p.line_height = 26
    p.line("HOSPITAL SINTETICO XDIAG", size=16, bold=True)
    p.line("Paciente: {PATIENT_NAME|CARLOS EDUARDO M. DE OLIVEIRA}", size=15, bold=True)
    p.line("Pront: {PRONTUARIO|2026-004-887}  Atend: {ATENDIMENTO|778991}", size=14)
    p.line("Nasc: {DATE_OF_BIRTH|04/07/1968}  Leito: 302-B", size=14)
    p.paste_barcode("ATD778991^OLIVEIRA^CARLOS", 30, 140, target_w=420)
    p.watermark()
    return p


def gen_10_etiqueta_pulseira() -> Page:
    p = Page(width=700, height=200, bg=(252, 252, 250))
    p.at(20, 12)
    p.line_height = 24
    p.line("SANTA CASA SINTETICA", size=14, bold=True)
    p.line("Prontuario: {PRONTUARIO|887459}", size=14)
    p.paste_barcode("887459", 24, 70, target_w=380)
    p.watermark()
    return p


def gen_11_encaminhamento() -> Page:
    p = Page()
    p.header_bar("Consultorio Xdiag, Clinica Geral", "Encaminhamento medico")
    p.center("ENCAMINHAMENTO", 150)
    p.center("Documento sintetico para teste, dados ficticios", 188, size=14, bold=False, color=(100, 116, 139))
    p.separator(230)
    p.at(80, 270)
    p.line("Ao colega cardiologista,", size=18)
    p.gap(10)
    for t in [
        "Encaminho a paciente {PATIENT_NAME|Tereza Cristina Fontes Amaral}, {AGE|68 anos}, hipertensa",
        "de longa data e com dislipidemia em tratamento, que apresentou episodios",
        "de dor toracica atipica aos moderados esforcos nas ultimas tres semanas.",
        "Nega sincope. Em uso de losartana 50 mg/dia e atorvastatina 20 mg/dia.",
        "Eletrocardiograma de repouso sem alteracoes isquemicas agudas.",
        "Solicito avaliacao especializada e, a criterio, teste ergometrico.",
    ]:
        p.line(t, size=17)
    p.gap(14)
    p.line("Contato da paciente: {PHONE|(62) 98811-2233}", size=17)
    p.gap(40)
    p.line("Atenciosamente,", size=17)
    p.gap(24)
    p.line("{DOCTOR_NAME|Dr. Rafael Antunes Sobrinho}", size=19, bold=True)
    # Erro comum de OCR gravado literalmente no documento: CRM lido como CFM.
    p.line("{CRM|CFM 12345} - Goiania, GO", size=16)
    p.line("Goiania, {DATE?|21/05/2026}", size=16)
    p.watermark()
    return p


def _us_frame(strip_lines: list[str], caliper: str | None, name_span_line: int) -> Page:
    """Frame de ultrassom 1024x768: faixa preta com texto branco + leque."""
    p = Page(width=1024, height=768, bg=(2, 2, 2))
    strip_h = 64
    p.draw.rectangle([(0, 0), (1024, strip_h)], fill=(4, 4, 4))
    y = 8
    for i, tline in enumerate(strip_lines):
        p.text_at(16, y, tline, size=17, mono=True, color=(242, 242, 242))
        y += 24
    _paste_speckle_fan(p, apex=(512, strip_h + 26), depth=560, half_angle_deg=38)
    if caliper:
        p.text_at(430, 430, caliper, size=15, mono=True, color=(240, 240, 240))
    p.add_region("us_header", [0, 0, 1024, strip_h], None, "redact")
    p.watermark()
    return p


def gen_12_us_header() -> Page:
    return _us_frame(
        [
            "PAT: {PATIENT_NAME#hard|SILVA, MARIA APARECIDA}  ID: {PRONTUARIO#hard|2026-004-887}",
            "DOB: {DATE_OF_BIRTH#hard|12/03/1991}  GE LOGIQ P9  27/04/2026 14:32  TIs 0.2  MI 0.9",
        ],
        caliper=None,
        name_span_line=0,
    )


def gen_13_us_header_sem_prefixo() -> Page:
    return _us_frame(
        [
            "{PATIENT_NAME#hard|MARIA APARECIDA PEREIRA DA SILVA}   {DATE_OF_BIRTH#hard|12/03/1991}",
            "SAMSUNG HS40  28/04/2026 09:11  ABD GERAL  FR 22Hz  GN 48",
        ],
        caliper="RIM D  +DIST 4.5cm",
        name_span_line=0,
    )


def gen_14_ficha_admissao() -> Page:
    p = Page()
    p.header_bar("Hospital Sintetico Xdiag", "CNPJ: {CNPJ?|" + CNPJ_HOSPITAL + "}")
    p.center("FICHA DE ADMISSAO HOSPITALAR", 150)
    p.center("Documento sintetico para teste, dados ficticios", 188, size=14, bold=False, color=(100, 116, 139))
    p.separator(230)
    p.at(80, 260)
    p.line("Numero do prontuario: {PRONTUARIO|2026-004-887}       Atendimento: {ATENDIMENTO|778991}", size=18, bold=True)
    p.gap(6)
    p.line("DADOS DO PACIENTE", size=18, bold=True, color=(15, 23, 42))
    p.line("Nome: {PATIENT_NAME|Carlos Eduardo Marques de Oliveira}", size=18, bold=True)
    p.line("CPF: {CPF|" + CPF_CARLOS + "}              RG: {RG|22.333.444-5} SSP/RJ")
    p.line("Data de nascimento: {DATE_OF_BIRTH|04/07/1968}               Idade: {AGE|57 anos}")
    p.line("Sexo: Masculino                  Cor declarada: parda")
    p.line("Naturalidade: Niteroi, RJ        Nacionalidade: brasileira")
    p.line("Telefone: {PHONE|(21) 99876-5432}        Email: {EMAIL|carlos.marques@example.com}")
    p.line("Endereco: {ADDRESS|Av. Atlantica, 4567, ap 301, Copacabana, Rio de Janeiro, RJ}, CEP {CEP|22070-002}")
    p.gap(6)
    p.separator()
    p.gap(12)
    p.line("RESPONSAVEL / CONTATO DE EMERGENCIA", size=18, bold=True, color=(15, 23, 42))
    p.line("Nome: {OTHER_NAME|Beatriz Marques de Oliveira}          Parentesco: filha")
    p.line("Telefone: {PHONE|(21) 98123-4567}         CPF: {CPF|" + CPF_ANA + "}")
    p.gap(6)
    p.separator()
    p.gap(12)
    p.line("DADOS CLINICOS", size=18, bold=True, color=(15, 23, 42))
    p.line("Data de admissao: {DATE?|22/04/2026}  Hora: 14:35     Origem: Pronto Socorro", size=16)
    p.line("Queixa principal: dor toracica retroesternal de inicio ha 2 horas.", size=16)
    p.line("Pressao arterial: 150 x 90 mmHg     Frequencia cardiaca: 96 bpm", size=16)
    p.line("Saturacao: 96 por cento     Temperatura: 36.7 graus Celsius", size=16)
    p.line("Antecedentes: hipertensao, dislipidemia, ex tabagista.", size=16)
    p.line("Alergia conhecida: dipirona.", size=16)
    p.gap(6)
    p.separator()
    p.gap(12)
    p.line("EQUIPE", size=18, bold=True, color=(15, 23, 42))
    p.line("Medico admissor: {DOCTOR_NAME|Dra. Patricia Souza Lima}", size=18, bold=True)
    p.line("{CRM|CRM/RJ 098765}                Especialidade: Cardiologia")
    p.line("Enfermeira: {OTHER_NAME|Fernanda Castro}       {COREN|COREN/RJ 234567}")
    p.line("Email do plantao: {EMAIL|plantao.cardio@example.com}")
    p.gap(16)
    p.line("Rio de Janeiro, {DATE?|22/04/2026}", size=16)
    p.watermark()
    return p


def gen_15_guia_tiss_consulta() -> Page:
    p = Page()
    p.draw.rectangle([(0, 0), (WIDTH, 90)], fill=(30, 41, 59))
    p.text_at(80, 30, "GUIA DE CONSULTA (sintetica)", size=24, bold=True, color=(248, 250, 252))
    p.at(80, 120)
    p.line_height = 30
    p.line("1 - Registro ANS: {NUMERO?|417173}       2 - No da guia: {GUIA_NUM|2026050700455}")
    p.gap(6)
    p.separator()
    p.gap(10)
    p.line("DADOS DO BENEFICIARIO", size=18, bold=True, color=(15, 23, 42))
    p.line("4 - Numero da carteira: {CARTEIRINHA|" + CART_BRADESCO + "}   (Bradesco Saude)")
    p.line("6 - Nome: {PATIENT_NAME|TEREZA CRISTINA FONTES AMARAL}", bold=True)
    p.line("7 - Cartao Nacional de Saude: {CNS|" + CNS_MARIA + "}")
    p.gap(6)
    p.separator()
    p.gap(10)
    p.line("DADOS DO CONTRATADO", size=18, bold=True, color=(15, 23, 42))
    p.line("9 - Codigo na operadora: {NUMERO|00812377}   10 - Nome: Centro Clinico Xdiag")
    p.line("11 - Codigo CNES: {CNES|7361442}")
    p.gap(6)
    p.separator()
    p.gap(10)
    p.line("DADOS DO ATENDIMENTO", size=18, bold=True, color=(15, 23, 42))
    p.line("13 - Data do atendimento: {DATE?|07/05/2026}    14 - Tipo de consulta: primeira")
    p.line("15 - Profissional executante: {DOCTOR_NAME|FELIPE RAMOS CARDOSO}", bold=True)
    p.line("16 - Conselho: CRM    17 - Numero: {CRM|224466}    18 - UF: SP    19 - CBO: 225120")
    p.gap(30)
    p.line("Assinatura do profissional executante: ______________________________", size=16)
    p.watermark()
    return p


def gen_16_laudo_rx() -> Page:
    p = Page()
    p.header_bar("Centro de Imagem Xdiag", "CNES: {CNES?|7361442}")
    p.center("RADIOGRAFIA DE TORAX (PA E PERFIL)", 150)
    p.center("Documento sintetico para teste, dados ficticios", 188, size=14, bold=False, color=(100, 116, 139))
    p.separator(230)
    p.at(80, 262)
    p.line("Paciente: {PATIENT_NAME|Jose Roberto Nascimento Filho}", size=20, bold=True)
    # Prontuario sem rotulo, logo abaixo do nome: caso dificil deliberado.
    p.line("{PRONTUARIO#hard|887459}", size=16)
    p.line("Data de nascimento: {DATE_OF_BIRTH|02/09/1972}      Exame: {DATE?|11/05/2026}")
    p.gap(16)
    p.separator()
    p.gap(16)
    p.line("RELATORIO", size=18, bold=True, color=(15, 23, 42))
    for t in [
        "Campos pulmonares com transparencia preservada, sem consolidacoes.",
        "Seios costofrenicos livres. Silhueta cardiaca dentro dos limites.",
        "Indice cardiotoracico estimado em 0,48.",
        "Arcabouco osseo sem lesoes evidentes.",
    ]:
        p.line(t, size=16)
    p.gap(8)
    p.line("IMPRESSAO: estudo radiografico do torax sem alteracoes agudas.", size=16, bold=True)
    p.gap(30)
    p.separator()
    p.gap(14)
    p.line("{DOCTOR_NAME|Dra. Helena Castilho Braga}    {CRM|CRM/GO 45678}", size=18, bold=True)
    p.line("Tecnologo em radiologia: {OTHER_NAME|Paulo Sergio Andrade}")
    p.watermark()
    return p


def gen_17_receituario_assinado(rng: random.Random) -> Page:
    p = Page()
    p.header_bar("Consultorio Xdiag, Clinica Medica", "Receituario simples")
    p.center("RECEITUARIO", 150)
    p.center("Documento sintetico para teste, dados ficticios", 188, size=14, bold=False, color=(100, 116, 139))
    p.separator(230)
    p.at(80, 262)
    p.line("Paciente: {PATIENT_NAME|Maria Aparecida Pereira da Silva}", size=20, bold=True)
    p.line("CPF: {CPF|" + CPF_MARIA + "}")
    p.gap(14)
    p.line("Uso oral:", size=17, bold=True)
    p.line("1. Nitrofurantoina 100 mg", size=18)
    p.line("   Tomar 1 capsula de 6 em 6 horas, por 7 dias.", size=16)
    p.line("2. Dipirona 500 mg", size=18)
    p.line("   Tomar 1 comprimido se dor, ate 4 vezes ao dia.", size=16)
    p.gap(280)
    sig_y = p.y
    p.draw_signature(430, sig_y, 360, 110, rng)
    p.gap(120)
    p.draw.line([(400, p.y), (830, p.y)], fill=(30, 30, 30), width=2)
    p.gap(10)
    p.text_at(430, p.y, "{DOCTOR_NAME|Dr. Joao Carlos Pereira}", size=18, bold=True)
    p.gap(28)
    p.text_at(430, p.y, "{CRM|CRM/SP 123456}", size=16)
    p.gap(28)
    p.text_at(430, p.y, "Sao Paulo, {DATE?|12/05/2026}", size=16)
    p.watermark()
    return p


def gen_18_pdf_guia_2pag() -> list[Page]:
    p1 = Page()
    p1.draw.rectangle([(0, 0), (WIDTH, 90)], fill=(30, 41, 59))
    p1.text_at(80, 30, "GUIA SP/SADT (sintetica) - pagina 1 de 2", size=24, bold=True, color=(248, 250, 252))
    p1.at(80, 130)
    p1.line_height = 32
    p1.line("No da guia no prestador: {GUIA_NUM|20260601000777}")
    p1.line("Senha de autorizacao: {SENHA_AUT|G91X44}      Validade: {DATE?|30/06/2026}")
    p1.gap(8)
    p1.separator()
    p1.gap(12)
    p1.line("BENEFICIARIO", size=18, bold=True, color=(15, 23, 42))
    p1.line("Nome: {PATIENT_NAME|JOSE ROBERTO NASCIMENTO FILHO}", bold=True)
    p1.line("CNS: {CNS|" + CNS_JOSE + "}      Nascimento: {DATE_OF_BIRTH|02/09/1972}")
    p1.line("Carteira: {CARTEIRINHA|" + CART_UNIMED + "}  (Unimed)")
    p1.gap(8)
    p1.separator()
    p1.gap(12)
    p1.line("PROCEDIMENTOS", size=18, bold=True, color=(15, 23, 42))
    p1.line("40808012  RM coluna lombar     Qtde: 1", size=16)
    p1.line("Indicacao clinica: lombociatalgia refrataria ha 6 semanas.", size=16)
    p1.line("(continua na pagina 2)", size=14, color=(100, 116, 139))
    p1.watermark()

    p2 = Page()
    p2.draw.rectangle([(0, 0), (WIDTH, 90)], fill=(30, 41, 59))
    p2.text_at(80, 30, "GUIA SP/SADT (sintetica) - pagina 2 de 2", size=24, bold=True, color=(248, 250, 252))
    p2.at(80, 130)
    p2.line_height = 32
    p2.line("SOLICITANTE", size=18, bold=True, color=(15, 23, 42))
    p2.line("Profissional: {DOCTOR_NAME|HELENA CASTILHO BRAGA}", bold=True)
    p2.line("Conselho: CRM   Numero: {CRM|45678}   UF: GO")
    p2.gap(8)
    p2.separator()
    p2.gap(12)
    p2.line("EXECUTANTE", size=18, bold=True, color=(15, 23, 42))
    p2.line("Codigo CNES: {CNES|2077485}     Contratado: Centro Diagnostico Xdiag")
    p2.line("Contato: {PHONE|(62) 3225-8899}")
    p2.gap(30)
    p2.line("Data de emissao: {DATE?|01/06/2026}", size=16)
    p2.gap(40)
    p2.line("Assinatura do beneficiario: ______________________________", size=16)
    p2.watermark()
    return [p1, p2]


# --- Main --------------------------------------------------------------------


def write_corpus() -> None:
    rng = random.Random(SEED)
    print(f"Gerando corpus em {CORPUS_DIR}")
    gen_01_laudo_us_obstetrico().save_png(CORPUS_DIR, "laudo_us_obstetrico_01", "laudo_us")
    gen_02_laudo_us_abdome().save_png(CORPUS_DIR, "laudo_us_abdome_02", "laudo_us")
    gen_03_pedido_exame().save_png(CORPUS_DIR, "pedido_exame_03", "pedido_exame")
    gen_04_guia_tiss_sadt().save_png(CORPUS_DIR, "guia_tiss_sadt_04", "guia_tiss")
    gen_05_hemograma().save_png(CORPUS_DIR, "resultado_lab_hemograma_05", "resultado_lab")
    gen_06_bioquimica_qr().save_png(CORPUS_DIR, "resultado_lab_bioquimica_06", "resultado_lab")
    gen_07_receituario().save_png(CORPUS_DIR, "receituario_07", "receituario")
    gen_08_receita_controle_especial().save_png(CORPUS_DIR, "receita_controle_especial_08", "receituario")
    gen_09_etiqueta_hospitalar().save_png(CORPUS_DIR, "etiqueta_hospitalar_09", "etiqueta")
    gen_10_etiqueta_pulseira().save_png(CORPUS_DIR, "etiqueta_pulseira_10", "etiqueta")
    gen_11_encaminhamento().save_png(CORPUS_DIR, "encaminhamento_11", "encaminhamento")
    gen_12_us_header().save_png(CORPUS_DIR, "us_header_burn_12", "us_frame")
    gen_13_us_header_sem_prefixo().save_png(CORPUS_DIR, "us_header_burn_13", "us_frame")
    gen_14_ficha_admissao().save_png(CORPUS_DIR, "ficha_admissao_14", "ficha_admissao")
    gen_15_guia_tiss_consulta().save_png(CORPUS_DIR, "guia_tiss_consulta_15", "guia_tiss")
    gen_16_laudo_rx().save_png(CORPUS_DIR, "laudo_raio_x_16", "laudo_rx")
    gen_17_receituario_assinado(rng).save_png(CORPUS_DIR, "receituario_assinado_17", "receituario")
    save_pdf(gen_18_pdf_guia_2pag(), CORPUS_DIR, "guia_tiss_2pag_18", "guia_tiss_pdf")
    print("Corpus completo: 17 PNGs + 1 PDF + gabaritos JSON.")


def write_samples() -> None:
    print(f"Gerando samples de demonstracao em {SAMPLES_DIR}")
    gen_01_laudo_us_obstetrico().save_png(SAMPLES_DIR, "laudo_us_obstetrico", "laudo_us", gabarito=False)
    gen_14_ficha_admissao().save_png(SAMPLES_DIR, "ficha_admissao", "ficha_admissao", gabarito=False)
    gen_07_receituario().save_png(SAMPLES_DIR, "prescricao_medica", "receituario", gabarito=False)
    print("Samples atualizados.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", action="store_true", help="gera apenas tests/corpus/")
    ap.add_argument("--samples", action="store_true", help="gera apenas samples/")
    args = ap.parse_args()
    both = not args.corpus and not args.samples
    if args.corpus or both:
        write_corpus()
    if args.samples or both:
        write_samples()
    return 0


if __name__ == "__main__":
    sys.exit(main())
