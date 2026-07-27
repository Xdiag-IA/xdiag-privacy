# Backend image for Xdiag Privacy.
#
# Notes:
#  1. Uses the slim Python base, then layers system libs needed by PaddleOCR
#     and Pillow (libgomp, libgl, fonts).
#  2. Installs torch from the CPU only wheel index to avoid pulling CUDA
#     binaries (saves ~3GB). For GPU, swap to a CUDA base image and remove
#     the --index-url override.
#  3. The openmed[hf] package is installed best effort. If it is not
#     available on PyPI, the pii wrapper falls back to using transformers
#     directly, so this is non blocking.
#  4. Pre downloads no models at build time so the user controls when the
#     ~700MB pull happens; first request after boot warms the caches.
#  5. Runs as a non root user.

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/app/.cache/huggingface \
    TRANSFORMERS_CACHE=/app/.cache/huggingface \
    PADDLE_PDX_CACHE_HOME=/app/.cache/paddle \
    XDIAG_CACHE_DIR=/app/.cache \
    XDIAG_SAMPLES_DIR=/app/samples

# System dependencies for paddle, opencv, pillow.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libgomp1 \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libjpeg62-turbo \
        libpng16-16 \
        fonts-dejavu-core \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Torch CPU only first, so the rest of the install does not pull cu12 wheels.
RUN pip install --upgrade pip \
    && pip install --index-url https://download.pytorch.org/whl/cpu \
        "torch>=2.4,<3"

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# OpenMed wrapper, optional; pii.py has a transformers fallback.
RUN pip install "openmed[hf]" || echo "openmed not available on this index, using transformers fallback"

COPY app /app/app

RUN useradd --create-home --uid 1001 xdiag \
    && mkdir -p /app/.cache /app/samples \
    && chown -R xdiag:xdiag /app
USER xdiag

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD curl --fail --silent http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
