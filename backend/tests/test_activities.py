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
