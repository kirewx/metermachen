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
 https://metermachen.jasperz.de        └── watchtower
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

## Schritt 1 — Nur die Subdomain `metermachen.jasperz.de` an Cloudflare delegieren

> **Warum überhaupt?** Der Tunnel funktioniert über einen DNS-Eintrag vom Typ
> `CNAME → <tunnel-id>.cfargotunnel.com`. Diesen Zielnamen kann **nur**
> Cloudflare auflösen; bei Strato lässt er sich nicht anlegen. Cloudflare muss
> also für den Namen zuständig sein.
>
> **Wichtig:** Auf `jasperz.de` liegt noch anderes (E-Mail, Website o. Ä.).
> Deshalb ziehen wir **nicht** die ganze Domain zu Cloudflare um — das würde
> alle Strato-DNS-Einträge auf einen Schlag ungültig machen. Stattdessen
> delegieren wir **nur die eine Subdomain** `metermachen.jasperz.de` an
> Cloudflare. `jasperz.de` selbst bleibt komplett bei Strato, unangetastet.
> Blast-Radius = genau diese Subdomain.

**1.1 — Subdomain als eigene Zone in Cloudflare anlegen.** Cloudflare Dashboard →
*Add a site* → dort **`metermachen.jasperz.de`** eintragen (nicht `jasperz.de`!)
→ Plan *Free*. Cloudflare findet keine bestehenden Records (die Subdomain ist ja
neu) — das ist in Ordnung, der Tunnel legt seinen Eintrag später selbst an.

Cloudflare zeigt dir am Ende **zwei Nameserver**, z. B.:

```
xy.ns.cloudflare.com
zz.ns.cloudflare.com
```

**1.2 — Delegation bei Strato eintragen.** In der DNS-Verwaltung von
`jasperz.de` (Strato: Domainverwaltung → Zahnrad → *DNS*) **zwei NS-Records**
für den Host `metermachen` anlegen, mit genau den beiden Cloudflare-Namen:

```
metermachen   NS   xy.ns.cloudflare.com
metermachen   NS   zz.ns.cloudflare.com
```

Sonst an `jasperz.de` **nichts** ändern — kein Nameserver-Umzug. MX, Website und
alle anderen Records bleiben, wie sie sind.

> [!NOTE]
> Falls Stratos DNS-Editor keine NS-Records für eine Subdomain zulässt, ist
> dieser Weg blockiert. Fallback dann: Mini-VPS als Relay (WireGuard/frp) —
> melde dich, dann bauen wir das.

**1.3 — Delegation prüfen.** Greift meist nach Minuten, kann laut Doku bis zu
24 h dauern. Cloudflare schickt eine Mail, sobald die Zone aktiv ist. Von außen:

```bash
dig +short NS metermachen.jasperz.de
```

Sobald hier die beiden `*.ns.cloudflare.com` erscheinen, ist die Subdomain
delegiert und du kannst weitermachen.

---

## Schritt 2 — Cloudflare Tunnel anlegen

1. Cloudflare Dashboard → **Zero Trust** → *Networks* → *Tunnels* → *Create a tunnel*.
2. Typ **Cloudflared**, Name z. B. `homeserver`.
3. Im Installationsschritt zeigt Cloudflare einen langen **Connector-Token**
   (in der `docker run ... --token eyJ...`-Zeile). **Diesen Token kopieren** —
   er kommt gleich in die `.env`. Die vorgeschlagene Install-Zeile brauchst du
   nicht, das übernimmt Compose.
4. Tab **Public Hostname** → *Add a public hostname*:
   - **Subdomain:** *(leer lassen)*
   - **Domain:** `metermachen.jasperz.de`  ← die ganze Subdomain ist hier die „Domain", weil sie eine eigene Zone ist
   - **Type:** `HTTP`
   - **URL:** `app:8000`

   > `app:8000` ist der Compose-Servicename, nicht `localhost`. `cloudflared`
   > und die App liegen im selben Docker-Netz und erreichen sich über den Namen.
   > `HTTP` ist hier korrekt: die Strecke Besucher→Cloudflare ist HTTPS, die
   > letzten Zentimeter im Docker-Netz brauchen kein zweites Zertifikat.

Den DNS-Eintrag für `metermachen.jasperz.de` legt Cloudflare dabei selbst an.

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
- `PUBLIC_BASE_URL` — `https://metermachen.jasperz.de` (exakt der Hostname aus Schritt 2.4)
- `CLOUDFLARE_TUNNEL_TOKEN` — der Token aus Schritt 2.3

Starten:

```bash
docker compose -f docker-compose.homeserver.yml up -d
docker compose -f docker-compose.homeserver.yml logs -f
```

In den `cloudflared`-Logs sollte `Registered tunnel connection` erscheinen.
Danach ist `https://metermachen.jasperz.de` von überall erreichbar.

---

## Schritt 5 — Strava (optional)

Nur nötig, wenn du die Strava-Integration nutzt. Unter
<https://www.strava.com/settings/api>:

- **Authorization Callback Domain:** `metermachen.jasperz.de`
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
