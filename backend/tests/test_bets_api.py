from datetime import date, timedelta

from app.models import Season
from tests.conftest import make_addon, make_category, make_user, login

HEUTE = date.today()


def _setup(session):
    session.add(
        Season(
            year=HEUTE.year,
            goal_km=1000,
            milestones_json="[]",
            start_date=HEUTE - timedelta(days=10),
        )
    )
    make_addon(session, "sidebets", enabled=True)  # Wetten-Add-on aktiv
    erik = make_user(session, is_admin=True)
    lisa = make_user(session, username="lisa")
    make_category(session, factor=1.0)
    session.commit()
    return erik, lisa


def _duell_body(lisa, stake=20):
    return {
        "type": "duell",
        "title": "Erik vs. Lisa",
        "stake": stake,
        "period_start": (HEUTE + timedelta(days=1)).isoformat(),
        "period_end": (HEUTE + timedelta(days=8)).isoformat(),
        "params": {"opponent_id": lisa.id},
    }


def test_bets_requires_auth(client, session):
    make_addon(session, "sidebets", enabled=True)
    assert client.get("/api/bets").status_code == 401


def test_bets_404_when_addon_disabled(client, session):
    # Ohne aktives sidebets-Add-on ist die Wetten-API nicht verfügbar.
    make_user(session, is_admin=True)
    login(client)
    assert client.get("/api/bets").status_code == 404
    assert client.get("/api/points").status_code == 404


def test_create_and_accept_duell_flow(client, session):
    erik, lisa = _setup(session)
    login(client)
    r = client.post("/api/bets", json=_duell_body(lisa))
    assert r.status_code == 201, r.text
    bet = r.json()
    assert bet["status"] == "offen"
    assert bet["my_role"] == "ersteller"

    # Punkte: Startgutschrift 100 - Einsatz 20
    r = client.get("/api/points")
    assert r.json()["balance"] == 80

    login(client, username="lisa")
    r = client.post(f"/api/bets/{bet['id']}/respond", json={"action": "accept"})
    assert r.status_code == 200
    assert r.json()["status"] == "laufend"

    r = client.get("/api/bets")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["standing"] == {}  # Zeitraum noch nicht gestartet


def test_create_bet_validation_error_ist_400(client, session):
    erik, lisa = _setup(session)
    login(client)
    body = _duell_body(lisa, stake=500)  # mehr als Kontostand
    r = client.post("/api/bets", json=body)
    assert r.status_code == 400
    assert "Punkte" in r.json()["detail"]


def test_cancel_vor_start(client, session):
    erik, lisa = _setup(session)
    login(client)
    bet = client.post("/api/bets", json=_duell_body(lisa)).json()
    r = client.post(f"/api/bets/{bet['id']}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "abgebrochen"
    assert client.get("/api/points").json()["balance"] == 100


def test_points_ranking(client, session):
    erik, lisa = _setup(session)
    login(client)
    client.post("/api/bets", json=_duell_body(lisa))  # Erik: 80, Lisa: 100
    r = client.get("/api/points/ranking")
    assert r.status_code == 200
    ranking = r.json()
    assert ranking[0]["display_name"] == "Lisa"
    assert ranking[0]["rank"] == 1
    assert ranking[1]["balance"] == 80


def test_bet_achievements_leer(client, session):
    _setup(session)
    login(client)
    r = client.get("/api/bets/achievements")
    assert r.status_code == 200
    keys = [a["key"] for a in r.json()]
    assert keys == ["zocker", "david", "high_roller", "orakel"]
    assert all(a["achieved"] is False for a in r.json())
