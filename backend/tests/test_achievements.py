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
        "startschuss", "marathon", "aermelkanal", "transalp", "ironman", "tausender"
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
