"""FastAPI entrypoint for Xdiag Privacy.

Exposes three endpoints:
  GET  /api/health   liveness plus model load status
  GET  /api/labels   supported PII labels with display colors
  POST /api/redact   run the OCR plus PII pipeline on an uploaded document

The app is intentionally stateless. There is no persistence layer; the
upload is read into memory, processed, and the response is returned. This
matches the local first deployment model where the user controls retention.
"""

from __future__ import annotations

import base64
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import ocr as ocr_mod
from . import pii as pii_mod
from .config import get_settings
from .mapper import build_entities, build_ocr_blocks, deidentify_text, stats_by_label
from .models import (
    HealthResponse,
    ImageDimensions,
    LabelInfo,
    LabelsResponse,
    PageResult,
    RedactResponse,
    Stats,
)
from .ocr import PageLimitExceeded

logger = logging.getLogger("xdiag.redact")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


ALLOWED_MIME = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "application/pdf",
}


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if settings.eager_load:
        logger.info("eager loading models on startup (mock_mode=%s)", settings.mock_mode)
        ocr_mod.get_engine().warmup()
        pii_mod.get_engine().warmup()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Local first PII redaction for Brazilian medical documents. "
            "All inference runs inside this container."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_origin_regex=settings.cors_origin_regex or None,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # Serve the synthetic samples folder as static so the web frontend can
    # download canned documents on demand without bundling them.
    if settings.samples_dir.exists():
        app.mount(
            "/samples",
            StaticFiles(directory=str(settings.samples_dir)),
            name="samples",
        )

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        ocr_engine = ocr_mod.get_engine()
        pii_engine = pii_mod.get_engine()
        device = "gpu" if settings.ocr_use_gpu else "cpu"
        return HealthResponse(
            status="ok",
            ocr="loaded" if ocr_engine.loaded else "pending",
            pii=pii_engine.backend if pii_engine.loaded else "pending",
            device=device,
            version=settings.app_version,
            mock_mode=settings.mock_mode,
        )

    @app.get("/api/labels", response_model=LabelsResponse)
    async def labels() -> LabelsResponse:
        return LabelsResponse(
            labels=[
                LabelInfo(label=l, color=c, placeholder=ph)
                for (l, c, ph) in pii_mod.supported_labels()
            ]
        )

    @app.post("/api/redact", response_model=RedactResponse)
    async def redact(
        file: UploadFile = File(...),
        reveal: bool = Query(False),
        threshold: float = Query(default=settings.confidence_default, ge=0.0, le=1.0),
        is_synthetic: bool = Query(False),
    ) -> RedactResponse:
        started = time.time()

        if file.content_type not in ALLOWED_MIME:
            raise HTTPException(
                status_code=415,
                detail=f"unsupported media type: {file.content_type}",
            )

        body = await file.read()
        if len(body) == 0:
            raise HTTPException(status_code=400, detail="empty upload")
        if len(body) > settings.max_upload_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"file too large (limit {settings.max_upload_bytes} bytes)",
            )

        ocr_engine = ocr_mod.get_engine()
        pii_engine = pii_mod.get_engine()

        try:
            ocr_results = ocr_engine.run(body, file.content_type or "image/png")
        except PageLimitExceeded as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("OCR failed")
            raise HTTPException(status_code=500, detail=f"OCR failure: {exc}") from exc

        pages: list[PageResult] = []
        all_entities = []
        for page_index, ocr_result in enumerate(ocr_results):
            try:
                pii_entities = pii_engine.detect(ocr_result.text, threshold=threshold)
            except Exception as exc:
                logger.exception("PII detection failed (page %d)", page_index)
                raise HTTPException(
                    status_code=500,
                    detail=f"PII failure na página {page_index + 1}: {exc}",
                ) from exc

            entities = build_entities(pii_entities, ocr_result.lines)
            all_entities.extend(entities)
            rendered_data_url = ""
            if ocr_result.image_png:
                rendered_data_url = (
                    "data:image/png;base64,"
                    + base64.b64encode(ocr_result.image_png).decode("ascii")
                )
            pages.append(
                PageResult(
                    page_index=page_index,
                    image_dimensions=ImageDimensions(
                        w=ocr_result.width, h=ocr_result.height
                    ),
                    ocr_blocks=build_ocr_blocks(ocr_result),
                    entities=entities,
                    deidentified_text=deidentify_text(ocr_result.text, pii_entities),
                    original_text=ocr_result.text if reveal else None,
                    rendered_image_data_url=rendered_data_url,
                )
            )

        elapsed = int((time.time() - started) * 1000)

        return RedactResponse(
            pages=pages,
            page_count=len(pages),
            stats=Stats(
                total_entities=len(all_entities),
                by_label=stats_by_label(all_entities),
                unmapped=sum(1 for e in all_entities if e.unmapped),
            ),
            is_synthetic=is_synthetic,
            elapsed_ms=elapsed,
        )

    @app.exception_handler(Exception)
    async def unhandled(_, exc: Exception):  # type: ignore[no-redef]
        logger.exception("unhandled error")
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "detail": str(exc)},
        )

    # O SPA e montado por ULTIMO, na raiz. StaticFiles em "/" captura tudo que
    # sobrar, entao qualquer rota registrada depois daqui ficaria inalcancavel.
    #
    # Isto so acontece no perfil desktop (XDIAG_WEB_DIR definido). Ali a
    # interface e a API passam a viver na MESMA origem, o que resolve duas
    # coisas de uma vez: acaba o CORS, e a janela do Electron carrega de
    # http://127.0.0.1:<porta> em vez de file://. A segunda importa mais do que
    # parece: file:// nao e contexto seguro, e sem contexto seguro a File
    # System Access API nao existe, ou seja, a pasta de saida configuravel
    # simplesmente nao funcionaria.
    if settings.web_dir is not None:
        if settings.web_dir.is_dir():
            app.mount(
                "/",
                StaticFiles(directory=str(settings.web_dir), html=True),
                name="web",
            )
            logger.info("serving SPA from %s", settings.web_dir)
        else:
            logger.warning(
                "XDIAG_WEB_DIR aponta para %s, que nao existe; SPA nao sera servido",
                settings.web_dir,
            )

    return app


app = create_app()
