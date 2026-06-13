# MeterMachen 🏃🚴🥾

Kilometer-Tracking mit skalierten Kategorien und Jahres-Distanzvergleich
für den Freundeskreis. FastAPI + React, SQLite, ein Container.

## Betrieb

    SECRET_KEY=<zufälliger-string> ADMIN_PASSWORD=<passwort> docker compose up -d --build

Alternativ `.env.example` nach `.env` kopieren und ausfüllen — docker compose
liest die Datei automatisch.

App: http://localhost:8000 — Login mit `admin` / `<passwort>`.
Backup: den Ordner `./data` kopieren (SQLite-DB).

## Mitglieder

Neue Mitglieder werden nicht direkt angelegt, sondern eingeladen: im
Admin-Bereich unter „Mitglied einladen" einen Einladungslink (mit QR-Code)
erzeugen und teilen. Über den Link legt das Mitglied selbst Benutzername,
Passwort und Avatar an und ist danach direkt eingeloggt. Jeder Link ist
einmalig nutzbar und 7 Tage gültig; offene Einladungen lassen sich widerrufen.

## Entwicklung

    cd backend && uv sync && uv run uvicorn app.main:app --reload   # API :8000
    cd frontend && npm install && npm run dev                       # UI  :5173

Tests: `cd backend && uv run pytest` · `cd frontend && npm test`
Lint/Format: `uvx pre-commit install` (einmalig), läuft dann bei jedem Commit (Ruff + Basis-Checks).

## Strava-Integration (optional)

Die vier Variablen aus `.env.example` setzen (Abschnitt „Strava-Integration"):
`STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_WEBHOOK_VERIFY_TOKEN` und
`PUBLIC_BASE_URL`. Die API-App wird unter https://www.strava.com/settings/api
angelegt.

Der Endpunkt `POST /api/strava/webhook` muss öffentlich per HTTPS erreichbar
sein — lokal z. B. über einen ngrok-Tunnel (`ngrok http 8000`), dessen URL dann
als `PUBLIC_BASE_URL` eingetragen wird.

Einmalig die Webhook-Subscription registrieren (aus `backend/`, mit gesetzten
Env-Variablen):

    python -m scripts.strava_subscribe create

Zum Verwalten: `view` zeigt die aktive Subscription, `delete <id>` löscht sie.

Beim **erstmaligen Verbinden** eines Strava-Accounts werden automatisch alle
Aktivitäten des laufenden Kalenderjahres im Hintergrund importiert (nur gemappte
Sport-Typen, idempotent). Der Fortschritt wird im Profil-Modal angezeigt.

Funktioniert mit kostenlosen Strava-Accounts. Mit dem Scope `activity:read_all`
werden auch private Aktivitäten importiert. Nur neue Aktivitäten werden
automatisch übernommen; lokale Änderungen in MeterMachen bleiben erhalten
(kein Update- oder Delete-Sync).

## Doku

- Spec: docs/superpowers/specs/2026-06-12-metermachen-design.md
- Plan: docs/superpowers/plans/2026-06-12-metermachen-v1.md
