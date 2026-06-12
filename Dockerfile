# Stage 1: Frontend bauen
FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Backend + statisches Frontend
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /srv/backend
COPY backend/pyproject.toml backend/uv.lock* ./
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev
COPY backend/app ./app
COPY --from=frontend /build/dist /srv/frontend/dist

ENV DATA_DIR=/data \
    FRONTEND_DIST=/srv/frontend/dist
EXPOSE 8000
CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
