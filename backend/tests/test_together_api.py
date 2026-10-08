"""API-Tests für Together (Spec 2026-10-05, 4.3): Vorschläge, Bestätigen/
Ablehnen, Partner-Statistik und Opt-out."""

from datetime import date

import pytest
from sqlmodel import select

from app.models import Category, SessionParticipant, TrainingSession
from tests.conftest import login, make_addon, make_category, make_user
from tests.test_together import _part, _tag, manual


def _addon(session):
    return make_addon(session, key="together", label="Zusammen", enabled=True)


# --- Add-on aus -----------------------------------------------------------


def test_together_endpoints_404_when_addon_off(client, session):
    make_user(session, "erik")
    login(client, "erik")
    assert client.get("/api/together/suggestions").status_code == 404
    assert client.post("/api/together/participants/1/confirm", json={}).status_code == 404
    assert client.post("/api/together/participants/1/decline").status_code == 404
    assert client.get("/api/together/partners/1").status_code == 404


# --- Vorschläge -------------------------------------------------------------


def test_suggestions_lists_tag_with_candidates(client, session):
    _addon(session)
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    e = manual(session, erik)
    _tag(session, e, [anna])
    own_candidate = manual(session, anna, day=e.date)

    login(client, "anna")
    r = client.get("/api/together/suggestions")
    assert r.status_code == 200
    [sug] = r.json()
    assert sug["source"] == "manual"
    assert sug["partners"] == [{"user_id": erik.id, "display_name": "Erik"}]
    assert sug["my_activity"] is None
    assert [c["id"] for c in sug["candidates"]] == [own_candidate.id]
    cat = session.get(Category, e.category_id)
    assert sug["partner_activity"] == {
        "category_name": cat.name,
        "date": str(e.date),
        "duration_min": e.duration_min,
        "distance_km": e.distance_km,
    }


def test_suggestions_with_own_activity_has_no_candidates(client, session):
    _addon(session)
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    e = manual(session, erik, km=20.0)
    a = manual(session, anna, km=8.0)
    ts = TrainingSession(source="auto", km_together=3.0, share=0.4)
    session.add(ts)
    session.commit()
    session.add_all([
        SessionParticipant(
            session_id=ts.id, user_id=erik.id, activity_id=e.id,
            status="confirmed", km_together=3.0,
        ),
        SessionParticipant(
            session_id=ts.id, user_id=anna.id, activity_id=a.id,
            status="suggested", km_together=3.0,
        ),
    ])
    session.commit()

    login(client, "anna")
    [sug] = client.get("/api/together/suggestions").json()
    assert sug["my_activity"]["id"] == a.id
    assert sug["candidates"] == []
    assert sug["km_together"] == pytest.approx(3.0)


# --- Bestätigen / Ablehnen --------------------------------------------------


def test_confirm_success_and_foreign_404(client, session):
    _addon(session)
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    e = manual(session, erik)
    _tag(session, e, [anna])
    anna_act = manual(session, anna, day=e.date)
    p_anna = _part(session, anna)

    login(client, "erik")
    r = client.post(
        f"/api/together/participants/{p_anna.id}/confirm",
        json={"activity_id": anna_act.id},
    )
    assert r.status_code == 404

    login(client, "anna")
    r = client.post(
        f"/api/together/participants/{p_anna.id}/confirm",
        json={"activity_id": anna_act.id},
    )
    assert r.status_code == 204
    session.refresh(p_anna)
    assert p_anna.status == "confirmed"
    assert p_anna.activity_id == anna_act.id


def test_confirm_without_activity_returns_400(client, session):
    _addon(session)
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    e = manual(session, erik)
    _tag(session, e, [anna])
    p_anna = _part(session, anna)

    login(client, "anna")
    r = client.post(f"/api/together/participants/{p_anna.id}/confirm", json={})
    assert r.status_code == 400
    assert r.json()["detail"] == "Bitte eine eigene Aktivität wählen"


def test_decline_success_and_foreign_404(client, session):
    _addon(session)
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    e = manual(session, erik)
    _tag(session, e, [anna])
    p_anna = _part(session, anna)

    login(client, "erik")
    assert (
        client.post(f"/api/together/participants/{p_anna.id}/decline").status_code
        == 404
    )

    login(client, "anna")
    assert (
        client.post(f"/api/together/participants/{p_anna.id}/decline").status_code
        == 204
    )
    session.refresh(p_anna)
    assert p_anna.status == "declined"


# --- Partner-Statistik -------------------------------------------------------


def test_partners_counts_only_real_sessions_and_sorts(client, session):
    _addon(session)
    erik, anna, tom = (make_user(session, n) for n in ("erik", "anna", "tom"))
    for i in range(2):  # zwei echte Sessions mit Anna
        ts = TrainingSession(source="auto", km_together=5.0 + i)
        session.add(ts)
        session.commit()
        session.add_all([
            SessionParticipant(
                session_id=ts.id, user_id=erik.id, status="confirmed", km_together=5.0 + i
            ),
            SessionParticipant(
                session_id=ts.id, user_id=anna.id, status="confirmed", km_together=5.0 + i
            ),
        ])
        session.commit()
    ts_tom = TrainingSession(source="auto", km_together=2.0)  # nicht echt (nur 1 bestätigt)
    session.add(ts_tom)
    session.commit()
    session.add_all([
        SessionParticipant(
            session_id=ts_tom.id, user_id=erik.id, status="confirmed", km_together=2.0
        ),
        SessionParticipant(
            session_id=ts_tom.id, user_id=tom.id, status="suggested", km_together=2.0
        ),
    ])
    session.commit()

    login(client, "erik")
    r = client.get(f"/api/together/partners/{erik.id}")
    assert r.status_code == 200
    data = r.json()
    assert [d["user_id"] for d in data] == [anna.id]
    assert data[0]["display_name"] == "Anna"
    assert data[0]["sessions"] == 2
    assert data[0]["km_together"] == pytest.approx(11.0)


# --- Opt-out -----------------------------------------------------------------


def test_patch_me_detect_together_opt_out(client, session):
    make_user(session, "erik")
    login(client, "erik")
    r = client.patch("/api/users/me", json={"detect_together": False})
    assert r.status_code == 200
    assert r.json()["detect_together"] is False
    me = client.get("/api/auth/me")
    assert me.json()["detect_together"] is False


# --- Badge auf ActivityOut ---------------------------------------------------


def test_activity_list_includes_together_partners(client, session):
    _addon(session)
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    today = date.today()
    e = manual(session, erik, day=today)
    a = manual(session, anna, day=today)
    ts = TrainingSession(source="auto", km_together=4.0, share=1.0)
    session.add(ts)
    session.commit()
    session.add_all([
        SessionParticipant(
            session_id=ts.id, user_id=erik.id, activity_id=e.id,
            status="confirmed", km_together=4.0,
        ),
        SessionParticipant(
            session_id=ts.id, user_id=anna.id, activity_id=a.id,
            status="confirmed", km_together=4.0,
        ),
    ])
    session.commit()

    login(client, "erik")
    r = client.get(f"/api/activities?year={today.year}")
    assert r.status_code == 200
    [out] = [x for x in r.json() if x["id"] == e.id]
    assert out["together"]["status"] == "confirmed"
    assert out["together"]["partners"] == [{"user_id": anna.id, "display_name": "Anna"}]
    assert out["together"]["km_together"] == pytest.approx(4.0)


def _session_with(session, rows, source="auto"):
    """TrainingSession mit Teilnahmen [(user, activity|None, status)]."""
    ts = TrainingSession(source=source, km_together=4.0, share=1.0)
    session.add(ts)
    session.commit()
    for user, act, status in rows:
        session.add(SessionParticipant(
            session_id=ts.id, user_id=user.id,
            activity_id=act.id if act is not None else None,
            status=status, km_together=4.0,
        ))
    session.commit()
    return ts


def _badge(client, url, act_id):
    r = client.get(url)
    assert r.status_code == 200, r.text
    [out] = [x for x in r.json() if x["id"] == act_id]
    return out["together"]


def test_badge_null_when_addon_off(client, session):
    addon = _addon(session)
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    today = date.today()
    e, a = manual(session, erik, day=today), manual(session, anna, day=today)
    _session_with(session, [(erik, e, "confirmed"), (anna, a, "confirmed")])
    addon.enabled = False
    session.add(addon)
    session.commit()
    login(client, "erik")
    assert _badge(client, f"/api/activities?year={today.year}", e.id) is None


def test_badge_null_when_own_declined(client, session):
    _addon(session)
    erik, anna, tom = (make_user(session, n) for n in ("erik", "anna", "tom"))
    today = date.today()
    e, a, t = (manual(session, u, day=today) for u in (erik, anna, tom))
    _session_with(session, [
        (erik, e, "declined"), (anna, a, "confirmed"), (tom, t, "confirmed"),
    ])
    login(client, "erik")
    assert _badge(client, f"/api/activities?year={today.year}", e.id) is None


def test_badge_other_profile_hides_suggested(client, session):
    _addon(session)
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    today = date.today()
    e, a = manual(session, erik, day=today), manual(session, anna, day=today)
    _session_with(session, [(erik, e, "suggested"), (anna, a, "confirmed")])
    make_user(session, "tom")
    login(client, "tom")
    url = f"/api/users/{erik.id}/activities?year={today.year}"
    assert _badge(client, url, e.id) is None
    # eigene Liste: Vorschlag mit nicht abgelehntem Partner bleibt sichtbar
    login(client, "erik")
    own = _badge(client, f"/api/activities?year={today.year}", e.id)
    assert own["status"] == "suggested"


def test_badge_other_profile_shows_real_confirmed(client, session):
    _addon(session)
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    today = date.today()
    e, a = manual(session, erik, day=today), manual(session, anna, day=today)
    ts = _session_with(session, [(erik, e, "confirmed"), (anna, a, "confirmed")])
    make_user(session, "tom")
    login(client, "tom")
    out = _badge(client, f"/api/users/{erik.id}/activities?year={today.year}", e.id)
    assert out["session_id"] == ts.id
    assert out["partners"] == [{"user_id": anna.id, "display_name": "Anna"}]


def test_badge_other_profile_hides_confirmed_but_not_real(client, session):
    _addon(session)
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    today = date.today()
    e = manual(session, erik, day=today)
    _session_with(session, [(erik, e, "confirmed"), (anna, None, "suggested")],
                  source="manual")
    make_user(session, "tom")
    login(client, "tom")
    assert _badge(client, f"/api/users/{erik.id}/activities?year={today.year}", e.id) is None


def test_badge_own_list_null_when_partner_left(client, session):
    _addon(session)
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    today = date.today()
    e = manual(session, erik, day=today)
    _session_with(session, [(erik, e, "confirmed"), (anna, None, "declined")],
                  source="manual")
    login(client, "erik")
    assert _badge(client, f"/api/activities?year={today.year}", e.id) is None


def test_together_map_failure_keeps_list_working(client, session, monkeypatch):
    from app.services import together

    _addon(session)
    erik = make_user(session, "erik")
    today = date.today()
    e = manual(session, erik, day=today)

    def boom(*a, **kw):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(together, "enabled", boom)
    login(client, "erik")
    assert _badge(client, f"/api/activities?year={today.year}", e.id) is None
    assert _badge(client, f"/api/users/{erik.id}/activities?year={today.year}", e.id) is None
