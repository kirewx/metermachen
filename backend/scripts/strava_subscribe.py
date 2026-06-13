"""Einmaliges Setup/Verwalten der Strava-Webhook-Subscription.

Aufruf (aus backend/, mit gesetzten Strava-Env-Variablen):
    python -m scripts.strava_subscribe create
    python -m scripts.strava_subscribe view
    python -m scripts.strava_subscribe delete <subscription_id>

Voraussetzung: Der Callback (PUBLIC_BASE_URL + /api/strava/webhook) muss
oeffentlich per HTTPS erreichbar sein, BEVOR 'create' aufgerufen wird —
Strava validiert ihn sofort per GET.
"""
import sys

import httpx

from app import config

PUSH_URL = "https://www.strava.com/api/v3/push_subscriptions"


def create() -> None:
    callback = f"{config.PUBLIC_BASE_URL}/api/strava/webhook"
    r = httpx.post(PUSH_URL, data={
        "client_id": config.STRAVA_CLIENT_ID,
        "client_secret": config.STRAVA_CLIENT_SECRET,
        "callback_url": callback,
        "verify_token": config.STRAVA_WEBHOOK_VERIFY_TOKEN,
    }, timeout=20)
    print(r.status_code, r.text)


def view() -> None:
    r = httpx.get(PUSH_URL, params={
        "client_id": config.STRAVA_CLIENT_ID,
        "client_secret": config.STRAVA_CLIENT_SECRET,
    }, timeout=20)
    print(r.status_code, r.text)


def delete(subscription_id: str) -> None:
    r = httpx.delete(f"{PUSH_URL}/{subscription_id}", params={
        "client_id": config.STRAVA_CLIENT_ID,
        "client_secret": config.STRAVA_CLIENT_SECRET,
    }, timeout=20)
    print(r.status_code, r.text)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "view"
    if cmd == "create":
        create()
    elif cmd == "view":
        view()
    elif cmd == "delete" and len(sys.argv) > 2:
        delete(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(1)
