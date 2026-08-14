# Admin-generierte Passwort-Reset-Links

## Problem

Wer sein Passwort vergisst, ist ausgesperrt. Es gibt keinen Selbstbedienungs-Reset
und keinen Operator-Weg außer direktem Datenbank-Eingriff. Der naheliegende Weg —
Reset-Mail — scheitert an Infrastruktur: MeterMachen verschickt keine E-Mails, und
auf dem Netcup-VPS wäre SMTP-Versand (Relay-Konto, SPF/DKIM, Port-Freigaben) ein
eigenes Projekt. Kontowiederherstellung darf daran nicht hängen.

## Lösung

Ein Admin erzeugt in der Mitglieder-Liste einen einmalig nutzbaren Reset-Link und
übergibt ihn außerhalb der App — persönlich, per Chat, wie man sich eben erreicht.
Der Link öffnet eine öffentliche Seite, auf der die Person ein neues Passwort setzt
und direkt eingeloggt wird (wie beim Einladungs-Flow).

Das Muster stammt aus ChAiMa (Spec 2026-08-07 „Admin-Generated Password Reset
Links"), übersetzt auf den MeterMachen-Stack: statt fastapi-users-JWT ein
`itsdangerous`-Token — dieselbe Bibliothek, die schon die Session-Tokens signiert.

**Token-Aufbau:** `URLSafeTimedSerializer(SECRET_KEY, salt="password-reset")`
serialisiert `[user_id, fingerprint]`, wobei `fingerprint` ein gekürzter
SHA-256-Hash des *aktuellen* `password_hash` ist. Beim Einlösen wird der
Fingerprint gegen den Hash in der Datenbank geprüft. Eine Passwort-Änderung
ändert den Hash und macht damit jeden ausstehenden Token automatisch ungültig —
Einmal-Nutzung ohne eigene Token-Tabelle, ohne Migration. Ablauf über `max_age`
(24 Stunden): lang genug für Übergabe von Hand, kurz genug, um das Fenster klein
zu halten.

## Verworfene Alternativen

1. **Token-Tabelle wie `Invite`** (gespeichert, widerrufbar, auflistbar): mehr
   Code plus Schema-Änderung für eine Fähigkeit (Widerruf vor Ablauf), die bei
   24 h TTL und automatischer Entwertung kaum Wert hat.
2. **Self-Service „Passwort vergessen" per E-Mail**: braucht SMTP-Infrastruktur.
   Bewusst nicht jetzt — der hier spezifizierte Einlöse-Endpoint ist genau das,
   was ein späterer Mail-Flow ebenfalls nutzen würde; die Erweiterung wäre rein
   additiv.

## Backend

### `auth.py`

- `RESET_MAX_AGE = 60 * 60 * 24` (24 Stunden)
- eigener Serializer mit `salt="password-reset"` (Domänentrennung von Session-Tokens)
- `password_fingerprint(password_hash) -> str` — SHA-256, auf 16 Hex-Zeichen gekürzt
- `create_reset_token(user_id, password_hash) -> str`
- `read_reset_token(token) -> tuple[user_id, fingerprint] | None` — `None` bei
  Manipulation, Ablauf oder unerwartetem Payload

### `routers/users.py` — Ausstellen

`POST /api/users/{user_id}/reset-link` (nur Admin) → `ResetLinkOut { token, url,
expires_at }`. `url` wie bei Einladungen: `{PUBLIC_BASE_URL}/passwort-reset/{token}`,
relativ wenn `PUBLIC_BASE_URL` leer ist (Frontend fällt auf `window.location.origin`
zurück). 404 bei unbekanntem User. Jeder Admin darf jeden zurücksetzen — in
MeterMachen sind alle Admins gleichgestellt (jeder Admin kann ohnehin
Admin-Einladungen erzeugen), eine Sonderregel wie ChAiMas Superuser-Schutz hätte
hier kein Gegenstück.

### `routers/auth_router.py` — Einlösen

`POST /api/auth/reset-password` mit `{ token, password (min. 4) }`, öffentlich:

1. Token lesen; `None` → 400 „Link ungültig oder abgelaufen"
2. User laden; fehlt er oder passt der Fingerprint nicht (Passwort seit Ausstellung
   geändert = Link verbraucht) → ebenfalls 400, gleiche Meldung — keine
   Unterscheidbarkeit für Außenstehende
3. deaktivierter Account → 403 „Account ist deaktiviert" (wie Login)
4. neues Passwort hashen, speichern, Session-Cookie setzen, `MeOut` zurückgeben

Bewusst **kein** Prüf-Endpoint vor dem Einlösen (anders als `GET /api/invites/{token}`):
er würde erlauben, Token auf Gültigkeit abzuklopfen. Die Reset-Seite zeigt ihr
Formular bedingungslos und meldet das Ergebnis erst beim Absenden.

## Frontend

- **`api/client.ts`**: Typ `ResetLink`, Methoden `createResetLink(userId)` und
  `resetPassword(token, password)`.
- **`App.tsx`**: Route `/passwort-reset/:token` im ausgeloggten Zweig, neben
  `/einladung/:token`.
- **`pages/PasswortReset.tsx`** (neu): zwei Passwortfelder mit Gleichheits-Check,
  Absenden, bei Erfolg `['me']` setzen und zu `/` navigieren (auto-eingeloggt).
  400 → „Dieser Link ist ungültig oder abgelaufen."
- **`pages/Admin.tsx`**, Sektion „Mitglieder": Ghost-Button „Reset-Link" pro
  Zeile (auch für den eigenen Account — auch der eigene Passwort-Verlust ist der
  Anwendungsfall). Öffnet ein `Modal` mit QR-Code, URL, Kopieren-Button und dem
  Warnhinweis, dass der Link vollen Zugriff auf das Konto gewährt und nur direkt
  an die Person gehen darf.
- **`pages/Login.tsx`**: eine Zeile unter dem Formular: Passwort vergessen →
  Admin fragt. Ohne Mail-Versand gibt es keinen Selbstbedienungsweg; das ehrlich
  hinzuschreiben ist besser, als Nutzer suchen zu lassen.

## Bekannte Grenzen

- **Kein Session-Entzug beim Reset.** Sessions sind zustandslose signierte Tokens
  (30 Tage); ein Reset loggt bestehende Sitzungen nicht aus. Das Feature stellt
  *Zugang wieder her*, es ist kein Mittel gegen ein kompromittiertes Konto. Dafür
  bleibt: Passwort zurücksetzen und `SECRET_KEY` rotieren (invalidiert alle
  Sessions der Instanz). Gleiche bewusste Abwägung wie in ChAiMa.
- **Ausgestellte Links sind nicht einzeln widerrufbar.** Begrenzt durch 24 h TTL
  und automatische Entwertung bei der nächsten Passwort-Änderung.
- **Mehrere offene Links pro User bleiben parallel gültig**, bis das Passwort
  geändert wird oder sie ablaufen. Bei der Zielgruppe (Freundesgruppe, Handvoll
  Nutzer) unkritisch.

## Tests

`backend/tests/test_password_reset.py`:

- Admin erzeugt Link → 200, `url` endet auf `/passwort-reset/{token}`
- Nicht-Admin → 403, unbekannter User → 404
- Gültiger Token → 200, Cookie gesetzt (`/api/auth/me` funktioniert), Login mit
  neuem Passwort klappt, altes Passwort scheitert
- Derselbe Token ein zweites Mal → 400 (Fingerprint passt nicht mehr — der Test,
  der die Einmal-Nutzung festnagelt)
- Manipulierter Token → 400; abgelaufener Token → 400 (via Monkeypatch von
  `RESET_MAX_AGE`)
- Deaktivierter Account → 403
- Zu kurzes Passwort → 422

Frontend: `PasswortReset.test.tsx` nach dem Muster von `Einladung.test.tsx`
(Formular rendert, Erfolg navigiert, Fehler wird angezeigt).
