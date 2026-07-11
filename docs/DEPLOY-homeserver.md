# Deploy auf dem Home-Server (Docker + Cloudflare Tunnel + Auto-Deploy)

Anleitung für den Betrieb von MeterMachen auf einem eigenen Server zuhause,
öffentlich erreichbar, mit automatischem Deploy vom `main`-Branch.

Für den VPS-Betrieb (Caddy, eigene öffentliche IP) siehe stattdessen
[DEPLOY-netcup.md](DEPLOY-netcup.md).

---

## Wie das Ganze zusammenhängt

```
git push main
      │
      ▼
GitHub Actions ──baut Image──▶ GHCR (ghcr.io/kirewx/metermachen:latest)
                                        │
                                        │ Watchtower pollt alle 5 min
                                        ▼
   Cloudflare ◀──ausgehender Tunnel── Home-Server
        ▲                              ├── app         (kein Port nach außen)
        │                              ├── cloudflared
   https://meter.deine-domain.de       └── watchtower
        │
    Besucher
```

Zwei Eigenschaften, die das Setup angenehm machen:

- **Kein Port-Forwarding.** `cloudflared` baut die Verbindung von innen nach
  außen auf. Dein Router bleibt zu, deine Heim-IP steht nirgends, und es
  funktioniert auch hinter DS-Lite/CGNAT (kein echtes öffentliches IPv4 nötig).
- **Kein Konflikt mit Pi-hole.** Der Stack veröffentlicht keinen einzigen Port
  am Host, also auch nicht die 80, auf der Pi-hole gern sitzt.

Der Server baut nichts selbst — GitHub baut, der Server zieht nur das fertige
Image. Das schont RAM/CPU und gibt dir versionierte Images zum Zurückrollen.

---

## Voraussetzungen

- Home-Server mit Docker + Docker Compose (Portainer darf danebenlaufen, wird
  hier aber nicht gebraucht).
- Eine eigene Domain.
- Ein Cloudflare-Account (Free-Plan genügt).

---

## Schritt 1 — Domain zu Cloudflare umziehen

> **Warum überhaupt?** Der Tunnel funktioniert über einen DNS-Eintrag vom Typ
> `CNAME → <tunnel-id>.cfargotunnel.com`. Diesen Zielnamen kann **nur**
> Cloudflare auflösen; bei Strato lässt er sich nicht anlegen. Die Alternative,
> bei der die Domain beim alten Anbieter bleibt ("Partial/CNAME Setup"),
> ist Business-Plan aufwärts. Also: DNS-Hoheit zu Cloudflare.
>
> Die Domain bleibt bei Strato **registriert**. Nur die Nameserver ändern sich.

> [!IMPORTANT]
> Im **Free-Plan** geht ausschließlich der Umzug der **gesamten** Domain
> ("full setup"). Nur eine einzelne Subdomain an Cloudflare zu delegieren
> (eine Subdomain als eigene Zone) ist **Enterprise-only**; die CNAME-/Partial-
> Variante ist Business aufwärts. Der „Add a site"-Assistent akzeptiert deshalb
> auch nur Root-Domains, keine Subdomains. Liegt auf deiner Domain noch anderes
> (E-Mail, Website) und willst du das **nicht** zu Cloudflare umziehen, ist
> dieser Home-Server-Weg für dich nicht der richtige — nimm dann den VPS-Weg
> ([DEPLOY-netcup.md](DEPLOY-netcup.md)), bei dem ein einzelner A-Record beim
> bestehenden Anbieter genügt.

> [!WARNING]
> Sobald die Nameserver umgestellt sind, gelten **alle** DNS-Einträge bei Strato
> nicht mehr. Liegt auf der Domain E-Mail (MX-Records) oder eine Website, ist
> beides sofort tot, wenn die Einträge nicht vorher in Cloudflare stehen.
> Schritt 1.1 ist deshalb keine Fleißarbeit, sondern der wichtigste Schritt.

**1.1 — Bestehende Einträge sichern.** Bei Strato unter
Domainverwaltung → Zahnrad → *DNS* alle Records notieren, besonders
`MX`, `TXT` (SPF/DKIM), `A`, `CNAME`. Zur Kontrolle von außen:

```bash
dig +short deine-domain.de MX
dig +short deine-domain.de TXT
dig +short deine-domain.de A
```

**1.2 — Domain in Cloudflare anlegen.** Dashboard → *Add a site* → Domain
eintragen → *Free*. Cloudflare scannt die vorhandenen Records und übernimmt die
meisten automatisch. **Trotzdem prüfen** und Fehlendes aus 1.1 von Hand
nachtragen, bevor du weitermachst.

**1.3 — Nameserver bei Strato umstellen.** Cloudflare zeigt dir zwei Nameserver
(z. B. `xxx.ns.cloudflare.com`). Bei Strato: Domainverwaltung → Zahnrad →
Tab *DNS* → *Eigene Nameserver* aktivieren → beide eintragen → speichern.

Die Umstellung braucht meist Minuten, laut Registrar-Doku bis zu 24 Stunden.
Cloudflare schickt eine Mail, sobald die Domain aktiv ist. Prüfen:

```bash
dig +short NS deine-domain.de
```

---

## Schritt 2 — Cloudflare Tunnel anlegen

1. Cloudflare Dashboard → **Zero Trust** → *Networks* → *Tunnels* → *Create a tunnel*.
2. Typ **Cloudflared**, Name z. B. `homeserver`.
3. Im Installationsschritt zeigt Cloudflare einen langen **Connector-Token**
   (in der `docker run ... --token eyJ...`-Zeile). **Diesen Token kopieren** —
   er kommt gleich in die `.env`. Die vorgeschlagene Install-Zeile brauchst du
   nicht, das übernimmt Compose.
4. Tab **Public Hostname** → *Add a public hostname*:
   - **Subdomain:** `meter`
   - **Domain:** `deine-domain.de`
   - **Type:** `HTTP`
   - **URL:** `app:8000`

   > `app:8000` ist der Compose-Servicename, nicht `localhost`. `cloudflared`
   > und die App liegen im selben Docker-Netz und erreichen sich über den Namen.
   > `HTTP` ist hier korrekt: die Strecke Besucher→Cloudflare ist HTTPS, die
   > letzten Zentimeter im Docker-Netz brauchen kein zweites Zertifikat.

Den DNS-Eintrag für `meter.deine-domain.de` legt Cloudflare dabei selbst an.

---

## Schritt 3 — Image bauen lassen und Server zum Ziehen berechtigen

**3.1 — Ersten Build auslösen.** Sobald `.github/workflows/deploy.yml` auf
`main` liegt, baut GitHub bei jedem Push. Den ersten Lauf kannst du unter
*Actions* → *Build & Publish Image* → *Run workflow* manuell starten.
Danach existiert das Package `ghcr.io/kirewx/metermachen` — standardmäßig
**privat**.

**3.2 — Zugriffstoken erzeugen.** Das Image enthält deinen Quellcode, es sollte
privat bleiben. Damit der Server es ziehen darf:

GitHub → *Settings* → *Developer settings* → *Personal access tokens* →
*Tokens (classic)* → *Generate new token*, einziger Scope: **`read:packages`**.

**3.3 — Auf dem Server anmelden.**

```bash
echo '<DEIN_PAT>' | docker login ghcr.io -u kirewx --password-stdin
```

Das schreibt `~/.docker/config.json` — genau die Datei, die der Stack in den
Watchtower-Container mountet, damit auch der automatische Pull autorisiert ist.

> Alternative ohne Token: das Package unter *Package settings* auf **Public**
> stellen. Dann ist dein Code als Image für jeden herunterladbar.

---

## Schritt 4 — Stack starten

Auf dem Server:

```bash
git clone https://github.com/kirewx/metermachen.git
cd metermachen
cp .env.homeserver.example .env
```

`.env` ausfüllen:

```bash
openssl rand -hex 32          # -> SECRET_KEY
```

- `ADMIN_PASSWORD` — frei wählen
- `PUBLIC_BASE_URL` — `https://meter.deine-domain.de` (exakt der Hostname aus Schritt 2.4)
- `CLOUDFLARE_TUNNEL_TOKEN` — der Token aus Schritt 2.3

Starten:

```bash
docker compose -f docker-compose.homeserver.yml up -d
docker compose -f docker-compose.homeserver.yml logs -f
```

In den `cloudflared`-Logs sollte `Registered tunnel connection` erscheinen.
Danach ist `https://meter.deine-domain.de` von überall erreichbar.

---

## Schritt 5 — Strava (optional)

Nur nötig, wenn du die Strava-Integration nutzt. Unter
<https://www.strava.com/settings/api>:

- **Authorization Callback Domain:** `meter.deine-domain.de`
  (nur der Hostname, ohne `https://`, ohne Pfad)

`STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET` und einen selbst ausgedachten
`STRAVA_WEBHOOK_VERIFY_TOKEN` in die `.env` eintragen, dann
`docker compose -f docker-compose.homeserver.yml up -d`.

---

## Der Auto-Deploy im Alltag

Ab jetzt gilt schlicht:

```bash
git push origin main
```

1. GitHub Actions baut das Image (~2–4 min) und pusht `:latest` + `:sha-<commit>`.
2. Watchtower bemerkt das neue `:latest` beim nächsten Poll (alle 5 min),
   zieht es, startet `app` neu und räumt das alte Image weg (`--cleanup`).

Also: **spätestens ~10 Minuten nach dem Push ist die Änderung live.**

Sofort deployen statt warten:

```bash
docker compose -f docker-compose.homeserver.yml pull app
docker compose -f docker-compose.homeserver.yml up -d app
```

Watchtower fasst dabei **nur** Container mit dem Label
`com.centurylinklabs.watchtower.scope=metermachen` an. Pi-hole, Portainer und
alles andere auf dem Server bleiben unberührt.

---

## Betrieb

**Backup.** Die gesamte Anwendungsdatenlage ist eine SQLite-Datei unter `./data`:

```bash
docker compose -f docker-compose.homeserver.yml stop app
tar czf metermachen-$(date +%F).tar.gz data/
docker compose -f docker-compose.homeserver.yml start app
```

**Rollback.** Jeder Commit liegt als eigenes Image vor. Im Notfall in
`docker-compose.homeserver.yml` das Tag auf einen bekannten guten Commit
festnageln und Watchtower vorübergehend stoppen:

```yaml
image: ghcr.io/kirewx/metermachen:sha-<voller-commit-hash>
```

**Logs.**

```bash
docker compose -f docker-compose.homeserver.yml logs -f app
docker compose -f docker-compose.homeserver.yml logs -f cloudflared
```

---

## Fallstricke

- **Läuft der Server auf ARM (Raspberry Pi)?** Dann schlägt der Start mit
  `exec format error` fehl. In `.github/workflows/deploy.yml` bei `platforms:`
  `linux/arm64` ergänzen und neu bauen lassen.
- **`cloudflared` startet, aber die Seite bleibt weiß.** Meist zeigt der Public
  Hostname auf `localhost:8000` statt auf `app:8000`.
- **Login funktioniert nicht / Strava-Redirect landet falsch.** `PUBLIC_BASE_URL`
  stimmt nicht exakt mit dem Public Hostname überein (Tippfehler, `http` statt
  `https`, Slash am Ende).
- **Watchtower zieht nichts.** Fast immer fehlende Registry-Credentials:
  prüfen, ob `~/.docker/config.json` auf dem Server existiert und einen
  `ghcr.io`-Eintrag hat.
