# Deployment: NetCup VPS + Docker + Caddy

Anleitung für den Betrieb von MeterMachen auf einem NetCup VPS (getestet gedacht
für **VPS 500 G12**, Standort Nürnberg). Caddy übernimmt HTTPS automatisch.

Ergebnis: App unter `https://<deine-domain>` erreichbar, inkl. funktionierender
Strava-Integration (OAuth + Webhook).

---

## 0. Voraussetzungen

- NetCup VPS ist bestellt, du hast Root-SSH-Zugang (`ssh root@<server-ip>`).
- Eine (Sub-)Domain, z. B. `meter.deinedomain.de`.
- Deine Strava-API-Keys liegen bereit (Client ID, Client Secret).

---

## 1. DNS setzen

Beim Domain-Anbieter einen Record auf die Server-IP legen:

    A     meter.deinedomain.de   ->   <server-ipv4>
    AAAA  meter.deinedomain.de   ->   <server-ipv6>   (falls IPv6 genutzt wird)

Kurz warten, bis es greift:

    ping meter.deinedomain.de    # muss die Server-IP zeigen

> Wichtig: DNS muss **vor** dem ersten Start stimmen, sonst kann Caddy kein
> Let's-Encrypt-Zertifikat ausstellen.

---

## 2. Server vorbereiten (als root)

    apt update && apt -y upgrade

    # Docker + Compose-Plugin
    curl -fsSL https://get.docker.com | sh
    docker compose version    # muss eine Version ausgeben

    # Firewall: nur SSH + HTTP + HTTPS
    apt -y install ufw
    ufw allow OpenSSH
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw --force enable

> NetCup-Hinweis: Es gibt zusätzlich ein Firewall-Feature im SCP (Server Control
> Panel). Wenn dort eine Firewall aktiv ist, müssen 80/443 auch dort offen sein.

---

## 3. Code holen

    cd /opt
    git clone https://github.com/kirewx/metermachen.git
    cd metermachen

---

## 4. Konfiguration anlegen

    cp .env.prod.example .env
    nano .env

Ausfüllen:

    SECRET_KEY=          # erzeugen: openssl rand -hex 32
    ADMIN_PASSWORD=      # dein Admin-Passwort
    DOMAIN=meter.deinedomain.de
    PUBLIC_BASE_URL=https://meter.deinedomain.de

    STRAVA_CLIENT_ID=...
    STRAVA_CLIENT_SECRET=...
    STRAVA_WEBHOOK_VERIFY_TOKEN=   # frei wählbar, z. B. openssl rand -hex 16

Tipp für `SECRET_KEY`:

    openssl rand -hex 32

---

## 5. Strava-App konfigurieren

Unter <https://www.strava.com/settings/api>:

- **Authorization Callback Domain** = nur der Hostname, also `meter.deinedomain.de`
  (ohne `https://`, ohne Pfad).

Mehr ist app-seitig nicht nötig — die App baut Redirect/Webhook-URLs selbst aus
`PUBLIC_BASE_URL`.

---

## 6. Starten

    docker compose -f docker-compose.prod.yml up -d --build

Prüfen:

    docker compose -f docker-compose.prod.yml ps
    docker compose -f docker-compose.prod.yml logs -f caddy   # Zertifikat-Ausstellung beobachten

Dann im Browser: `https://meter.deinedomain.de` → Login `admin` / `<ADMIN_PASSWORD>`.

---

## 7. Strava-Webhook-Subscription registrieren (einmalig)

Muss **nach** Schritt 6 passieren — Strava validiert den Callback sofort per GET,
die App muss also schon öffentlich per HTTPS laufen.

Das Hilfsskript liegt nicht im Image, daher direkt per `curl` (Werte aus deiner
`.env` einsetzen):

    # Anlegen
    curl -X POST https://www.strava.com/api/v3/push_subscriptions \
      -F client_id=$STRAVA_CLIENT_ID \
      -F client_secret=$STRAVA_CLIENT_SECRET \
      -F callback_url=https://meter.deinedomain.de/api/strava/webhook \
      -F verify_token=$STRAVA_WEBHOOK_VERIFY_TOKEN

    # Anzeigen
    curl -G https://www.strava.com/api/v3/push_subscriptions \
      -d client_id=$STRAVA_CLIENT_ID -d client_secret=$STRAVA_CLIENT_SECRET

    # Löschen (id aus der Anzeige)
    curl -X DELETE "https://www.strava.com/api/v3/push_subscriptions/<id>?client_id=$STRAVA_CLIENT_ID&client_secret=$STRAVA_CLIENT_SECRET"

> Die Env-Variablen sind in deiner `.env`, nicht automatisch in der Shell. Entweder
> Werte direkt einsetzen oder vorher laden: `set -a && . ./.env && set +a`.

Erfolg: Status `201` mit einer `{"id": ...}`. Danach werden neue Strava-
Aktivitäten automatisch importiert; beim ersten Verbinden eines Accounts läuft
zusätzlich der Jahres-Backfill im Hintergrund.

---

## 8. Betrieb

**Update einspielen (automatisch):**

Jeder Push auf `main` deployt automatisch: der GitHub-Actions-Job `deploy`
(`.github/workflows/deploy.yml`) verbindet sich per SSH mit dem VPS und führt
dort `git pull` + `docker compose up -d --build` aus.

Einmalige Einrichtung:

    # 1. Auf dem eigenen Rechner ein Deploy-Schlüsselpaar erzeugen (ohne Passphrase):
    ssh-keygen -t ed25519 -f deploy_key -N "" -C "github-actions-deploy"

    # 2. Public Key auf dem VPS autorisieren:
    ssh root@<server-ip> "cat >> ~/.ssh/authorized_keys" < deploy_key.pub

    # 3. In GitHub (Repo → Settings → Secrets and variables → Actions) zwei Secrets anlegen:
    #    VPS_HOST    = <server-ip oder metermachen.jasperz.de>
    #    VPS_SSH_KEY = kompletter Inhalt der Datei deploy_key (der PRIVATE Key)

    # 4. Lokale Schlüsseldateien danach sicher verwahren oder löschen.

**Update einspielen (manuell, falls nötig):**

    cd /opt/metermachen
    git pull
    docker compose -f docker-compose.prod.yml up -d --build

**Backup (SQLite-DB):**

    # die DB liegt in ./data — einfach kopieren/sichern
    tar czf metermachen-backup-$(date +%F).tar.gz data/

Zusätzlich die NetCup-**Snapshots** nutzen (Copy-on-Write, im SCP) als
Gesamt-System-Sicherung.

**Logs:**

    docker compose -f docker-compose.prod.yml logs -f app
    docker compose -f docker-compose.prod.yml logs -f caddy

**Stoppen:**

    docker compose -f docker-compose.prod.yml down

---

## Troubleshooting

- **Kein HTTPS / Caddy-Fehler im Log**: DNS zeigt nicht (oder noch nicht) auf den
  Server, oder Port 80/443 blockiert (ufw + NetCup-SCP-Firewall prüfen). Caddy
  braucht Port 80 erreichbar für die LE-Validierung.
- **Strava-Einstellung im Profil unsichtbar**: Einer der vier `STRAVA_*` /
  `PUBLIC_BASE_URL`-Werte fehlt. Nach Änderung der `.env`:
  `docker compose -f docker-compose.prod.yml up -d` (App neu starten).
- **Webhook-Subscription `create` schlägt fehl**: App war beim `curl` noch nicht
  öffentlich erreichbar, oder `verify_token` weicht von dem in der `.env` ab.
- **Login schlägt fehl**: `ADMIN_PASSWORD` in der `.env` prüfen, App neu starten.
