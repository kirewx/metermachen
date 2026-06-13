from tests.conftest import login, make_category, make_user


def test_list_categories_requires_login(client, session):
    make_category(session)
    assert client.get("/api/categories").status_code == 401


def test_list_categories(client, session):
    make_user(session)
    make_category(session)
    make_category(session, name="Radfahren", factor=1.0, is_active=False)
    login(client)
    r = client.get("/api/categories")
    assert r.status_code == 200
    assert [c["name"] for c in r.json()] == ["Joggen", "Radfahren"]
    assert r.json()[1]["is_active"] is False


def test_create_category_admin_only(client, session):
    make_user(session)
    login(client)
    r = client.post(
        "/api/categories",
        json={"name": "Rudern", "factor": 2.0, "color": "#123456", "icon": "medaille"},
    )
    assert r.status_code == 403


def test_create_and_patch_category_as_admin(client, session):
    make_user(session, username="chef", is_admin=True)
    login(client, username="chef")
    r = client.post(
        "/api/categories",
        json={"name": "Rudern", "factor": 2.0, "color": "#123456", "icon": "medaille"},
    )
    assert r.status_code == 201
    cat_id = r.json()["id"]
    r = client.patch(
        f"/api/categories/{cat_id}", json={"factor": 3.0, "is_active": False}
    )
    assert r.status_code == 200
    assert r.json()["factor"] == 3.0
    assert r.json()["is_active"] is False


def test_patch_category_ignores_explicit_null(client, session):
    make_user(session, username="chef", is_admin=True)
    cat = make_category(session)
    login(client, username="chef")
    r = client.patch(f"/api/categories/{cat.id}", json={"icon": None})
    assert r.status_code == 200
    assert r.json()["icon"] == "laufen"


def test_default_km_anlegen_und_patchen(client, session):
    make_user(session, is_admin=True)
    login(client)
    r = client.post(
        "/api/categories",
        json={"name": "Rudern", "factor": 2.0, "color": "#123456", "icon": "medaille", "default_km": 7.5},
    )
    assert r.status_code == 201
    assert r.json()["default_km"] == 7.5
    cat_id = r.json()["id"]
    r = client.patch(f"/api/categories/{cat_id}", json={"default_km": 12.0})
    assert r.json()["default_km"] == 12.0


def test_default_km_muss_positiv_sein(client, session):
    make_user(session, is_admin=True)
    login(client)
    r = client.post(
        "/api/categories",
        json={"name": "Kaputt", "factor": 1.0, "color": "#123456", "default_km": 0},
    )
    assert r.status_code == 422


def test_create_category_with_strava_sport_types(client, session):
    make_user(session, is_admin=True)
    login(client)
    r = client.post("/api/categories", json={
        "name": "Laufen", "factor": 4.0, "color": "#e74c3c", "icon": "laufen",
        "default_km": 5.0, "strava_sport_types": ["Run", "TrailRun"],
    })
    assert r.status_code == 201, r.text
    assert r.json()["strava_sport_types"] == ["Run", "TrailRun"]


def test_list_categories_returns_sport_types_as_list(client, session):
    make_user(session, is_admin=True)
    make_category(session, name="Rad", factor=1.0, strava_sport_types='["Ride"]')
    login(client)
    r = client.get("/api/categories")
    assert r.status_code == 200
    rad = next(c for c in r.json() if c["name"] == "Rad")
    assert rad["strava_sport_types"] == ["Ride"]


def test_patch_category_updates_sport_types(client, session):
    make_user(session, is_admin=True)
    cat = make_category(session)
    login(client)
    r = client.patch(f"/api/categories/{cat.id}", json={"strava_sport_types": ["Run"]})
    assert r.status_code == 200
    assert r.json()["strava_sport_types"] == ["Run"]
