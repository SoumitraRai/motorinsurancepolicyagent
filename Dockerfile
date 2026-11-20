# One image for both Render services: the web API (default CMD) and the background worker
# (`python -m rater.worker`). Containers are stateless: PDFs and analyses live in Supabase.

# --- frontend ---------------------------------------------------------------------------
FROM node:22-slim AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# Public values only (Supabase URL + anon key are designed to ship to browsers).
ARG VITE_SUPABASE_URL=""
ARG VITE_SUPABASE_ANON_KEY=""
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY
RUN npm run build

# --- backend ----------------------------------------------------------------------------
FROM python:3.12-slim
# tesseract: cross-check OCR engine; libgl1/libglib2.0-0: OpenCV runtime needed by RapidOCR.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.12.23

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock backend/.python-version backend/
RUN cd backend && uv sync --frozen --no-dev --no-install-project
COPY backend/src backend/src
RUN cd backend && uv sync --frozen --no-dev

COPY migrations/ migrations/
# Read-only challenge input, packaged with the deployment (challenge.md allows this).
COPY insurance-rater-agent-challenge/ insurance-rater-agent-challenge/
COPY --from=web /app/frontend/dist frontend/dist

ENV PATH=/app/backend/.venv/bin:$PATH \
    STATIC_DIR=/app/frontend/dist \
    PYTHONUNBUFFERED=1 \
    OCR_WORKERS=1
EXPOSE 8000
CMD ["sh", "-c", "uvicorn --factory rater.api.app:create_app_from_env --host 0.0.0.0 --port ${PORT:-8000}"]
