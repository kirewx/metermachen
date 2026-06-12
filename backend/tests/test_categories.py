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
        json={"name": "Rudern", "factor": 2.0, "color": "#123456", "icon_emoji": "🚣"},
    )
    assert r.status_code == 403


def test_create_and_patch_category_as_admin(client, session):
    make_user(session, username="chef", is_admin=True)
    login(client, username="chef")
    r = client.post(
        "/api/categories",
        json={"name": "Rudern", "factor": 2.0, "color": "#123456", "icon_emoji": "🚣"},
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
    r = client.patch(f"/api/categories/{cat.id}", json={"icon_emoji": None})
    assert r.status_code == 200
    assert r.json()["icon_emoji"] == "🏃"
