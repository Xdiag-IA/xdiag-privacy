"""PaddleOCR wrapper.

Responsibilities:
1. Lazy load PaddleOCR with the configured language and device.
2. Decode the raw bytes (PNG, JPG, PDF first page) into a numpy ndarray.
3. Run detection plus recognition.
4. Build a continuous text stream where every character knows which OCR line
   it came from. This offset map is what makes mapping PII spans back to image
   space possible without re tokenizing.

When XDIAG_MOCK is set, the wrapper returns a synthetic page so the rest of
the pipeline can be exercised without downloading the models.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from threading import Lock
from typing import Any

import numpy as np
from PIL import Image

from .config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class OCRLine:
    """Single OCR line with its quadrilateral bbox and offset into the stream."""

    text: str
    bbox: list[list[float]]
    confidence: float
    char_start: int
    char_end: int  # exclusive

    def length(self) -> int:
        return self.char_end - self.char_start


@dataclass
class OCRResult:
    width: int
    height: int
    lines: list[OCRLine]
    text: str  # deidentified candidate, joined by newline
    image_png: bytes = b""  # canonical PNG bytes of the page actually OCRd


class OCREngine:
    """Thread safe wrapper around PaddleOCR.

    The PaddleOCR object itself is not strictly thread safe across requests
    because it caches intermediate tensors, so we serialize calls with a lock.
    This is fine for the demo workload (one document at a time).
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._engine: Any | None = None
        self._lock = Lock()
        self._loaded = False

    @property
    def loaded(self) -> bool:
        return self._loaded or self.settings.mock_mode

    def warmup(self) -> None:
        if self.settings.mock_mode:
            self._loaded = True
            logger.info("OCR engine running in mock mode")
            return
        with self._lock:
            if self._engine is not None:
                return
            from paddleocr import PaddleOCR  # imported lazily to keep CLI snappy

            logger.info(
                "Loading PaddleOCR (lang=%s, gpu=%s)",
                self.settings.ocr_lang,
                self.settings.ocr_use_gpu,
            )
            self._engine = PaddleOCR(
                use_angle_cls=self.settings.ocr_use_angle_cls,
                lang=self.settings.ocr_lang,
                use_gpu=self.settings.ocr_use_gpu,
                show_log=False,
                det_db_box_thresh=self.settings.ocr_det_db_box_thresh,
            )
            self._loaded = True
            logger.info("PaddleOCR loaded")

    def run(self, image_bytes: bytes, mimetype: str) -> OCRResult:
        image = self._decode(image_bytes, mimetype)
        # Re encode to a canonical PNG once so callers (and the frontend)
        # can render exactly what OCR saw, regardless of input format
        # (PDFs become PNGs, JPGs become PNGs, etc.). The bbox coordinates
        # in OCRLine are in this image's pixel space.
        png_buf = io.BytesIO()
        image.save(png_buf, format="PNG", optimize=False)
        canonical_png = png_buf.getvalue()

        if self.settings.mock_mode:
            res = self._mock_result(image.width, image.height)
            res.image_png = canonical_png
            return res

        if self._engine is None:
            self.warmup()
        assert self._engine is not None  # for type checkers

        np_img = np.array(image)
        with self._lock:
            raw = self._engine.ocr(np_img, cls=self.settings.ocr_use_angle_cls)
        lines = self._normalize_paddle_output(raw)
        result = self._build_result(image.width, image.height, lines)
        result.image_png = canonical_png
        return result

    @staticmethod
    def _decode(image_bytes: bytes, mimetype: str) -> Image.Image:
        if mimetype == "application/pdf":
            return _decode_pdf_first_page(image_bytes)
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img.load()
        except Exception as exc:  # pragma: no cover (depends on file)
            raise ValueError(f"could not decode image: {exc}") from exc
        if img.mode != "RGB":
            img = img.convert("RGB")
        return img

    @staticmethod
    def _normalize_paddle_output(raw: Any) -> list[tuple[list[list[float]], str, float]]:
        """Map PaddleOCR's nested output to a flat list of (bbox, text, score).

        PaddleOCR returns either a list of pages (newer versions) or directly
        a list of detections (older versions). Handle both.
        """
        if not raw:
            return []
        # Newer versions wrap in a per page list
        if isinstance(raw[0], list) and raw[0] and isinstance(raw[0][0], list):
            page = raw[0]
        else:
            page = raw
        out: list[tuple[list[list[float]], str, float]] = []
        for det in page:
            if not det:
                continue
            try:
                bbox, recog = det[0], det[1]
                text, score = recog[0], float(recog[1])
                bbox_norm = [[float(p[0]), float(p[1])] for p in bbox]
                out.append((bbox_norm, text, score))
            except (TypeError, IndexError, ValueError):
                continue
        return out

    @staticmethod
    def _build_result(
        width: int,
        height: int,
        raw_lines: list[tuple[list[list[float]], str, float]],
    ) -> OCRResult:
        # Sort top to bottom, then left to right, by bbox first vertex.
        raw_lines.sort(key=lambda r: (round(r[0][0][1] / 8) * 8, r[0][0][0]))
        lines: list[OCRLine] = []
        cursor = 0
        text_parts: list[str] = []
        for bbox, txt, score in raw_lines:
            if not txt:
                continue
            start = cursor
            end = cursor + len(txt)
            lines.append(
                OCRLine(text=txt, bbox=bbox, confidence=score, char_start=start, char_end=end)
            )
            text_parts.append(txt)
            cursor = end + 1  # account for the newline separator
        text = "\n".join(text_parts)
        return OCRResult(width=width, height=height, lines=lines, text=text)

    @staticmethod
    def _mock_result(width: int, height: int) -> OCRResult:
        """Synthesize a deterministic OCR layout to validate the pipeline."""
        canonical_lines = [
            "CLINICA XDIAG SYNTHETIC",
            "Paciente: Maria Aparecida da Silva",
            "CPF: 529.982.247-25  RG: 12.345.678-9",
            "Data de nascimento: 12/03/1984  Idade: 41 anos",
            "Telefone: (11) 98765-4321  Email: maria.silva@example.com",
            "Endereco: Rua das Flores, 123, Sao Paulo, SP",
            "Medico responsavel: Dr. Joao Pereira  CRM/SP 123456",
            "Data do exame: 15/04/2026",
            "Conclusao: gestacao unica, topica, em evolucao normal.",
        ]
        # synth bboxes evenly spaced
        margin_x, margin_y = 80.0, 80.0
        line_h = (height - 2 * margin_y) / max(len(canonical_lines), 1)
        text_w = width - 2 * margin_x
        lines: list[OCRLine] = []
        cursor = 0
        text_parts: list[str] = []
        for idx, line_text in enumerate(canonical_lines):
            y1 = margin_y + idx * line_h
            y2 = y1 + line_h * 0.7
            x1 = margin_x
            # estimate width by char count, capped to text_w
            est_w = min(text_w, len(line_text) * 11.0)
            x2 = x1 + est_w
            bbox = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
            lines.append(
                OCRLine(
                    text=line_text,
                    bbox=bbox,
                    confidence=0.99,
                    char_start=cursor,
                    char_end=cursor + len(line_text),
                )
            )
            text_parts.append(line_text)
            cursor += len(line_text) + 1
        return OCRResult(width=width, height=height, lines=lines, text="\n".join(text_parts))


def _decode_pdf_first_page(pdf_bytes: bytes) -> Image.Image:
    """Render page 1 of a PDF using pypdfium2 (no native deps required)."""
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "PDF support requires pypdfium2; install with pip install pypdfium2"
        ) from exc
    doc = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
    if len(doc) == 0:
        raise ValueError("PDF contains no pages")
    page = doc[0]
    pil = page.render(scale=2).to_pil()  # 2x for higher OCR fidelity
    if pil.mode != "RGB":
        pil = pil.convert("RGB")
    return pil


_engine_singleton: OCREngine | None = None


def get_engine() -> OCREngine:
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = OCREngine()
    return _engine_singleton
