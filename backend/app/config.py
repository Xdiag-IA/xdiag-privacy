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


def _path(val: str | None) -> Path | None:
    """Caminho opcional. String vazia conta como nao definido."""
    if val is None or not val.strip():
        return None
    return Path(val)


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

    # Motores. "paddle" + "model" e o perfil completo (desktop e Docker).
    # "tesseract" + "rules" e o perfil leve (xdiag-privacy-VPS): OCR por
    # Tesseract e deteccao so por regras brasileiras, sem modelo de PII.
    ocr_engine: str = "paddle"
    pii_engine: str = "model"
    # Binario do Tesseract e pasta dos idiomas (tessdata). Vazio usa o PATH
    # e o TESSDATA_PREFIX do sistema.
    tesseract_cmd: str = ""
    tessdata_dir: Path | None = None

    # Segunda camada de PII por LLM, so no perfil leve (pii_engine=rules).
    # Vazio = desligada. "claude" = Claude Code em modo -p. Manda o TEXTO do
    # documento a um servico externo: nunca liga por padrao.
    pii_llm: str = ""
    claude_cmd: str = ""
    llm_model: str = "claude-sonnet-5"
    llm_timeout_s: int = 120

    # PII model
    pii_model: str = "OpenMed/OpenMed-PII-Portuguese-SnowflakeMed-Large-568M-v1"
    pii_device: int = -1  # transformers convention, negative means CPU
    pii_aggregation: str = "simple"
    pii_max_input_chars: int = 8000  # safe ceiling per chunk

    # Segunda passada do modelo sobre linhas em CAIXA ALTA (Title Case).
    # Recupera nome de cabecalho DICOM, que o modelo perde por capitalizacao.
    caps_retry: bool = True

    # Mapeamento de span de caractere para bbox de pixel. A folga e
    # fail-closed: tarja de menos deixa letra visivel na imagem exportada,
    # tarja de mais so cobre um caractere vizinho.
    bbox_pad_chars: float = 0.6  # folga lateral, em larguras de caractere
    bbox_pad_lines: float = 0.08  # folga vertical, em fracao da altura da linha

    # Pipeline
    confidence_default: float = 0.5
    # Piso de coleta do modelo: tudo acima disso entra no pipeline e passa
    # por snap e validacao ANTES do corte pelo threshold do usuario.
    pii_score_floor: float = 0.15
    max_upload_bytes: int = 20 * 1024 * 1024  # 20MB
    # Limite de paginas de PDF: acima disso a API responde 422 explicito.
    # Nunca processar em silencio apenas parte do documento.
    max_pdf_pages: int = 20

    # Storage
    # Defaults relativos de proposito. Os absolutos antigos (/app/...) so
    # existiam dentro do container; no Windows, sem env, o backend escrevia em
    # lugar nenhum. Docker e o app de mesa definem os dois explicitamente.
    samples_dir: Path = field(default_factory=lambda: Path("samples"))
    cache_dir: Path = field(default_factory=lambda: Path(".cache"))
    # Diretorio dos modelos do PaddleOCR. Vazio deixa o PaddleOCR usar o
    # default dele, que e ~/.paddleocr: fora da pasta do aplicativo, sobrevive
    # a desinstalacao e quebra em perfil corporativo restrito. O perfil desktop
    # aponta para dentro da propria instalacao.
    ocr_model_dir: Path | None = None

    # Pasta do frontend ja compilado. Quando definida, o backend serve o SPA
    # na propria origem. E o que o app de mesa usa: origem unica mata o CORS e,
    # mais importante, mantem contexto seguro (file:// nao e), sem o qual a
    # File System Access API da pasta de saida nao funciona.
    web_dir: Path | None = None

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
            ocr_engine=os.getenv("XDIAG_OCR_ENGINE", "paddle").strip().lower(),
            pii_engine=os.getenv("XDIAG_PII_ENGINE", "model").strip().lower(),
            tesseract_cmd=os.getenv("XDIAG_TESSERACT_CMD", "").strip(),
            tessdata_dir=_path(os.getenv("XDIAG_TESSDATA_DIR")),
            pii_llm=os.getenv("XDIAG_PII_LLM", "").strip().lower(),
            claude_cmd=os.getenv("XDIAG_CLAUDE_CMD", "").strip(),
            llm_model=os.getenv("XDIAG_LLM_MODEL", "claude-sonnet-5").strip(),
            llm_timeout_s=_int(os.getenv("XDIAG_LLM_TIMEOUT"), 120),
            pii_model=os.getenv(
                "XDIAG_PII_MODEL",
                "OpenMed/OpenMed-PII-Portuguese-SnowflakeMed-Large-568M-v1",
            ),
            pii_device=_int(os.getenv("XDIAG_PII_DEVICE"), -1),
            pii_aggregation=os.getenv("XDIAG_PII_AGGREGATION", "simple"),
            pii_max_input_chars=_int(os.getenv("XDIAG_PII_MAX_CHARS"), 8000),
            caps_retry=_bool(os.getenv("XDIAG_CAPS_RETRY"), True),
            bbox_pad_chars=_float(os.getenv("XDIAG_BBOX_PAD_CHARS"), 0.6),
            bbox_pad_lines=_float(os.getenv("XDIAG_BBOX_PAD_LINES"), 0.08),
            confidence_default=_float(os.getenv("XDIAG_CONFIDENCE"), 0.5),
            pii_score_floor=_float(os.getenv("XDIAG_PII_SCORE_FLOOR"), 0.15),
            max_upload_bytes=_int(os.getenv("XDIAG_MAX_UPLOAD"), 20 * 1024 * 1024),
            max_pdf_pages=_int(os.getenv("XDIAG_MAX_PDF_PAGES"), 20),
            samples_dir=Path(os.getenv("XDIAG_SAMPLES_DIR", "samples")),
            cache_dir=Path(os.getenv("XDIAG_CACHE_DIR", ".cache")),
            ocr_model_dir=_path(os.getenv("XDIAG_OCR_MODEL_DIR")),
            web_dir=_path(os.getenv("XDIAG_WEB_DIR")),
            mock_mode=_bool(os.getenv("XDIAG_MOCK"), False),
            eager_load=_bool(os.getenv("XDIAG_EAGER_LOAD"), True),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
