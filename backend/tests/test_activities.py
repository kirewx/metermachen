from datetime import date, timedelta

from tests.conftest import login, make_category, make_user


def create_activity(client, cat_id, **overrides):
    body = {"category_id": cat_id, "date": "2026-03-01", "distance_km": 5.0}
    body.update(overrides)
    return client.post("/api/activities", json=body)


def test_create_and_list_with_scaled_km(client, session):
    make_user(session)
    cat = make_category(session, factor=4.0)
    login(client)
    r = create_activity(client, cat.id, note="Feierabendrunde")
    assert r.status_code == 201
    assert r.json()["scaled_km"] == 20.0
    assert r.json()["edited"] is False
    # Manuelle Aktivität: keine Höhenmeter, kein Strava-Link.
    assert r.json()["elevation_m"] is None
    assert r.json()["strava_url"] is None
    r = client.get("/api/activities", params={"year": 2026})
    assert len(r.json()) == 1
    assert client.get("/api/activities", params={"year": 2025}).json() == []


def test_validation_rules(client, session):
    make_user(session)
    cat = make_category(session)
    inactive = make_category(session, name="Alt", factor=2.0, is_active=False)
    login(client)
    assert create_activity(client, cat.id, distance_km=-1).status_code == 422
    future = (date.today() + timedelta(days=1)).isoformat()
    assert create_activity(client, cat.id, date=future).status_code == 422
    assert create_activity(client, inactive.id).status_code == 422
    assert create_activity(client, 999).status_code == 422


def test_patch_sets_edited_flag_and_rescales(client, session):
    make_user(session)
    cat = make_category(session, factor=4.0)
    login(client)
    act_id = create_activity(client, cat.id).json()["id"]
    r = client.patch(f"/api/activities/{act_id}", json={"distance_km": 10.0})
    assert r.status_code == 200
    assert r.json()["scaled_km"] == 40.0
    assert r.json()["edited"] is True


def test_cannot_touch_foreign_activities(client, session):
    make_user(session)
    make_user(session, username="lisa")
    cat = make_category(session)
    login(client)
    act_id = create_activity(client, cat.id).json()["id"]
    client.post("/api/auth/logout")
    login(client, username="lisa")
    assert (
        client.patch(f"/api/activities/{act_id}", json={"distance_km": 1}).status_code
        == 404
    )
    assert client.delete(f"/api/activities/{act_id}").status_code == 404
    assert client.get("/api/activities", params={"year": 2026}).json() == []


def test_delete_own_activity(client, session):
    make_user(session)
    cat = make_category(session)
    login(client)
    act_id = create_activity(client, cat.id).json()["id"]
    assert client.delete(f"/api/activities/{act_id}").status_code == 204
    assert client.get("/api/activities", params={"year": 2026}).json() == []


def test_patch_ignores_null_for_required_fields_but_clears_note(client, session):
    make_user(session)
    cat = make_category(session, factor=4.0)
    login(client)
    act_id = create_activity(client, cat.id, note="alt").json()["id"]
    r = client.patch(
        f"/api/activities/{act_id}", json={"distance_km": None, "note": None}
    )
    assert r.status_code == 200
    assert r.json()["distance_km"] == 5.0
    assert r.json()["note"] is None


def test_manual_activity_has_source_manual(client, session):
    make_user(session)
    cat = make_category(session, factor=4.0)
    login(client)
    r = create_activity(client, cat.id)
    assert r.status_code == 201
    assert r.json()["source"] == "manual"


def test_start_time_roundtrip(client, session):
    make_user(session)
    cat = make_category(session)
    login(client)
    r = client.post("/api/activities", json={
        "category_id": cat.id, "date": "2026-07-01", "distance_km": 5.0,
        "start_time": "07:30",
    })
    assert r.status_code == 201, r.text
    assert r.json()["start_time"] == "07:30:00"
    act_id = r.json()["id"]
    # Patch ohne Angabe lässt die Zeit unangetastet
    r = client.patch(f"/api/activities/{act_id}", json={"distance_km": 6.0})
    assert r.json()["start_time"] == "07:30:00"
    # explizit null = Zeit löschen
    r = client.patch(f"/api/activities/{act_id}", json={"start_time": None})
    assert r.json()["start_time"] is None


def test_start_time_ist_optional(client, session):
    make_user(session)
    cat = make_category(session)
    login(client)
    r = client.post("/api/activities", json={
        "category_id": cat.id, "date": "2026-07-01", "distance_km": 5.0,
    })
    assert r.status_code == 201, r.text
    assert r.json()["start_time"] is None


def test_liste_zeigt_saison_fenster_ueber_jahresgrenze(client, session):
    from datetime import date

    from app.models import Activity, Season

    user = make_user(session)
    cat = make_category(session)
    session.add(Season(year=2026, goal_km=1000, milestones_json="[]",
                       start_date=date(2026, 7, 1), end_date=date(2027, 5, 16)))
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2027, 1, 15), distance_km=10))  # im Fenster
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2027, 6, 1), distance_km=5))  # nach dem Ende
    session.commit()
    login(client)
    r = client.get("/api/activities?year=2026")
    daten = [a["date"] for a in r.json()]
    assert "2027-01-15" in daten
    assert "2027-06-01" not in daten


def test_hoehenmeter_manuell_erfassen_und_korrigieren(client, session):
    make_user(session)
    cat = make_category(session, factor=4.0)
    login(client)
    r = create_activity(client, cat.id, elevation_m=420.5)
    assert r.status_code == 201, r.text
    assert r.json()["elevation_m"] == 420.5
    act_id = r.json()["id"]
    r = client.patch(f"/api/activities/{act_id}", json={"elevation_m": 500.0})
    assert r.json()["elevation_m"] == 500.0
    # explizit leeren ist erlaubt — sonst bliebe ein Tippfehler für immer stehen
    r = client.patch(f"/api/activities/{act_id}", json={"elevation_m": None})
    assert r.json()["elevation_m"] is None


def test_hoehenmeter_duerfen_nicht_negativ_sein(client, session):
    make_user(session)
    cat = make_category(session)
    login(client)
    assert create_activity(client, cat.id, elevation_m=-10).status_code == 422


def _swimming_with_cutover(session):
    """Swimming counts x30, from 2026-09-01 on only x25."""
    from app.models import CategoryFactorChange

    cat = make_category(session, name="Schwimmen", factor=30.0, icon="schwimmen")
    session.add(
        CategoryFactorChange(category_id=cat.id, factor=25.0, valid_from=date(2026, 9, 1))
    )
    session.commit()
    return cat


def test_scaled_km_uses_factor_valid_on_activity_date(client, session):
    # Regression: create/list multiplied with the stored base factor, so the
    # activity lists showed "2.0 -> 60.0" after the cutover while the totals
    # already counted x25.
    make_user(session)
    cat = _swimming_with_cutover(session)
    login(client)
    before = create_activity(client, cat.id, date="2026-08-31", distance_km=2.0)
    after = create_activity(client, cat.id, date="2026-09-01", distance_km=2.0)
    assert before.json()["scaled_km"] == 60.0
    assert after.json()["scaled_km"] == 50.0
    listed = client.get("/api/activities", params={"year": 2026}).json()
    assert {a["date"]: a["scaled_km"] for a in listed} == {
        "2026-08-31": 60.0,
        "2026-09-01": 50.0,
    }


def test_patch_rescales_with_factor_of_new_date(client, session):
    make_user(session)
    cat = _swimming_with_cutover(session)
    login(client)
    act_id = create_activity(client, cat.id, date="2026-08-31", distance_km=2.0).json()["id"]
    r = client.patch(f"/api/activities/{act_id}", json={"date": "2026-09-01"})
    assert r.status_code == 200, r.text
    assert r.json()["scaled_km"] == 50.0


# --- Together: Partner taggen (Spec 2026-10-05, 2.5) --------------------------


def _together_setup(session):
    from tests.conftest import make_addon

    make_addon(session, key="together", label="Zusammen")
    erik, anna, tom = (make_user(session, n) for n in ("erik", "anna", "tom"))
    return erik, anna, tom, make_category(session)


def _parts(session):
    from sqlmodel import select

    from app.models import SessionParticipant

    return session.exec(select(SessionParticipant)).all()


def test_tag_creates_manual_session(client, session):
    from sqlmodel import select

    from app.models import FeedEvent, TrainingSession

    erik, anna, _, cat = _together_setup(session)
    login(client)
    r = create_activity(client, cat.id, partner_ids=[anna.id])
    assert r.status_code == 201, r.text

    [ts] = session.exec(select(TrainingSession)).all()
    assert ts.source == "manual"
    by_user = {p.user_id: p for p in _parts(session)}
    assert by_user[erik.id].status == "confirmed"
    assert by_user[erik.id].activity_id == r.json()["id"]
    assert by_user[anna.id].status == "suggested"
    assert by_user[anna.id].activity_id is None
    assert session.exec(select(FeedEvent).where(FeedEvent.type == "together")).all() == []


def test_create_without_partners_creates_no_session(client, session):
    *_, cat = _together_setup(session)
    login(client)
    assert create_activity(client, cat.id).status_code == 201
    assert create_activity(client, cat.id, partner_ids=[]).status_code == 201
    assert _parts(session) == []


def test_cannot_tag_opted_out_or_inactive_user_400(client, session):
    _, anna, tom, cat = _together_setup(session)
    anna.detect_together = False
    tom.is_active = False
    session.add_all([anna, tom])
    session.commit()
    login(client)
    for pid in (anna.id, tom.id, 99999):
        r = create_activity(client, cat.id, partner_ids=[pid])
        assert r.status_code == 400, r.text
    # Atomar: bei Fehler wird auch die Aktivität nicht angelegt
    assert client.get("/api/activities", params={"year": 2026}).json() == []
    assert _parts(session) == []


def test_cannot_tag_self_400(client, session):
    erik, _, _, cat = _together_setup(session)
    login(client)
    r = create_activity(client, cat.id, partner_ids=[erik.id])
    assert r.status_code == 400
    assert client.get("/api/activities", params={"year": 2026}).json() == []


def test_tag_with_addon_off_404(client, session):
    make_user(session)
    anna = make_user(session, "anna")
    cat = make_category(session)
    login(client)
    assert create_activity(client, cat.id, partner_ids=[anna.id]).status_code == 404
    assert create_activity(client, cat.id, partner_ids=[]).status_code == 201


def test_patch_removes_suggested_tag_keeps_confirmed(client, session):
    from app.models import Activity
    from app.services import together

    erik, anna, tom, cat = _together_setup(session)
    login(client)
    act_id = create_activity(client, cat.id, partner_ids=[anna.id, tom.id]).json()["id"]
    toms = Activity(user_id=tom.id, category_id=cat.id, date=date(2026, 3, 1), distance_km=4.0)
    session.add(toms)
    session.commit()
    p_tom = next(p for p in _parts(session) if p.user_id == tom.id)
    together.confirm(session, p_tom, activity_id=toms.id)

    r = client.patch(f"/api/activities/{act_id}", json={"partner_ids": []})
    assert r.status_code == 200, r.text
    session.expire_all()
    by_user = {p.user_id: p for p in _parts(session)}
    assert set(by_user) == {erik.id, tom.id}
    assert by_user[tom.id].status == "confirmed"


def test_patch_without_partner_ids_keeps_tags(client, session):
    _, anna, _, cat = _together_setup(session)
    login(client)
    act_id = create_activity(client, cat.id, partner_ids=[anna.id]).json()["id"]
    r = client.patch(f"/api/activities/{act_id}", json={"note": "Gym"})
    assert r.status_code == 200
    assert r.json()["note"] == "Gym"
    assert len(_parts(session)) == 2


def test_patch_adds_partner(client, session, monkeypatch):
    from app.services import together

    calls = []
    monkeypatch.setattr(together, "notify", lambda uid, kind, payload: calls.append((uid, kind)))
    erik, anna, tom, cat = _together_setup(session)
    login(client)
    act_id = create_activity(client, cat.id).json()["id"]
    r = client.patch(f"/api/activities/{act_id}", json={"partner_ids": [anna.id, tom.id]})
    assert r.status_code == 200
    session.expire_all()
    by_user = {p.user_id: p for p in _parts(session)}
    assert set(by_user) == {erik.id, anna.id, tom.id}
    assert by_user[erik.id].status == "confirmed"
    assert by_user[anna.id].status == "suggested"
    assert by_user[tom.id].status == "suggested"
    assert sorted(calls) == sorted([(anna.id, "together_tagged"), (tom.id, "together_tagged")])


def test_patch_with_addon_off_and_empty_list_keeps_tags(client, session):
    from sqlmodel import select

    from app.models import AddOn

    _, anna, _, cat = _together_setup(session)
    login(client)
    act_id = create_activity(client, cat.id, partner_ids=[anna.id]).json()["id"]
    addon = session.exec(select(AddOn).where(AddOn.key == "together")).one()
    addon.enabled = False
    session.add(addon)
    session.commit()
    r = client.patch(f"/api/activities/{act_id}", json={"partner_ids": []})
    assert r.status_code == 200, r.text
    assert len(_parts(session)) == 2


def test_patch_declined_own_participation_400_before_saving(client, session):
    from app.models import Activity

    _, anna, tom, cat = _together_setup(session)
    login(client)
    act_id = create_activity(client, cat.id, partner_ids=[anna.id], note="alt").json()["id"]
    own = next(p for p in _parts(session) if p.activity_id == act_id)
    own.status = "declined"
    session.add(own)
    session.commit()
    r = client.patch(
        f"/api/activities/{act_id}", json={"note": "neu", "partner_ids": [anna.id, tom.id]}
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "Eigene Teilnahme ist abgelehnt"
    session.expire_all()
    assert session.get(Activity, act_id).note == "alt"
    assert {p.user_id for p in _parts(session)} == {own.user_id, anna.id}
