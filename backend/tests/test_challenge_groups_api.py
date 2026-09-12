"""Group challenge endpoints (spec 2026-09-12)."""

import json
from datetime import date, timedelta

from sqlmodel import select

from app.models import Activity, Challenge
from tests.conftest import login, make_addon, make_category, make_user


def setup(session, n_users=4):
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    admin = make_user(session, username="admin", is_admin=True)
    users = [make_user(session, username=f"u{k}") for k in range(n_users)]
    return admin, users


def team_body(**kw):
    heute = date.today()
    body = {
        "title": "Teams", "mode": "ziel", "target": 100, "metric": "mm",
        "join_mode": "auto", "period_start": str(heute + timedelta(days=1)),
        "period_end": str(heute + timedelta(days=30)),
        "team_mode": True, "group_count": 2, "seeding_days": 30,
    }
    body.update(kw)
    return body


def test_create_auto_team_challenge_draws_immediately(session, client):
    setup(session)
    login(client, username="admin")
    r = client.post("/api/challenges", json=team_body())
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["team_mode"] is True and out["group_count"] == 2
    assert out["groups_drawn"] is True
    assert len(out["groups"]) == 2
    assert sorted(len(g["members"]) for g in out["groups"]) == [2, 3]  # admin + 4 users
    assert out["kann_gruppen_bearbeiten"] is True
    assert out["status"] == "geplant"


def test_create_opt_in_team_challenge_waits_for_draw(session, client):
    setup(session)
    login(client, username="admin")
    r = client.post("/api/challenges", json=team_body(join_mode="opt_in"))
    assert r.status_code == 201, r.text
    assert r.json()["groups_drawn"] is False and r.json()["groups"] == []


def test_create_validates_team_rules(session, client):
    setup(session)
    login(client, username="admin")
    assert client.post("/api/challenges", json=team_body(metric="streak")).status_code == 422
    assert client.post("/api/challenges", json=team_body(group_count=1)).status_code == 422
    assert client.post("/api/challenges", json=team_body(group_count=None)).status_code == 422
    assert client.post("/api/challenges", json=team_body(seeding_days=0)).status_code == 422


def test_create_with_too_few_people_is_422(session, client):
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    make_user(session, username="admin", is_admin=True)
    login(client, username="admin")
    r = client.post("/api/challenges", json=team_body(group_count=3))
    assert r.status_code == 422
    assert session.exec(select(Challenge)).first() is None


def test_draw_and_save_groups_only_while_planned(session, client):
    admin, users = setup(session)
    login(client, username="admin")
    ch_id = client.post("/api/challenges", json=team_body(join_mode="opt_in")).json()["id"]
    assert client.post(f"/api/challenges/{ch_id}/draw").status_code == 422  # nobody joined
    for u in users:
        login(client, username=u.username)
        client.post(f"/api/challenges/{ch_id}/join")
    login(client, username="admin")
    r = client.post(f"/api/challenges/{ch_id}/draw")
    assert r.status_code == 200, r.text
    gruppen = r.json()["groups"]
    assert sorted(len(g["members"]) for g in gruppen) == [2, 2]

    body = {"groups": [
        {"id": 1, "name": "Flitzer", "member_ids": [users[0].id, users[1].id, users[2].id]},
        {"id": 2, "name": "Gruppe B", "member_ids": [users[3].id]},
    ]}
    r = client.put(f"/api/challenges/{ch_id}/groups", json=body)
    assert r.status_code == 200, r.text
    assert {g["name"] for g in r.json()["groups"]} == {"Flitzer", "Gruppe B"}
    assert r.json()["unassigned"] == []

    bad = {"groups": [{"id": 1, "name": "A", "member_ids": [users[0].id, users[0].id]}, body["groups"][1]]}
    assert client.put(f"/api/challenges/{ch_id}/groups", json=bad).status_code == 422

    ch = session.get(Challenge, ch_id)
    ch.status = "laufend"
    session.add(ch)
    session.commit()
    assert client.post(f"/api/challenges/{ch_id}/draw").status_code == 409
    assert client.put(f"/api/challenges/{ch_id}/groups", json=body).status_code == 409


def test_draw_on_non_team_challenge_is_409(session, client):
    setup(session)
    login(client, username="admin")
    ch_id = client.post("/api/challenges", json=team_body(team_mode=False, group_count=None)).json()["id"]
    assert client.post(f"/api/challenges/{ch_id}/draw").status_code == 409
    assert client.get(f"/api/challenges/{ch_id}/seeding").status_code == 409


def test_seeding_lists_every_active_user_with_value(session, client):
    admin, users = setup(session, n_users=2)
    lauf = make_category(session, name="Joggen", factor=1.0)
    session.add(Activity(user_id=users[0].id, category_id=lauf.id, date=date.today() - timedelta(days=1), distance_km=12.0))
    session.commit()
    login(client, username="admin")
    ch_id = client.post("/api/challenges", json=team_body(join_mode="opt_in")).json()["id"]
    r = client.get(f"/api/challenges/{ch_id}/seeding")
    assert r.status_code == 200, r.text
    rows = {e["user_id"]: e for e in r.json()}
    assert set(rows) == {admin.id, users[0].id, users[1].id}
    assert rows[users[0].id]["value"] == 12.0 and rows[users[0].id]["display_name"] == "U0"


def test_seeding_and_draw_need_admin(session, client):
    admin, users = setup(session)
    login(client, username="admin")
    ch_id = client.post("/api/challenges", json=team_body()).json()["id"]
    login(client, username=users[0].username)
    assert client.get(f"/api/challenges/{ch_id}/seeding").status_code == 403
    assert client.post(f"/api/challenges/{ch_id}/draw").status_code == 403
    assert client.put(f"/api/challenges/{ch_id}/groups", json={"groups": []}).status_code == 403


def test_patch_group_count_clears_groups(session, client):
    setup(session)
    login(client, username="admin")
    ch_id = client.post("/api/challenges", json=team_body()).json()["id"]
    r = client.patch(f"/api/challenges/{ch_id}", json={"group_count": 3})
    assert r.status_code == 200, r.text
    assert r.json()["groups_drawn"] is False and r.json()["group_count"] == 3
    r = client.patch(f"/api/challenges/{ch_id}", json={"title": "Neu"})
    assert r.json()["groups_drawn"] is False  # still cleared, no auto redraw


def test_late_joiner_is_unassigned_and_join_blocked_once_running(session, client):
    admin, users = setup(session)
    login(client, username="admin")
    ch_id = client.post("/api/challenges", json=team_body(join_mode="opt_in")).json()["id"]
    for u in users[:2]:
        login(client, username=u.username)
        client.post(f"/api/challenges/{ch_id}/join")
    login(client, username="admin")
    client.post(f"/api/challenges/{ch_id}/draw")
    login(client, username=users[2].username)
    r = client.post(f"/api/challenges/{ch_id}/join")
    assert r.status_code == 200
    assert r.json()["bin_dabei"] is True
    assert [e["user_id"] for e in r.json()["unassigned"]] == [users[2].id]
    assert r.json()["meine_gruppe_id"] is None

    ch = session.get(Challenge, ch_id)
    ch.status = "laufend"
    session.add(ch)
    session.commit()
    login(client, username=users[3].username)
    assert client.post(f"/api/challenges/{ch_id}/join").status_code == 409
    login(client, username=users[0].username)
    assert client.delete(f"/api/challenges/{ch_id}/join").status_code == 409


def test_leaving_planned_team_challenge_removes_from_group(session, client):
    admin, users = setup(session)
    login(client, username="admin")
    ch_id = client.post("/api/challenges", json=team_body(join_mode="opt_in")).json()["id"]
    for u in users[:2]:
        login(client, username=u.username)
        client.post(f"/api/challenges/{ch_id}/join")
    login(client, username="admin")
    client.post(f"/api/challenges/{ch_id}/draw")
    login(client, username=users[0].username)
    r = client.delete(f"/api/challenges/{ch_id}/join")
    assert r.status_code == 200
    assert users[0].id not in [m["user_id"] for g in r.json()["groups"] for m in g["members"]]
    assert r.json()["bin_dabei"] is False


def test_detail_shows_group_standings_and_my_group(session, client):
    admin, users = setup(session, n_users=2)
    lauf = make_category(session, name="Joggen", factor=1.0)
    heute = date.today()
    ch = Challenge(
        title="Teams", creator_id=admin.id, mode="ziel", target=100.0, metric="mm",
        join_mode="auto", period_start=heute - timedelta(days=5), period_end=heute + timedelta(days=5),
        status="laufend", team_mode=True, group_count=2,
        groups_json=json.dumps([
            {"id": 1, "name": "Gruppe A", "member_ids": [admin.id, users[0].id]},
            {"id": 2, "name": "Gruppe B", "member_ids": [users[1].id]},
        ]),
    )
    session.add(ch)
    session.commit()
    session.add(Activity(user_id=users[0].id, category_id=lauf.id, date=heute, distance_km=240.0))
    session.commit()
    login(client, username="u0")
    out = client.get(f"/api/challenges/{ch.id}").json()
    assert out["meine_gruppe_id"] == 1
    a = next(g for g in out["groups"] if g["id"] == 1)
    assert (a["sum"], a["value"], a["size"], a["rank"], a["geschafft"]) == (240.0, 120.0, 2, 1, True)
    assert a["members"][0]["display_name"] == "U0"
    assert out["mein_stand"]["value"] == 240.0
    assert out["kann_gruppen_bearbeiten"] is False
    assert out["gewinner_ids"] == sorted([admin.id, users[0].id]) or set(out["gewinner_ids"]) == {admin.id, users[0].id}


def test_sieger_endpoint_accepts_group_or_person(session, client):
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    anna = make_user(session, username="anna", is_admin=True)
    ben = make_user(session, username="ben")
    carla = make_user(session, username="carla")
    heute = date.today()
    ch = Challenge(
        title="Teams", creator_id=anna.id, mode="ziel", target=100.0, metric="mm",
        join_mode="auto", period_start=heute - timedelta(days=20), period_end=heute - timedelta(days=10),
        status="beendet", team_mode=True, group_count=2,
        groups_json=json.dumps([
            {"id": 1, "name": "Gruppe A", "member_ids": [anna.id, ben.id]},
            {"id": 2, "name": "Gruppe B", "member_ids": [carla.id]},
        ]),
        result_json=json.dumps({
            "entries": [
                {"user_id": anna.id, "value": 150.0, "rank": 1, "geschafft": True},
                {"user_id": ben.id, "value": 70.0, "rank": 3, "geschafft": False},
                {"user_id": carla.id, "value": 90.0, "rank": 2, "geschafft": False},
            ],
            "groups": [
                {"id": 1, "name": "Gruppe A", "member_ids": [anna.id, ben.id], "sum": 220.0, "value": 110.0, "rank": 1, "geschafft": True},
                {"id": 2, "name": "Gruppe B", "member_ids": [carla.id], "sum": 90.0, "value": 90.0, "rank": 2, "geschafft": False},
            ],
            "gewinner_ids": [anna.id, ben.id],
            "gewinner_group_ids": [1],
        }),
    )
    session.add(ch)
    session.commit()
    login(client, username="anna")
    detail = client.get(f"/api/challenges/{ch.id}").json()
    assert detail["kann_sieger_setzen"] is True
    assert [g["id"] for g in detail["groups"]] == [1, 2]
    r = client.put(f"/api/challenges/{ch.id}/sieger", json={"group_id": 1})
    assert r.status_code == 200, r.text
    assert r.json()["sieger_group_id"] == 1 and r.json()["sieger_id"] is None
    r = client.put(f"/api/challenges/{ch.id}/sieger", json={"user_id": ben.id})
    assert r.status_code == 200
    assert r.json()["sieger_id"] == ben.id and r.json()["sieger_group_id"] is None
    assert client.put(f"/api/challenges/{ch.id}/sieger", json={"user_id": carla.id}).status_code == 422
    assert client.put(f"/api/challenges/{ch.id}/sieger", json={"group_id": 2}).status_code == 422
    assert client.put(f"/api/challenges/{ch.id}/sieger", json={}).status_code == 422
    assert client.put(f"/api/challenges/{ch.id}/sieger", json={"user_id": ben.id, "group_id": 1}).status_code == 422
