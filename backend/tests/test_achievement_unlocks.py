from datetime import date, timedelta

from sqlmodel import select

from app.models import AchievementUnlock, Activity, Season
from app.services.achievements import check_unlocks
from tests.conftest import make_category, make_user


def add_act(session, user, cat, km, d=date(2026, 8, 1), elevation=None):
    session.add(Activity(
        user_id=user.id, category_id=cat.id, date=d, distance_km=km, elevation_m=elevation
    ))
    session.commit()


def keys_of(session, user):
    return {
        u.key
        for u in session.exec(
            select(AchievementUnlock).where(AchievementUnlock.user_id == user.id)
        ).all()
    }


def test_stufen_grenzen(session):
    user = make_user(session)
    lauf = make_category(session, name="Laufen", icon="laufen")
    add_act(session, user, lauf, 249.9)
    check_unlocks(session, user.id)
    assert keys_of(session, user) == set()
    add_act(session, user, lauf, 0.1)  # exakt 250 → Bronze
    check_unlocks(session, user.id)
    assert keys_of(session, user) == {"stufe_lauf_bronze"}
    add_act(session, user, lauf, 750.0)  # 1000 → Silber UND Gold in einem Lauf
    check_unlocks(session, user.id)
    assert {"stufe_lauf_silber", "stufe_lauf_gold"} <= keys_of(session, user)


def test_check_unlocks_ist_idempotent(session):
    user = make_user(session)
    lauf = make_category(session, name="Laufen", icon="laufen")
    add_act(session, user, lauf, 300.0)
    check_unlocks(session, user.id)
    check_unlocks(session, user.id)
    unlocks = session.exec(
        select(AchievementUnlock).where(AchievementUnlock.user_id == user.id)
    ).all()
    assert len(unlocks) == 1


def test_unlock_bleibt_nach_loeschung(session):
    user = make_user(session)
    lauf = make_category(session, name="Laufen", icon="laufen")
    add_act(session, user, lauf, 300.0)
    check_unlocks(session, user.id)
    for act in session.exec(select(Activity)).all():
        session.delete(act)
    session.commit()
    check_unlocks(session, user.id)
    assert "stufe_lauf_bronze" in keys_of(session, user)


def test_erster_bonus_reihenfolge_der_persistierung(session):
    erik = make_user(session)
    lisa = make_user(session, username="lisa")
    lauf = make_category(session, name="Laufen", icon="laufen")
    # Lisa erreicht Gold mit ÄLTEREM Aktivitätsdatum, aber Eriks Unlock wird
    # zuerst persistiert → Erik bekommt den Bonus (Zurückdatieren klaut nichts).
    add_act(session, erik, lauf, 1000.0, d=date(2026, 9, 1))
    check_unlocks(session, erik.id)
    add_act(session, lisa, lauf, 1000.0, d=date(2026, 8, 1))
    check_unlocks(session, lisa.id)
    assert "erster_gold_lauf" in keys_of(session, erik)
    assert "erster_gold_lauf" not in keys_of(session, lisa)
    assert "stufe_lauf_gold" in keys_of(session, lisa)


def test_kletterkoenig_summiert_pro_kalendertag(session):
    user = make_user(session)
    rad = make_category(session, name="Radfahren", icon="rad")
    d = date(2026, 8, 1)
    add_act(session, user, rad, 20.0, d=d, elevation=600.0)
    add_act(session, user, rad, 20.0, d=d + timedelta(days=1), elevation=600.0)
    check_unlocks(session, user.id)
    assert "kletterkoenig" not in keys_of(session, user)  # 600 + 600 an ZWEI Tagen
    add_act(session, user, rad, 20.0, d=d, elevation=400.0)  # Tag 1: 600+400 = 1000
    check_unlocks(session, user.id)
    assert "kletterkoenig" in keys_of(session, user)


def test_hattrick_braucht_drei_eintraege_an_einem_tag(session):
    user = make_user(session)
    lauf = make_category(session, name="Laufen", icon="laufen")
    d = date(2026, 8, 1)
    add_act(session, user, lauf, 5.0, d=d)
    add_act(session, user, lauf, 5.0, d=d)
    add_act(session, user, lauf, 5.0, d=d + timedelta(days=1))
    check_unlocks(session, user.id)
    assert "hattrick" not in keys_of(session, user)
    add_act(session, user, lauf, 5.0, d=d)
    check_unlocks(session, user.id)
    assert "hattrick" in keys_of(session, user)


def make_season(session, start):
    session.add(Season(year=start.year, goal_km=1000.0, start_date=start,
                       milestones_json="[]"))
    session.commit()


def test_wochenkoenig_sieben_tage_allein_vorn(session):
    heute = date.today()
    start = heute - timedelta(days=10)
    make_season(session, start)
    erik = make_user(session)
    lisa = make_user(session, username="lisa")
    lauf = make_category(session, name="Laufen", icon="laufen", factor=1.0)
    # Erik führt ab Tag 0 allein, Lisa bleibt dahinter
    add_act(session, erik, lauf, 50.0, d=start)
    add_act(session, lisa, lauf, 10.0, d=start)
    check_unlocks(session, erik.id)
    assert "wochenkoenig" in keys_of(session, erik)
    check_unlocks(session, lisa.id)
    assert "wochenkoenig" not in keys_of(session, lisa)


def test_wochenkoenig_gleichstand_zaehlt_nicht(session):
    heute = date.today()
    start = heute - timedelta(days=10)
    make_season(session, start)
    erik = make_user(session)
    lisa = make_user(session, username="lisa")
    lauf = make_category(session, name="Laufen", icon="laufen", factor=1.0)
    add_act(session, erik, lauf, 50.0, d=start)
    add_act(session, lisa, lauf, 50.0, d=start)  # Gleichstand über alle Tage
    check_unlocks(session, erik.id)
    assert "wochenkoenig" not in keys_of(session, erik)


def test_wochenkoenig_erst_ab_challenge_start(session):
    heute = date.today()
    start = heute - timedelta(days=3)  # erst 4 Tage Challenge → kein 7-Tage-Fenster
    make_season(session, start)
    erik = make_user(session)
    lauf = make_category(session, name="Laufen", icon="laufen", factor=1.0)
    add_act(session, erik, lauf, 50.0, d=start)
    check_unlocks(session, erik.id)
    assert "wochenkoenig" not in keys_of(session, erik)


def test_testphasen_sieger_nach_start_gleichstand_alle(session):
    heute = date.today()
    start = heute  # Challenge startet heute → Warm-up abgeschlossen
    make_season(session, start)
    erik = make_user(session)
    lisa = make_user(session, username="lisa")
    tom = make_user(session, username="tom")
    lauf = make_category(session, name="Laufen", icon="laufen", factor=2.0)
    d = start - timedelta(days=2)
    add_act(session, erik, lauf, 50.0, d=d)  # 100 gewertet
    add_act(session, lisa, lauf, 50.0, d=d)  # 100 gewertet — Gleichstand
    add_act(session, tom, lauf, 10.0, d=d)   # 20 gewertet
    for u in (erik, lisa, tom):
        check_unlocks(session, u.id)
    assert "testphasen_sieger" in keys_of(session, erik)
    assert "testphasen_sieger" in keys_of(session, lisa)
    assert "testphasen_sieger" not in keys_of(session, tom)


def test_testphasen_sieger_nicht_vor_start(session):
    heute = date.today()
    make_season(session, heute + timedelta(days=5))  # Challenge noch nicht gestartet
    erik = make_user(session)
    lauf = make_category(session, name="Laufen", icon="laufen")
    add_act(session, erik, lauf, 50.0, d=heute - timedelta(days=1))
    check_unlocks(session, erik.id)
    assert keys_of(session, erik) == set()


def test_activity_create_loest_unlock_aus(client, session):
    from tests.conftest import login

    make_user(session)
    lauf = make_category(session, name="Laufen", icon="laufen")
    login(client)
    # Datum = heute: der Endpoint lehnt Zukunftsdaten ab (422)
    r = client.post("/api/activities", json={
        "category_id": lauf.id, "date": date.today().isoformat(), "distance_km": 250.0,
    })
    assert r.status_code == 201
    unlocks = session.exec(select(AchievementUnlock)).all()
    assert {u.key for u in unlocks} == {"stufe_lauf_bronze"}


def test_strava_import_loest_unlock_aus(session):
    from app.models import StravaConnection
    from app.services import strava

    user = make_user(session)
    make_category(session, name="Laufen", icon="laufen", strava_sport_types='["Run"]')
    conn = StravaConnection(user_id=user.id, athlete_id=9, access_token="a",
                            refresh_token="r", expires_at=9999999999)
    session.add(conn)
    session.commit()
    data = {"id": 500, "sport_type": "Run", "distance": 250000.0,
            "start_date_local": "2026-08-01T07:00:00Z", "name": "Ultra"}
    assert strava.import_activity(session, conn, data) is True
    assert "stufe_lauf_bronze" in keys_of(session, user)
