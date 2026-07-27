"""Pydantic schemas exchanged with the frontend.

These are the single source of truth for the API contract. Field names match
the JSON shape documented in the spec. Keep this file aligned with the
frontend types in frontend/src/api/types.ts.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# A bbox is a quadrilateral: 4 vertices, each (x, y), in image pixel space.
# Order: top-left, top-right, bottom-right, bottom-left.
BBox = list[list[float]]


class ImageDimensions(BaseModel):
    w: int
    h: int


class OCRBlock(BaseModel):
    """One line detected by PaddleOCR with its quadrilateral bbox."""

    text: str
    bbox: BBox
    confidence: float
    char_start: int = Field(..., description="Inclusive char offset in deidentified_text")
    char_end: int = Field(..., description="Exclusive char offset in deidentified_text")


class Entity(BaseModel):
    """A PII span detected by the model, mapped to image space."""

    label: str
    text: str
    score: float
    char_span: tuple[int, int]
    bboxes: list[BBox]
    redacted: str
    unmapped: bool = Field(
        default=False,
        description=(
            "True when the span exists in the text but no image region could "
            "be mapped. The frontend must block export until resolved."
        ),
    )


class Stats(BaseModel):
    total_entities: int
    by_label: dict[str, int]
    unmapped: int = 0


class PageResult(BaseModel):
    """Resultado completo de UMA pagina do documento."""

    page_index: int
    image_dimensions: ImageDimensions
    ocr_blocks: list[OCRBlock]
    entities: list[Entity]
    deidentified_text: str
    original_text: Optional[str] = Field(
        default=None,
        description="Only populated when reveal=true, controlled at API layer.",
    )
    rendered_image_data_url: str = Field(
        default="",
        description=(
            "data:image/png;base64,... of the page actually OCRd. The frontend "
            "should display this image so bboxes align (handles PDF->PNG)."
        ),
    )


class RedactResponse(BaseModel):
    pages: list[PageResult]
    page_count: int
    stats: Stats
    is_synthetic: bool = False
    elapsed_ms: int = 0


class HealthResponse(BaseModel):
    status: str
    ocr: str
    pii: str
    device: str
    version: str
    mock_mode: bool


class LabelInfo(BaseModel):
    label: str
    color: str
    description: str = ""
    placeholder: str


class LabelsResponse(BaseModel):
    labels: list[LabelInfo]


class ErrorResponse(BaseModel):
    error: str
    detail: str = ""
