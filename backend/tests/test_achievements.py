from datetime import date

from app.models import Activity, Category
from app.routers.achievements import LAUF, RAD, SCHWIMM, bucket_for_category
from tests.conftest import login, make_category, make_user


def add_activity(session, user, cat, km, d=date(2026, 7, 12)):
    session.add(Activity(user_id=user.id, category_id=cat.id, date=d, distance_km=km))
    session.commit()


def test_bucket_via_icon():
    assert bucket_for_category(Category(name="X", factor=1, color="#fff", icon="rad")) == RAD
    assert bucket_for_category(Category(name="X", factor=1, color="#fff", icon="laufen")) == LAUF
    assert (
        bucket_for_category(Category(name="X", factor=1, color="#fff", icon="schwimmen"))
        == SCHWIMM
    )


def test_bucket_via_strava_types_and_name():
    assert bucket_for_category(Category(
        name="X", factor=1, color="#fff", icon="medaille", strava_sport_types='["GravelRide"]'
    )) == RAD
    assert bucket_for_category(Category(
        name="Joggen am See", factor=1, color="#fff", icon="medaille"
    )) == LAUF
    assert bucket_for_category(Category(
        name="Wandern", factor=1, color="#fff", icon="wandern"
    )) is None


def test_achievements_require_login(client):
    assert client.get("/api/achievements").status_code == 401


def test_achievements_empty_user_nothing_achieved(client, session):
    make_user(session)
    login(client)
    r = client.get("/api/achievements")
    assert r.status_code == 200
    body = r.json()
    assert {a["key"] for a in body} == {
        "startschuss", "marathon", "aermelkanal", "transalp", "ironman", "tausender",
        "stufe_rad_bronze", "stufe_rad_silber", "stufe_rad_gold",
        "stufe_lauf_bronze", "stufe_lauf_silber", "stufe_lauf_gold",
        "stufe_schwimm_bronze", "stufe_schwimm_silber", "stufe_schwimm_gold",
        "erster_gold_rad", "erster_gold_lauf", "erster_gold_schwimm",
        "testphasen_sieger", "kletterkoenig", "hattrick", "wochenkoenig",
        "psychopath", "langstreckenguru", "kurzstreckenprofi", "fruehstarter",
    }
    assert all(a["achieved"] is False for a in body)


def test_startschuss_after_first_activity(client, session):
    user = make_user(session)
    cat = make_category(session, name="Spazieren", icon="gehen")
    add_activity(session, user, cat, 2.0)
    login(client)
    a = {x["key"]: x for x in client.get("/api/achievements").json()}
    assert a["startschuss"]["achieved"] is True
    # Gehen zählt für keinen Sport-Bucket, aber für "gesamt".
    assert a["tausender"]["progress"] == 0.002


def test_ironman_needs_all_three_parts(client, session):
    user = make_user(session)
    rad = make_category(session, name="Radfahren", icon="rad", factor=1.0)
    lauf = make_category(session, name="Laufen", icon="laufen", factor=4.0)
    schwimm = make_category(session, name="Schwimmen", icon="schwimmen", factor=10.0)
    add_activity(session, user, rad, 190.0)
    add_activity(session, user, lauf, 42.0)
    login(client)
    a = {x["key"]: x for x in client.get("/api/achievements").json()}
    assert a["ironman"]["achieved"] is False  # Schwimmen fehlt
    assert a["ironman"]["progress"] == 0.0  # min über alle Teile
    assert a["marathon"]["achieved"] is False  # 42.0 < 42.2
    add_activity(session, user, schwimm, 4.0)
    a = {x["key"]: x for x in client.get("/api/achievements").json()}
    assert a["ironman"]["achieved"] is True
    assert a["ironman"]["progress"] == 1.0
    parts = {p["label"]: p for p in a["ironman"]["parts"]}
    assert parts["Rad"]["target_km"] == 190.0
    assert parts["Schwimmen"]["current_km"] == 4.0


def test_raw_km_counted_not_scaled(client, session):
    """Achievements rechnen mit echten km, nicht mit gewerteten (Faktor)."""
    user = make_user(session)
    lauf = make_category(session, name="Laufen", icon="laufen", factor=4.0)
    add_activity(session, user, lauf, 42.2)  # gewertet wären das 168.8
    login(client)
    a = {x["key"]: x for x in client.get("/api/achievements").json()}
    assert a["marathon"]["achieved"] is True
    assert a["tausender"]["achieved"] is False


def test_only_own_activities_count(client, session):
    make_user(session)
    lisa = make_user(session, username="lisa")
    lauf = make_category(session, name="Laufen", icon="laufen")
    add_activity(session, lisa, lauf, 100.0)
    login(client)  # als erik
    a = {x["key"]: x for x in client.get("/api/achievements").json()}
    assert a["startschuss"]["achieved"] is False


def test_warmup_achievements(client, session):
    from datetime import date, timedelta

    from app.models import Season

    erik = make_user(session, is_admin=True)
    lisa = make_user(session, username="lisa")
    lauf = make_category(session, name="Laufen", icon="laufen", factor=1.0)
    rad = make_category(session, name="Radfahren", icon="rad", factor=0.25)
    start = date.today()  # Challenge startet heute -> Warm-up abgeschlossen
    session.add(Season(year=date.today().year, goal_km=1000,
                       start_date=start, milestones_json="[]"))
    d = start - timedelta(days=2)
    session.add(Activity(user_id=erik.id, category_id=lauf.id, date=d, distance_km=20))
    session.add(Activity(user_id=lisa.id, category_id=rad.id, date=d, distance_km=100))
    session.commit()
    login(client)
    r = client.get("/api/achievements/warmup")
    assert r.status_code == 200
    body = r.json()
    by_key = {a["key"]: a for a in body["achievements"]}
    assert by_key["warmup_laeufer"]["winners"][0]["display_name"] == "Erik"
    # Guter Start: gewertete km — Erik 20*1.0=20, Lisa 100*0.25=25
    assert by_key["guter_start"]["winners"][0]["display_name"] == "Lisa"
    assert by_key["guter_start"]["winners"][0]["km"] == 25.0
    assert "warmup_schwimmer" not in by_key  # keine Schwimm-Aktivität
    assert body["final"] is True


def test_warmup_achievements_ohne_startdatum_leer(client, session):
    make_user(session)
    login(client)
    r = client.get("/api/achievements/warmup")
    assert r.status_code == 200
    assert r.json() == {"final": False, "start_date": None, "achievements": []}


def test_neue_achievements_in_liste_und_maskierung(client, session):
    make_user(session)
    login(client)
    a = {x["key"]: x for x in client.get("/api/achievements").json()}
    # Stufen mit tier/discipline
    assert a["stufe_rad_gold"]["tier"] == "gold"
    assert a["stufe_rad_gold"]["discipline"] == "rad"
    assert a["stufe_rad_gold"]["achieved"] is False
    # Hidden maskiert: Titel ???, keine Parts, kein Fortschritt
    assert a["kletterkoenig"]["hidden"] is True
    assert a["kletterkoenig"]["title"] == "???"
    assert a["kletterkoenig"]["parts"] == []
    assert a["kletterkoenig"]["progress"] == 0.0
    # Einmal-Achievements vorhanden, noch unvergeben
    assert a["erster_gold_rad"]["claimed_by"] is None
    assert a["erster_gold_rad"]["emoji"] == "🚴"
    assert a["testphasen_sieger"]["achieved"] is False
    # Bestands-Achievements unverändert dabei
    assert "ironman" in a


def test_fruehstarter_sichtbar_mit_warmup_fortschritt(client, session):
    from datetime import timedelta

    from app.models import Season

    user = make_user(session)
    lauf = make_category(session, name="Laufen", icon="laufen", factor=2.0)
    start = date.today() + timedelta(days=5)  # Warm-up läuft noch
    session.add(Season(year=start.year, goal_km=1000,
                       start_date=start, milestones_json="[]"))
    session.commit()
    add_activity(session, user, lauf, 25.0, d=date.today() - timedelta(days=1))  # 50 MM
    login(client)
    a = {x["key"]: x for x in client.get("/api/achievements").json()}
    f = a["fruehstarter"]
    assert f["hidden"] is False
    assert f["title"] == "Frühstarter"
    assert f["achieved"] is False
    assert f["progress"] == 0.5
    assert f["parts"] == [{"label": "Warm-up", "current_km": 50.0, "target_km": 100.0}]
    assert f["emoji"] == "🔥"
    # über die Schwelle: Unlock beim nächsten Abruf
    add_activity(session, user, lauf, 26.0, d=date.today())  # gesamt 102 MM
    a = {x["key"]: x for x in client.get("/api/achievements").json()}
    assert a["fruehstarter"]["achieved"] is True
    assert a["fruehstarter"]["progress"] == 1.0
    assert a["fruehstarter"]["unlocked_at"] is not None


def test_fruehstarter_ohne_season_ohne_fortschritt(client, session):
    make_user(session)
    login(client)
    a = {x["key"]: x for x in client.get("/api/achievements").json()}
    assert a["fruehstarter"]["achieved"] is False
    assert a["fruehstarter"]["progress"] == 0.0


def test_hidden_wird_nach_unlock_aufgedeckt(client, session):
    from app.models import Activity

    user = make_user(session)
    rad = make_category(session, name="Radfahren", icon="rad")
    session.add(Activity(user_id=user.id, category_id=rad.id,
                         date=date(2026, 8, 1), distance_km=30.0, elevation_m=1200.0))
    session.commit()
    login(client)
    a = {x["key"]: x for x in client.get("/api/achievements").json()}
    assert a["kletterkoenig"]["achieved"] is True
    assert a["kletterkoenig"]["title"] == "Kletterkönig"
    assert a["kletterkoenig"]["emoji"] == "🏔️"
    assert a["kletterkoenig"]["showcased"] is True
    assert a["kletterkoenig"]["unlocked_at"] is not None


def test_claimed_by_zeigt_namen_der_anderen_person(client, session):
    from app.models import Activity
    from app.services.achievements import check_unlocks

    make_user(session)
    lisa = make_user(session, username="lisa")
    rad = make_category(session, name="Radfahren", icon="rad")
    session.add(Activity(user_id=lisa.id, category_id=rad.id,
                         date=date(2026, 8, 1), distance_km=4000.0))
    session.commit()
    check_unlocks(session, lisa.id)
    login(client)  # als erik
    a = {x["key"]: x for x in client.get("/api/achievements").json()}
    assert a["erster_gold_rad"]["achieved"] is False
    assert a["erster_gold_rad"]["claimed_by"] == "Lisa"


def test_showcase_toggle(client, session):
    from app.models import Activity

    user = make_user(session)
    rad = make_category(session, name="Radfahren", icon="rad")
    session.add(Activity(user_id=user.id, category_id=rad.id,
                         date=date(2026, 8, 1), distance_km=30.0, elevation_m=1200.0))
    session.commit()
    login(client)
    client.get("/api/achievements")  # löst check_unlocks aus
    r = client.patch("/api/achievements/kletterkoenig", json={"showcased": False})
    assert r.status_code == 200
    assert r.json() == {"key": "kletterkoenig", "showcased": False}
    a = {x["key"]: x for x in client.get("/api/achievements").json()}
    assert a["kletterkoenig"]["showcased"] is False
    # fremder/fehlender Unlock → 404
    assert client.patch("/api/achievements/wochenkoenig",
                        json={"showcased": False}).status_code == 404
