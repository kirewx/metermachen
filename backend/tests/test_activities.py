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
