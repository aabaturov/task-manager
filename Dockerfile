# ---------- stage 1: build the React frontend ----------
FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
# Make npm resilient to flaky networks: short per-request timeout so a stuck
# connection fails fast and retries, instead of hanging silently.
RUN npm config set fetch-retries 6 \
    && npm config set fetch-retry-mintimeout 5000 \
    && npm config set fetch-retry-maxtimeout 30000 \
    && npm config set fetch-timeout 60000 \
    && npm config set maxsockets 8 \
    && npm install --no-audit --no-fund --loglevel=http
COPY frontend/ ./
RUN npm run build

# ---------- stage 2: python runtime (used by both web and bot) ----------
FROM python:3.12-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STATIC_DIR=/app/static \
    DATABASE_PATH=/data/app.db

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
# Built static assets from stage 1 (served by FastAPI for the web service).
COPY --from=frontend /frontend/dist ./static

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
