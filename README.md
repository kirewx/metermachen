# MeterMachen 🏃🚴🥾

Kilometer-Tracking mit skalierten Kategorien und Jahres-Distanzvergleich
für den Freundeskreis. FastAPI + React, SQLite, ein Container.

## Betrieb

    SECRET_KEY=<zufälliger-string> ADMIN_PASSWORD=<passwort> docker compose up -d --build

Alternativ `.env.example` nach `.env` kopieren und ausfüllen — docker compose
liest die Datei automatisch.

App: http://localhost:8000 — Login mit `admin` / `<passwort>`.
Backup: den Ordner `./data` kopieren (SQLite-DB + Kartenbilder).

## Entwicklung

    cd backend && uv sync && uv run uvicorn app.main:app --reload   # API :8000
    cd frontend && npm install && npm run dev                       # UI  :5173

Tests: `cd backend && uv run pytest` · `cd frontend && npm test`
Lint/Format: `uvx pre-commit install` (einmalig), läuft dann bei jedem Commit (Ruff + Basis-Checks).

## Doku

- Spec: docs/superpowers/specs/2026-06-12-metermachen-design.md
- Plan: docs/superpowers/plans/2026-06-12-metermachen-v1.md
