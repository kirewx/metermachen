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
