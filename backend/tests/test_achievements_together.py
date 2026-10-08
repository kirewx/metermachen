"""Together-Achievements (Spec 2026-10-05 §3.3): Trainingspartner, Dream
Team, Rudel, Social Butterfly — gezählt über echte Sessions (>= 2 bestätigte
Teilnahmen) mit eigener `confirmed`-Teilnahme, nur bei aktivem Add-on."""

import pytest
from sqlmodel import select

from app.models import (
    AchievementUnlock,
    Activity,
    ActivityTrack,
    SessionParticipant,
    TrainingSession,
)
from app.services import together
from app.services.achievements import check_unlocks
from tests.conftest import login, make_addon, make_category, make_user
from tests.test_together import T0, encode_polyline, path


def keys_of(session, user):
    return {
        u.key
        for u in session.exec(
            select(AchievementUnlock).where(AchievementUnlock.user_id == user.id)
        ).all()
    }


def make_training_session(session, *participants, source="auto", km=5.0):
    """`participants`: [(user, status), ...]. Legt die Session samt
    Teilnahmen direkt an (kein Matching nötig für Schwellenwert-Tests)."""
    ts = TrainingSession(source=source, km_together=km)
    session.add(ts)
    session.commit()
    session.refresh(ts)
    for user, status in participants:
        session.add(SessionParticipant(
            session_id=ts.id, user_id=user.id, status=status, km_together=km,
        ))
    session.commit()
    return ts


@pytest.fixture
def addon(session):
    return make_addon(session, key="together", label="Zusammen", enabled=True)


# --- together_first ----------------------------------------------------


def test_together_first_needs_real_session(session, addon):
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    # Nur eine bestätigte Teilnahme -> nicht echt
    make_training_session(session, (erik, "confirmed"))
    check_unlocks(session, erik.id)
    assert "together_first" not in keys_of(session, erik)

    make_training_session(session, (erik, "confirmed"), (anna, "confirmed"))
    check_unlocks(session, erik.id)
    assert "together_first" in keys_of(session, erik)


def test_declined_and_suggested_dont_make_it_real(session, addon):
    erik, anna, bo = (
        make_user(session, "erik"), make_user(session, "anna"), make_user(session, "bo")
    )
    # Eine bestätigte, eine abgelehnte -> nicht echt
    make_training_session(session, (erik, "confirmed"), (anna, "declined"))
    check_unlocks(session, erik.id)
    assert "together_first" not in keys_of(session, erik)

    # Eine bestätigte, eine nur vorgeschlagene -> nicht echt
    make_training_session(session, (erik, "confirmed"), (bo, "suggested"))
    check_unlocks(session, erik.id)
    assert "together_first" not in keys_of(session, erik)


def test_together_first_both_participants_after_auto_match(session, addon):
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    n = [1]

    def act(user):
        n[0] += 1
        cat = make_category(session, name=f"Lauf-{n[0]}")
        a = Activity(
            user_id=user.id, category_id=cat.id, date=T0.date(), distance_km=5.0,
            source="strava", external_id=f"tt{n[0]}",
        )
        session.add(a)
        session.commit()
        session.refresh(a)
        session.add(ActivityTrack(
            activity_id=a.id, start_utc=T0, elapsed_s=1800,
            polyline=encode_polyline(path([("N", 5.0)])),
        ))
        session.commit()
        return a

    e = act(erik)
    together.match_activity(session, e)
    a = act(anna)
    together.match_activity(session, a)  # löst echten Match + Achievements aus

    assert "together_first" in keys_of(session, erik)
    assert "together_first" in keys_of(session, anna)


# --- together_dream_team -------------------------------------------------


def test_together_dream_team_threshold(session, addon):
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    for _ in range(9):
        make_training_session(session, (erik, "confirmed"), (anna, "confirmed"))
    check_unlocks(session, erik.id)
    assert "together_dream_team" not in keys_of(session, erik)

    make_training_session(session, (erik, "confirmed"), (anna, "confirmed"))
    check_unlocks(session, erik.id)
    assert "together_dream_team" in keys_of(session, erik)


# --- together_pack -------------------------------------------------------


def test_together_pack_threshold(session, addon):
    erik, anna, bo, cat_ = (
        make_user(session, "erik"), make_user(session, "anna"),
        make_user(session, "bo"), make_user(session, "cat_"),
    )
    make_training_session(
        session, (erik, "confirmed"), (anna, "confirmed"), (bo, "confirmed"),
    )
    check_unlocks(session, erik.id)
    assert "together_pack" not in keys_of(session, erik)

    make_training_session(
        session, (erik, "confirmed"), (anna, "confirmed"), (bo, "confirmed"),
        (cat_, "confirmed"),
    )
    check_unlocks(session, erik.id)
    assert "together_pack" in keys_of(session, erik)


# --- together_social_butterfly -------------------------------------------


def test_together_social_butterfly_threshold(session, addon):
    erik = make_user(session, "erik")
    partners = [make_user(session, f"p{i}") for i in range(4)]
    for p in partners:
        make_training_session(session, (erik, "confirmed"), (p, "confirmed"))
    check_unlocks(session, erik.id)
    assert "together_social_butterfly" not in keys_of(session, erik)

    fifth = make_user(session, "p5")
    make_training_session(session, (erik, "confirmed"), (fifth, "confirmed"))
    check_unlocks(session, erik.id)
    assert "together_social_butterfly" in keys_of(session, erik)


# --- Add-on aus -----------------------------------------------------------


def test_no_unlock_without_addon(session):
    """Kein `together`-Add-on geseedet -> keine Together-Achievements."""
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    make_training_session(session, (erik, "confirmed"), (anna, "confirmed"))
    check_unlocks(session, erik.id)
    assert "together_first" not in keys_of(session, erik)


def test_together_achievements_not_in_api_when_addon_off(client, session):
    make_user(session)
    login(client)
    body = client.get("/api/achievements").json()
    assert "together_first" not in {a["key"] for a in body}


def test_together_achievements_in_api_when_addon_on(client, session, addon):
    make_user(session)
    login(client)
    body = client.get("/api/achievements").json()
    by_key = {a["key"]: a for a in body}
    assert {
        "together_first", "together_dream_team", "together_pack",
        "together_social_butterfly",
    } <= set(by_key)
    first = by_key["together_first"]
    assert first["title"] == "Trainingspartner"
    assert first["description"] == "Zum ersten Mal gemeinsam unterwegs gewesen."
    assert first["icon"] == "medaille"
    assert first["emoji"] == "🤝"
    assert first["achieved"] is False
    assert "claimed_by" not in first or first["claimed_by"] is None
