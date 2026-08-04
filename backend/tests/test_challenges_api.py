from datetime import date, timedelta

from app.models import Challenge
from tests.conftest import login, make_addon, make_category, make_user


def make_challenge(session, **kw) -> Challenge:
    heute = date.today()
    daten = dict(
        title="Test", creator_id=1, mode="ziel", target=100.0, metric="mm",
        join_mode="auto", period_start=heute - timedelta(days=5),
        period_end=heute + timedelta(days=5), status="laufend",
    )
    daten.update(kw)
    ch = Challenge(**daten)
    session.add(ch)
    session.commit()
    session.refresh(ch)
    return ch


def test_liste_braucht_aktives_addon(session, client):
    make_user(session)
    make_addon(session, key="challenges", label="Challenges", enabled=False)
    login(client)
    assert client.get("/api/challenges").status_code == 404


def test_liste_liefert_stand(session, client):
    from app.models import Activity

    user = make_user(session)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    lauf = make_category(session, name="Joggen", factor=1.0)
    ch = make_challenge(session)
    session.add(
        Activity(
            user_id=user.id, category_id=lauf.id,
            date=date.today(), distance_km=120.0,
        )
    )
    session.commit()
    login(client)
    r = client.get("/api/challenges")
    assert r.status_code == 200, r.text
    eintrag = next(c for c in r.json() if c["id"] == ch.id)
    assert eintrag["bin_dabei"] is True
    assert eintrag["standings"][0]["value"] == 120.0
    assert eintrag["standings"][0]["geschafft"] is True
    assert eintrag["standings"][0]["display_name"] == "Erik"
    assert eintrag["mein_stand"]["value"] == 120.0
    assert eintrag["vorlaeufig"] is False


def test_liste_verschweigt_abgebrochene(session, client):
    make_user(session)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    make_challenge(session, status="abgebrochen")
    login(client)
    assert client.get("/api/challenges").json() == []


def test_detail_liefert_einzelne_challenge(session, client):
    make_user(session)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch = make_challenge(session, title="Radler-Monat")
    login(client)
    r = client.get(f"/api/challenges/{ch.id}")
    assert r.status_code == 200
    assert r.json()["title"] == "Radler-Monat"


def test_detail_404_bei_unbekannter_id(session, client):
    make_user(session)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    login(client)
    assert client.get("/api/challenges/999").status_code == 404
