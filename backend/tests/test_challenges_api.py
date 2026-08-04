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


def test_beitreten_und_austreten(session, client):
    make_user(session)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch = make_challenge(session, join_mode="opt_in")
    login(client)
    assert client.get(f"/api/challenges/{ch.id}").json()["bin_dabei"] is False
    r = client.post(f"/api/challenges/{ch.id}/join")
    assert r.status_code == 200, r.text
    assert r.json()["bin_dabei"] is True
    r = client.delete(f"/api/challenges/{ch.id}/join")
    assert r.status_code == 200
    assert r.json()["bin_dabei"] is False


def test_beitreten_ist_idempotent(session, client):
    make_user(session)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch = make_challenge(session, join_mode="opt_in")
    login(client)
    client.post(f"/api/challenges/{ch.id}/join")
    r = client.post(f"/api/challenges/{ch.id}/join")
    assert r.status_code == 200
    assert r.json()["bin_dabei"] is True


def test_beitreten_zu_auto_challenge_ist_409(session, client):
    make_user(session)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch = make_challenge(session, join_mode="auto")
    login(client)
    assert client.post(f"/api/challenges/{ch.id}/join").status_code == 409


def test_beitreten_nach_ende_ist_409(session, client):
    heute = date.today()
    make_user(session)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch = make_challenge(
        session, join_mode="opt_in", status="beendet",
        period_start=heute - timedelta(days=20), period_end=heute - timedelta(days=10),
    )
    login(client)
    assert client.post(f"/api/challenges/{ch.id}/join").status_code == 409


def test_beitreten_zu_geplanter_challenge_erlaubt(session, client):
    heute = date.today()
    make_user(session)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch = make_challenge(
        session, join_mode="opt_in", status="geplant",
        period_start=heute + timedelta(days=5), period_end=heute + timedelta(days=20),
    )
    login(client)
    assert client.post(f"/api/challenges/{ch.id}/join").status_code == 200


def test_austreten_aus_beendeter_challenge_ist_409(session, client):
    heute = date.today()
    make_user(session)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch = make_challenge(
        session, join_mode="opt_in", status="beendet",
        period_start=heute - timedelta(days=20), period_end=heute - timedelta(days=10),
    )
    login(client)
    assert client.delete(f"/api/challenges/{ch.id}/join").status_code == 409


def _basis(**kw) -> dict:
    heute = date.today()
    daten = {
        "title": "August bis Stuttgartlauf",
        "mode": "ziel",
        "target": 300.0,
        "metric": "mm",
        "join_mode": "auto",
        "period_start": (heute + timedelta(days=1)).isoformat(),
        "period_end": (heute + timedelta(days=20)).isoformat(),
    }
    daten.update(kw)
    return daten


def test_anlegen_nur_als_admin(session, client):
    make_user(session, username="erik")
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    login(client)
    assert client.post("/api/challenges", json=_basis()).status_code == 403


def test_admin_legt_challenge_an(session, client):
    make_user(session, username="erik", is_admin=True)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    login(client)
    r = client.post("/api/challenges", json=_basis(prize="Startplatz"))
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "geplant"
    assert r.json()["prize"] == "Startplatz"


def test_anlegen_validiert(session, client):
    heute = date.today()
    make_user(session, username="erik", is_admin=True)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    lauf = make_category(session, name="Joggen", factor=1.0)
    login(client)

    faelle = [
        _basis(period_start=(heute + timedelta(days=9)).isoformat(),
               period_end=(heute + timedelta(days=2)).isoformat()),
        _basis(period_start=(heute - timedelta(days=9)).isoformat(),
               period_end=(heute - timedelta(days=2)).isoformat()),
        _basis(mode="ziel", target=None),
        _basis(mode="rangliste", target=None, top_n=0),
        _basis(metric="quatsch"),
        _basis(metric="streak", streak_min_mm=0.0),
        _basis(category_ids=[lauf.id, 9999]),
        _basis(mode="quatsch"),
        _basis(join_mode="quatsch"),
    ]
    for daten in faelle:
        assert client.post("/api/challenges", json=daten).status_code == 422, daten


def test_patch_aendert_titel_immer_regeln_nur_geplant(session, client):
    make_user(session, username="erik", is_admin=True)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch = make_challenge(session, status="laufend")
    login(client)
    r = client.patch(f"/api/challenges/{ch.id}", json={"title": "Neuer Titel"})
    assert r.status_code == 200
    assert r.json()["title"] == "Neuer Titel"
    r = client.patch(f"/api/challenges/{ch.id}", json={"target": 50.0})
    assert r.status_code == 409


def test_patch_regeln_bei_geplanter_challenge_erlaubt(session, client):
    heute = date.today()
    make_user(session, username="erik", is_admin=True)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch = make_challenge(
        session, status="geplant",
        period_start=heute + timedelta(days=3), period_end=heute + timedelta(days=9),
    )
    login(client)
    r = client.patch(f"/api/challenges/{ch.id}", json={"target": 50.0})
    assert r.status_code == 200
    assert r.json()["target"] == 50.0


def test_delete_bricht_ab_statt_zu_loeschen(session, client):
    make_user(session, username="erik", is_admin=True)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch = make_challenge(session)
    login(client)
    assert client.delete(f"/api/challenges/{ch.id}").status_code == 204
    session.expire_all()
    assert session.get(Challenge, ch.id).status == "abgebrochen"


def _beendete_mit_qualifizierten(session):
    """Beendete Ziel-Challenge, in der anna qualifiziert ist und ben nicht."""
    import json

    from app.models import Challenge

    heute = date.today()
    anna = make_user(session, username="anna", is_admin=True)
    ben = make_user(session, username="ben")
    ch = Challenge(
        title="August-Ziel", creator_id=anna.id, mode="ziel", target=100.0,
        metric="mm", join_mode="auto",
        period_start=heute - timedelta(days=20), period_end=heute - timedelta(days=10),
        status="beendet",
        result_json=json.dumps(
            {
                "entries": [
                    {"user_id": anna.id, "value": 120.0, "rank": 1, "geschafft": True},
                    {"user_id": ben.id, "value": 40.0, "rank": 2, "geschafft": False},
                ],
                "gewinner_ids": [anna.id],
            }
        ),
    )
    session.add(ch)
    session.commit()
    session.refresh(ch)
    return ch, anna, ben


def test_sieger_eintragen_und_korrigieren(session, client):
    import json

    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch, anna, ben = _beendete_mit_qualifizierten(session)
    login(client, username="anna")

    r = client.put(f"/api/challenges/{ch.id}/sieger", json={"user_id": anna.id})
    assert r.status_code == 200, r.text
    assert r.json()["sieger_id"] == anna.id

    # Korrektur ist erlaubt — ein Eintrag ist eine Tatsache, keine Ziehung.
    ch.result_json = json.dumps(
        {**json.loads(ch.result_json), "gewinner_ids": [anna.id, ben.id]}
    )
    session.add(ch)
    session.commit()
    r = client.put(f"/api/challenges/{ch.id}/sieger", json={"user_id": ben.id})
    assert r.status_code == 200
    assert r.json()["sieger_id"] == ben.id


def test_sieger_nur_aus_den_qualifizierten(session, client):
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch, _anna, ben = _beendete_mit_qualifizierten(session)
    login(client, username="anna")
    r = client.put(f"/api/challenges/{ch.id}/sieger", json={"user_id": ben.id})
    assert r.status_code == 422


def test_sieger_nur_als_admin(session, client):
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch, anna, _ben = _beendete_mit_qualifizierten(session)
    login(client, username="ben")
    r = client.put(f"/api/challenges/{ch.id}/sieger", json={"user_id": anna.id})
    assert r.status_code == 403


def test_sieger_erst_nach_dem_einfrieren(session, client):
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch, anna, _ben = _beendete_mit_qualifizierten(session)
    ch.status = "laufend"
    session.add(ch)
    session.commit()
    login(client, username="anna")
    r = client.put(f"/api/challenges/{ch.id}/sieger", json={"user_id": anna.id})
    assert r.status_code == 409


def test_sieger_nicht_bei_rangliste(session, client):
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch, anna, _ben = _beendete_mit_qualifizierten(session)
    ch.mode = "rangliste"
    session.add(ch)
    session.commit()
    login(client, username="anna")
    r = client.put(f"/api/challenges/{ch.id}/sieger", json={"user_id": anna.id})
    assert r.status_code == 409


def test_sieger_korrektur_erzeugt_kein_zweites_feed_event(session, client):
    import json

    from sqlmodel import select

    from app.models import FeedEvent, Season

    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch, anna, ben = _beendete_mit_qualifizierten(session)
    session.add(Season(year=date.today().year, goal_km=1000.0, start_date=date.today()))
    ch.result_json = json.dumps(
        {**json.loads(ch.result_json), "gewinner_ids": [anna.id, ben.id]}
    )
    session.add(ch)
    session.commit()
    login(client, username="anna")

    client.put(f"/api/challenges/{ch.id}/sieger", json={"user_id": anna.id})
    client.put(f"/api/challenges/{ch.id}/sieger", json={"user_id": ben.id})
    events = [
        e for e in session.exec(select(FeedEvent)).all() if e.type == "challenge_sieger"
    ]
    assert len(events) == 1
    assert events[0].user_id == ben.id
