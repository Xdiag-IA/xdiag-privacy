"""Runtime configuration for the Xdiag Privacy backend.

All settings are environment driven so the same image runs on CPU dev boxes,
GPU servers, and CI without code changes. Defaults are tuned for the local
first demo (CPU, conservative thresholds, mock mode off).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


def _bool(val: str | None, default: bool = False) -> bool:
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on", "y", "t"}


def _int(val: str | None, default: int) -> int:
    try:
        return int(val) if val is not None else default
    except ValueError:
        return default


def _float(val: str | None, default: float) -> float:
    try:
        return float(val) if val is not None else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Process wide configuration."""

    app_name: str = "Xdiag Privacy"
    app_version: str = "0.1.0"

    # Networking
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: ("http://localhost:5173", "http://localhost:4173", "http://web:5173")
    )
    cors_origin_regex: str = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

    # OCR
    ocr_lang: str = "pt"
    ocr_use_angle_cls: bool = True
    ocr_use_gpu: bool = False
    ocr_det_db_box_thresh: float = 0.5

    # PII model
    pii_model: str = "OpenMed/OpenMed-PII-Portuguese-SnowflakeMed-Large-568M-v1"
    pii_device: int = -1  # transformers convention, negative means CPU
    pii_aggregation: str = "simple"
    pii_max_input_chars: int = 8000  # safe ceiling per chunk

    # Pipeline
    confidence_default: float = 0.5
    max_upload_bytes: int = 20 * 1024 * 1024  # 20MB

    # Storage
    samples_dir: Path = field(default_factory=lambda: Path("/app/samples"))
    cache_dir: Path = field(default_factory=lambda: Path("/app/.cache"))

    # Behavior toggles
    mock_mode: bool = False  # if true, synthesize OCR + PII without loading models
    eager_load: bool = True  # warm models on startup; set false for faster dev reloads

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            host=os.getenv("XDIAG_HOST", "0.0.0.0"),
            port=_int(os.getenv("XDIAG_PORT"), 8000),
            cors_origins=tuple(
                o.strip()
                for o in os.getenv(
                    "XDIAG_CORS_ORIGINS",
                    "http://localhost:5173,http://localhost:4173,http://web:5173",
                ).split(",")
                if o.strip()
            ),
            cors_origin_regex=os.getenv(
                "XDIAG_CORS_ORIGIN_REGEX",
                r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
            ),
            ocr_lang=os.getenv("XDIAG_OCR_LANG", "pt"),
            ocr_use_angle_cls=_bool(os.getenv("XDIAG_OCR_USE_ANGLE_CLS"), True),
            ocr_use_gpu=_bool(os.getenv("XDIAG_OCR_USE_GPU"), False),
            ocr_det_db_box_thresh=_float(os.getenv("XDIAG_OCR_DET_THRESH"), 0.5),
            pii_model=os.getenv(
                "XDIAG_PII_MODEL",
                "OpenMed/OpenMed-PII-Portuguese-SnowflakeMed-Large-568M-v1",
            ),
            pii_device=_int(os.getenv("XDIAG_PII_DEVICE"), -1),
            pii_aggregation=os.getenv("XDIAG_PII_AGGREGATION", "simple"),
            pii_max_input_chars=_int(os.getenv("XDIAG_PII_MAX_CHARS"), 8000),
            confidence_default=_float(os.getenv("XDIAG_CONFIDENCE"), 0.5),
            max_upload_bytes=_int(os.getenv("XDIAG_MAX_UPLOAD"), 20 * 1024 * 1024),
            samples_dir=Path(os.getenv("XDIAG_SAMPLES_DIR", "/app/samples")),
            cache_dir=Path(os.getenv("XDIAG_CACHE_DIR", "/app/.cache")),
            mock_mode=_bool(os.getenv("XDIAG_MOCK"), False),
            eager_load=_bool(os.getenv("XDIAG_EAGER_LOAD"), True),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
