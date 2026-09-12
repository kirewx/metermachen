"""Group challenges (spec 2026-09-12): helpers, seeding, draw, editing."""

import copy
import json
import random
from datetime import date, datetime, timedelta, timezone

import pytest

from app.models import Activity, Challenge, ChallengeParticipant
from app.services import challenge_groups as cg
from app.services import challenges as svc
from tests.conftest import make_category, make_user


def make_team_challenge(session, **kw) -> Challenge:
    heute = date.today()
    daten = dict(
        title="Teams", creator_id=1, mode="ziel", target=100.0, metric="mm",
        join_mode="auto", period_start=heute + timedelta(days=1),
        period_end=heute + timedelta(days=30), status="geplant",
        team_mode=True, group_count=2, seeding_days=30,
    )
    daten.update(kw)
    ch = Challenge(**daten)
    session.add(ch)
    session.commit()
    session.refresh(ch)
    return ch


def add_activity(session, user_id, cat_id, tag, km):
    session.add(Activity(user_id=user_id, category_id=cat_id, date=tag, distance_km=km))
    session.commit()


def groups_of(*member_lists):
    return [
        {"id": i + 1, "name": f"Gruppe {chr(65 + i)}", "member_ids": list(m)}
        for i, m in enumerate(member_lists)
    ]


# --- JSON helpers -----------------------------------------------------------

def test_group_helpers_read_and_remove(session):
    ch = make_team_challenge(session, groups_json=json.dumps(groups_of([1, 2], [3])))
    assert svc.group_member_ids(ch) == [1, 2, 3]
    svc.remove_group_member(ch, 2)
    assert svc.groups(ch) == groups_of([1], [3])
    svc.remove_group_member(ch, 99)  # unknown id is a no-op
    assert svc.group_member_ids(ch) == [1, 3]


def test_group_of_returns_group_or_none(session):
    ch = make_team_challenge(session, groups_json=json.dumps(groups_of([1, 2], [3])))
    assert svc.group_of(ch, 3) == {"id": 2, "name": "Gruppe B", "member_ids": [3]}
    assert svc.group_of(ch, 99) is None


def test_group_member_ids_dedupes_a_user_in_two_groups(session):
    # Not a state validate_groups should ever allow, but group_member_ids is a
    # safety net for the standings path.
    ch = make_team_challenge(session, groups_json=json.dumps(groups_of([1, 2], [2, 3])))
    assert svc.group_member_ids(ch) == [1, 2, 3]


# --- group_standings (pure) -------------------------------------------------

def entry(uid, value):
    """One per-person entry as standings() returns it."""
    return {"user_id": uid, "value": value, "rank": 0, "geschafft": False, "nicht_mehr_schaffbar": False}


def test_group_standings_per_head_target(session):
    ch = make_team_challenge(session, target=100.0, groups_json=json.dumps(groups_of([1, 2, 3], [4, 5])))
    e = [entry(1, 150.0), entry(2, 90.0), entry(3, 60.0), entry(4, 100.0), entry(5, 120.0)]
    out = svc.group_standings(ch, e)
    # group B: (100+120)/2 = 110 >= 100, group A: 300/3 = 100 >= 100
    b, a = out
    assert (b["id"], b["sum"], b["value"], b["rank"], b["geschafft"]) == (2, 220.0, 110.0, 1, True)
    assert (a["id"], a["sum"], a["value"], a["rank"], a["geschafft"]) == (1, 300.0, 100.0, 2, True)
    assert [m["user_id"] for m in a["members"]] == [1, 2, 3]  # sorted by value desc
    assert a["size"] == 3 and a["member_ids"] == [1, 2, 3]


def test_group_standings_ranking_mode_ties_and_top_n(session):
    ch = make_team_challenge(
        session, mode="rangliste", top_n=1,
        groups_json=json.dumps(groups_of([1], [2], [3])), group_count=3,
    )
    e = [entry(1, 50.0), entry(2, 50.0), entry(3, 10.0)]
    out = svc.group_standings(ch, e)
    assert [(g["id"], g["rank"], g["geschafft"]) for g in out] == [(1, 1, True), (2, 1, True), (3, 3, False)]


def test_group_standings_ignores_members_missing_from_entries(session):
    # An inactive member is not in the entries (teilnehmer_ids filters them):
    # it drops out of sum and divisor. A group with no scored member is 0.
    ch = make_team_challenge(session, groups_json=json.dumps(groups_of([1, 2], [3])))
    out = svc.group_standings(ch, [entry(1, 80.0)])
    a = next(g for g in out if g["id"] == 1)
    b = next(g for g in out if g["id"] == 2)
    assert (a["sum"], a["value"], a["size"], a["member_ids"]) == (80.0, 80.0, 1, [1])
    assert (b["sum"], b["value"], b["size"], b["member_ids"]) == (0.0, 0.0, 0, [])


def test_group_standings_rounds_sum_and_value(session):
    ch = make_team_challenge(session, groups_json=json.dumps(groups_of([1, 2, 3])))
    e = [entry(1, 33.33), entry(2, 33.33), entry(3, 33.34)]
    out = svc.group_standings(ch, e)
    assert (out[0]["sum"], out[0]["value"]) == (100.0, 33.33)


def test_group_standings_ziel_without_target_never_geschafft(session):
    ch = make_team_challenge(
        session, mode="ziel", target=None, groups_json=json.dumps(groups_of([1], [2]))
    )
    e = [entry(1, 500.0), entry(2, 10.0)]
    out = svc.group_standings(ch, e)
    assert all(g["geschafft"] is False for g in out)


def test_group_standings_empty_group_not_geschafft_in_rangliste(session):
    ch = make_team_challenge(
        session, mode="rangliste", top_n=1, groups_json=json.dumps(groups_of([1], [2]))
    )
    out = svc.group_standings(ch, [entry(1, 0.0)])  # user 2 missing -> group B is empty
    a = next(g for g in out if g["id"] == 1)
    b = next(g for g in out if g["id"] == 2)
    assert a["rank"] == 1 and a["geschafft"] is True
    assert b["rank"] == 1 and b["size"] == 0 and b["geschafft"] is False


def test_group_standings_does_not_mutate_input(session):
    ch = make_team_challenge(session, groups_json=json.dumps(groups_of([1, 2])))
    e = [entry(1, 10.0), entry(2, 20.0)]
    before = copy.deepcopy(e)
    svc.group_standings(ch, e)
    assert e == before


# --- rows_between -----------------------------------------------------------

def test_rows_between_uses_window_and_category_filter(session):
    u = make_user(session, username="anna")
    lauf = make_category(session, name="Joggen", factor=1.0)
    rad = make_category(session, name="Rad", factor=0.5)
    ch = make_team_challenge(session, category_ids_json=json.dumps([lauf.id]))
    add_activity(session, u.id, lauf.id, date(2026, 8, 1), 10.0)
    add_activity(session, u.id, lauf.id, date(2026, 8, 5), 10.0)
    add_activity(session, u.id, rad.id, date(2026, 8, 5), 10.0)
    add_activity(session, u.id, lauf.id, date(2026, 8, 9), 10.0)
    rows = svc.rows_between(session, u.id, ch, date(2026, 8, 2), date(2026, 8, 8))
    assert [a.date for a, _ in rows] == [date(2026, 8, 5)]


# --- pool and seeding --------------------------------------------------------

def test_pool_auto_is_all_active_users(session):
    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    c = make_user(session, username="carla")
    c.is_active = False
    session.add(c)
    session.commit()
    ch = make_team_challenge(session, join_mode="auto")
    assert cg.pool(session, ch) == sorted([a.id, b.id])


def test_pool_opt_in_is_joined_active_users(session):
    a = make_user(session, username="anna")
    make_user(session, username="ben")
    ch = make_team_challenge(session, join_mode="opt_in")
    session.add(ChallengeParticipant(challenge_id=ch.id, user_id=a.id))
    session.commit()
    assert cg.pool(session, ch) == [a.id]


def test_seeding_window_is_last_n_days_up_to_yesterday(session):
    u = make_user(session, username="anna")
    lauf = make_category(session, name="Joggen", factor=2.0)
    heute = date(2026, 9, 12)
    ch = make_team_challenge(session, seeding_days=7)
    add_activity(session, u.id, lauf.id, heute, 100.0)                      # today: excluded
    add_activity(session, u.id, lauf.id, heute - timedelta(days=1), 10.0)   # in
    add_activity(session, u.id, lauf.id, heute - timedelta(days=7), 10.0)   # in (7 days back)
    add_activity(session, u.id, lauf.id, heute - timedelta(days=8), 10.0)   # out
    assert cg.seeding_value(session, u.id, ch, heute) == 40.0  # 2 × 10 km × factor 2


def test_seeding_uses_category_filter_and_ignores_km_factor(session):
    u = make_user(session, username="anna")
    u.km_factor = 5.0
    session.add(u)
    session.commit()
    lauf = make_category(session, name="Joggen", factor=1.0)
    rad = make_category(session, name="Rad", factor=1.0)
    heute = date(2026, 9, 12)
    ch = make_team_challenge(session, category_ids_json=json.dumps([lauf.id]))
    add_activity(session, u.id, lauf.id, heute - timedelta(days=2), 10.0)
    add_activity(session, u.id, rad.id, heute - timedelta(days=2), 50.0)
    assert cg.seeding_value(session, u.id, ch, heute) == 10.0


def test_seeding_anzahl_counts_activities(session):
    u = make_user(session, username="anna")
    lauf = make_category(session, name="Joggen", factor=1.0)
    heute = date(2026, 9, 12)
    ch = make_team_challenge(session, metric="anzahl")
    add_activity(session, u.id, lauf.id, heute - timedelta(days=2), 1.0)
    add_activity(session, u.id, lauf.id, heute - timedelta(days=3), 1.0)
    assert cg.seeding_value(session, u.id, ch, heute) == 2.0


def test_seeding_sorted_desc_ties_by_user_id(session):
    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    c = make_user(session, username="carla")
    lauf = make_category(session, name="Joggen", factor=1.0)
    heute = date(2026, 9, 12)
    ch = make_team_challenge(session)
    add_activity(session, b.id, lauf.id, heute - timedelta(days=1), 30.0)
    add_activity(session, a.id, lauf.id, heute - timedelta(days=1), 10.0)
    add_activity(session, c.id, lauf.id, heute - timedelta(days=1), 10.0)
    assert cg.seeding(session, ch, heute) == [(b.id, 30.0), (a.id, 10.0), (c.id, 10.0)]


def test_default_name_wraps_after_the_alphabet():
    assert cg.default_name(25) == "Gruppe Z"
    assert cg.default_name(26) == "Gruppe 27"


def test_seeding_includes_pool_users_without_activities(session):
    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    lauf = make_category(session, name="Joggen", factor=1.0)
    heute = date(2026, 9, 12)
    ch = make_team_challenge(session)
    add_activity(session, a.id, lauf.id, heute - timedelta(days=1), 10.0)
    assert cg.seeding(session, ch, heute) == [(a.id, 10.0), (b.id, 0.0)]


def test_seeding_days_one_counts_only_yesterday(session):
    u = make_user(session, username="anna")
    lauf = make_category(session, name="Joggen", factor=1.0)
    heute = date(2026, 9, 12)
    ch = make_team_challenge(session, seeding_days=1)
    add_activity(session, u.id, lauf.id, heute - timedelta(days=1), 10.0)
    add_activity(session, u.id, lauf.id, heute - timedelta(days=2), 10.0)
    assert cg.seeding_value(session, u.id, ch, heute) == 10.0


# --- draw -------------------------------------------------------------------

def _seeded_users(session, n, heute):
    """n users; user k has (k+1) × 10 MM yesterday, so seeding order = reverse creation."""
    lauf = make_category(session, name="Joggen", factor=1.0)
    users = [make_user(session, username=f"u{k}") for k in range(n)]
    for k, u in enumerate(users):
        add_activity(session, u.id, lauf.id, heute - timedelta(days=1), (k + 1) * 10.0)
    return users


def test_draw_spreads_every_pot_over_distinct_groups(session):
    heute = date(2026, 9, 12)
    users = _seeded_users(session, 9, heute)
    ch = make_team_challenge(session, group_count=3)
    gruppen = cg.draw(session, ch, heute, jetzt=None, rng=random.Random(7))
    assert [g["name"] for g in gruppen] == ["Gruppe A", "Gruppe B", "Gruppe C"]
    assert sorted(uid for g in gruppen for uid in g["member_ids"]) == sorted(u.id for u in users)
    order = [uid for uid, _ in cg.seeding(session, ch, heute)]
    for start in range(0, 9, 3):
        pot = order[start:start + 3]
        gruppen_ids = {next(g["id"] for g in gruppen if uid in g["member_ids"]) for uid in pot}
        assert len(gruppen_ids) == 3, f"pot {pot} not spread"
    assert svc.groups(ch) == gruppen
    assert ch.groups_drawn_at is not None


def test_draw_partial_last_pot_sizes_differ_by_at_most_one(session):
    heute = date(2026, 9, 12)
    _seeded_users(session, 8, heute)
    ch = make_team_challenge(session, group_count=3)
    gruppen = cg.draw(session, ch, heute, jetzt=None, rng=random.Random(3))
    sizes = sorted(len(g["member_ids"]) for g in gruppen)
    assert sizes == [2, 3, 3]


def test_draw_keeps_existing_names(session):
    heute = date(2026, 9, 12)
    _seeded_users(session, 4, heute)
    ch = make_team_challenge(session, group_count=2)
    svc.set_groups(ch, [{"id": 1, "name": "Die Flitzer", "member_ids": []},
                        {"id": 2, "name": "Gruppe B", "member_ids": []}])
    gruppen = cg.draw(session, ch, heute, jetzt=None, rng=random.Random(1))
    assert [g["name"] for g in gruppen] == ["Die Flitzer", "Gruppe B"]


def test_draw_is_random_inside_a_pot(session):
    heute = date(2026, 9, 12)
    _seeded_users(session, 6, heute)
    ch = make_team_challenge(session, group_count=2)
    seen = set()
    for seed in range(10):
        gruppen = cg.draw(session, ch, heute, jetzt=None, rng=random.Random(seed))
        seen.add(tuple(gruppen[0]["member_ids"]))
    assert len(seen) > 1


def test_draw_uses_given_timestamp(session):
    heute = date(2026, 9, 12)
    _seeded_users(session, 2, heute)
    ch = make_team_challenge(session, group_count=2)
    jetzt = datetime(2026, 9, 12, 8, 0, tzinfo=timezone.utc)
    gruppen = cg.draw(session, ch, heute, jetzt=jetzt)
    assert ch.groups_drawn_at == jetzt
    assert sorted(len(g["member_ids"]) for g in gruppen) == [1, 1]


def test_draw_needs_at_least_group_count_people(session):
    heute = date(2026, 9, 12)
    make_user(session, username="anna")
    ch = make_team_challenge(session, group_count=2)
    with pytest.raises(cg.TooFewPeople):
        cg.draw(session, ch, heute, jetzt=None)


def test_draw_needs_at_least_two_groups(session):
    heute = date(2026, 9, 12)
    _seeded_users(session, 2, heute)
    for group_count in (0, 1):
        ch = make_team_challenge(session, group_count=group_count)
        with pytest.raises(cg.InvalidGroups):
            cg.draw(session, ch, heute, jetzt=None)


def test_redraw_drops_members_who_left_the_pool(session):
    heute = date(2026, 9, 12)
    users = _seeded_users(session, 4, heute)
    ch = make_team_challenge(session, group_count=2)
    cg.draw(session, ch, heute, jetzt=None, rng=random.Random(1))
    renamed = svc.groups(ch)
    renamed[0]["name"] = "Rakete"
    svc.set_groups(ch, renamed)
    left = users[0]
    left.is_active = False
    session.add(left)
    session.commit()
    gruppen = cg.draw(session, ch, heute, jetzt=None, rng=random.Random(2))
    assert left.id not in svc.group_member_ids(ch)
    assert [g["name"] for g in gruppen] == ["Rakete", "Gruppe B"]


# --- validate_groups / save_groups -------------------------------------------

def test_save_groups_accepts_clean_list_and_trims_names(session):
    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    ch = make_team_challenge(session, group_count=2)
    out = cg.save_groups(session, ch, [
        {"id": 1, "name": "  Flitzer ", "member_ids": [a.id]},
        {"id": 2, "name": "Gruppe B", "member_ids": [b.id]},
    ])
    assert out[0]["name"] == "Flitzer"
    session.refresh(ch)
    assert svc.group_member_ids(ch) == [a.id, b.id]


def test_save_groups_rejects_bad_lists(session):
    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    c = make_user(session, username="carla")
    c.is_active = False
    session.add(c)
    session.commit()
    ch = make_team_challenge(session, group_count=2)
    ok = {"id": 2, "name": "B", "member_ids": [b.id]}
    cases = [
        ([{"id": 1, "name": "A", "member_ids": [a.id]}], "genau 2 Gruppen"),
        ([{"id": 1, "name": "A", "member_ids": [a.id, b.id]}, ok], "zwei Gruppen"),
        ([{"id": 1, "name": "A", "member_ids": [c.id]}, ok], "inaktive"),
        ([{"id": 1, "name": "A", "member_ids": [999]}, ok], "inaktive"),
        ([{"id": 1, "name": "  ", "member_ids": [a.id]}, ok], "Namen"),
        ([{"id": 1, "name": "A", "member_ids": []}, ok], "leer"),
        ([{"id": 2, "name": "A", "member_ids": [a.id]}, ok], "Gruppen-ID"),
    ]
    for gruppen, text in cases:
        with pytest.raises(cg.InvalidGroups, match=text):
            cg.save_groups(session, ch, gruppen)


def test_save_groups_opt_in_adds_participant_rows(session):
    from sqlmodel import select

    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    ch = make_team_challenge(session, group_count=2, join_mode="opt_in")
    session.add(ChallengeParticipant(challenge_id=ch.id, user_id=a.id))
    session.commit()
    cg.save_groups(session, ch, [
        {"id": 1, "name": "A", "member_ids": [a.id]},
        {"id": 2, "name": "B", "member_ids": [b.id]},
    ])
    rows = session.exec(
        select(ChallengeParticipant).where(ChallengeParticipant.challenge_id == ch.id)
    ).all()
    assert sorted(r.user_id for r in rows) == sorted([a.id, b.id])
