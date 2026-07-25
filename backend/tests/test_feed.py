import json
from datetime import date, datetime, time, timezone

from sqlmodel import select

from app.models import AchievementUnlock, Activity, FeedEvent, Season
from app.services import feed
from tests.conftest import login, make_category, make_user


def _setup_saison(session, start=date(2026, 7, 20)):
    session.add(Season(year=2026, goal_km=1000.0, start_date=start,
                       end_date=date(2027, 5, 16),
                       milestones_json=json.dumps([{"km": 50.0, "label": "Ärmelkanal", "icon": "fahne"}])))
    session.commit()


def _act(session, user, cat, km, tag=date(2026, 8, 3)):
    act = Activity(user_id=user.id, category_id=cat.id, date=tag, distance_km=km)
    session.add(act)
    session.commit()
    session.refresh(act)
    return act


def test_activity_event_mit_kategorie_und_mm(session):
    _setup_saison(session)
    user = make_user(session)
    cat = make_category(session, factor=4.0)
    act = _act(session, user, cat, 10.0)
    feed.activity_event(session, act)
    ev = session.exec(select(FeedEvent).where(FeedEvent.type == "activity")).one()
    p = json.loads(ev.payload_json)
    assert ev.user_id == user.id and ev.activity_id == act.id
    assert p["mm"] == 40.0 and p["category"]["name"] == cat.name


def test_rank_events_nur_top5_aufsteiger(session):
    _setup_saison(session)
    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    before = [b.id, a.id]
    after = [a.id, b.id]
    feed.rank_events(session, before, after)
    ev = session.exec(select(FeedEvent).where(FeedEvent.type == "rank_change")).one()
    p = json.loads(ev.payload_json)
    assert ev.user_id == a.id
    assert p["ueberholt_user_id"] == b.id and p["neuer_rang"] == 1


def test_rank_events_keine_events_ohne_aenderung(session):
    _setup_saison(session)
    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    feed.rank_events(session, [a.id, b.id], [a.id, b.id])
    assert session.exec(select(FeedEvent)).all() == []


def test_milestone_event_bei_ueberschreitung(session):
    _setup_saison(session)
    user = make_user(session)
    feed.milestone_events(session, user.id, total_before=45.0, total_after=52.0)
    ev = session.exec(select(FeedEvent).where(FeedEvent.type == "milestone")).one()
    assert json.loads(ev.payload_json)["label"] == "Ärmelkanal"


def test_milestone_kein_event_ohne_ueberschreitung(session):
    _setup_saison(session)
    user = make_user(session)
    feed.milestone_events(session, user.id, total_before=52.0, total_after=60.0)
    assert session.exec(select(FeedEvent)).all() == []


def test_challenge_order_nach_mm_mit_handicap(session):
    _setup_saison(session)
    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    cat = make_category(session, factor=1.0)
    _act(session, a, cat, 10.0)
    _act(session, b, cat, 20.0)
    assert feed.challenge_order(session) == [b.id, a.id]


def test_remove_activity_events(session):
    _setup_saison(session)
    user = make_user(session)
    cat = make_category(session)
    act = _act(session, user, cat, 10.0)
    feed.activity_event(session, act)
    feed.remove_activity_events(session, act.id)
    assert session.exec(select(FeedEvent)).all() == []


def test_unlock_erzeugt_achievement_event(session):
    _setup_saison(session)
    user = make_user(session)
    cat = make_category(session, factor=1.0)
    for _ in range(3):  # Hattrick: 3 Aktivitäten an einem Tag
        _act(session, user, cat, 2.0)
    from app.services.achievements import check_unlocks
    check_unlocks(session, user.id)
    evs = session.exec(select(FeedEvent).where(FeedEvent.type == "achievement")).all()
    keys = [json.loads(e.payload_json)["key"] for e in evs]
    assert "hattrick" in keys
    hat = next(json.loads(e.payload_json) for e in evs
               if json.loads(e.payload_json)["key"] == "hattrick")
    assert hat["title"] == "Hattrick" and hat["emoji"] == "🎩"


# Abweichung vom Plan: statt "2026-08-03" wird "2026-07-24" gepostet —
# ActivityCreate lehnt Zukunftsdaten ab (not_in_future), das Plandatum läge
# beim Ausführungszeitpunkt in der Zukunft. 24.07. liegt im Season-Fenster.
def test_create_activity_emittiert_events(client, session):
    _setup_saison(session)
    make_user(session)
    cat = make_category(session, factor=1.0)
    login(client)
    r = client.post("/api/activities", json={
        "category_id": cat.id, "date": "2026-07-24", "distance_km": 60.0,
    })
    assert r.status_code == 201
    typen = {e.type for e in session.exec(select(FeedEvent)).all()}
    assert "activity" in typen
    assert "milestone" in typen  # 60 MM > 50-km-Meilenstein


def test_delete_activity_entfernt_feed_eintrag(client, session):
    _setup_saison(session)
    make_user(session)
    cat = make_category(session, factor=1.0)
    login(client)
    act_id = client.post("/api/activities", json={
        "category_id": cat.id, "date": "2026-07-24", "distance_km": 10.0,
    }).json()["id"]
    client.delete(f"/api/activities/{act_id}")
    assert session.exec(
        select(FeedEvent).where(FeedEvent.type == "activity")
    ).all() == []


def test_strava_backfill_erzeugt_keine_feed_events(session):
    _setup_saison(session)
    user = make_user(session)
    make_category(session, factor=1.0, strava_sport_types='["Run"]')
    from app.models import StravaConnection
    from app.services.strava import import_activity
    conn = StravaConnection(user_id=user.id, athlete_id=1, access_token="t",
                            refresh_token="r", expires_at=9999999999)
    session.add(conn)
    session.commit()
    data = {"id": 42, "sport_type": "Run", "distance": 8000,
            "start_date_local": "2026-08-03T07:00:00Z"}
    import_activity(session, conn, data, emit_feed=False)
    assert session.exec(
        select(FeedEvent).where(FeedEvent.type == "activity")
    ).all() == []


def _utc(dt):
    """DB-Zeitstempel normalisieren: SQLite liefert naive UTC-Zeiten."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _act_mit_event(session, user, cat, km, tag):
    """Aktivität + activity-Event mit created_at am Aktivitätstag 10:00."""
    act = _act(session, user, cat, km, tag=tag)
    feed.activity_event(session, act)
    ev = session.exec(
        select(FeedEvent).where(FeedEvent.activity_id == act.id)
    ).one()
    ev.created_at = datetime(tag.year, tag.month, tag.day, 10, 0)
    session.add(ev)
    session.commit()
    return act


def test_wochenrueckblick_wird_einmal_erzeugt(session):
    _setup_saison(session, start=date(2026, 7, 20))
    user = make_user(session)
    cat = make_category(session, factor=1.0)
    # Aktivität + Event in der Vorwoche (Mo 27.07.–So 02.08.)
    _act_mit_event(session, user, cat, 12.0, tag=date(2026, 7, 28))

    jetzt = datetime(2026, 8, 3, 8, 0, tzinfo=feed._MESZ)  # Montag danach
    feed.ensure_recaps(session, now=jetzt)
    feed.ensure_recaps(session, now=jetzt)  # idempotent
    recaps = session.exec(
        select(FeedEvent).where(FeedEvent.type == "recap_week")
    ).all()
    assert len(recaps) == 1
    p = json.loads(recaps[0].payload_json)
    assert p["period"] == "2026-W31"
    assert p["total_mm"] == 12.0
    assert p["per_user"][0]["user_id"] == user.id
    # created_at = Fälligkeitszeitpunkt So 02.08. 19:00 MESZ (= 17:00 UTC)
    assert _utc(recaps[0].created_at) == datetime(2026, 8, 2, 17, 0, tzinfo=timezone.utc)


def test_wochenrueckblick_erst_ab_sonntag_19_uhr(session):
    _setup_saison(session, start=date(2026, 7, 20))
    user = make_user(session)
    cat = make_category(session, factor=1.0)
    _act_mit_event(session, user, cat, 8.0, tag=date(2026, 7, 22))

    feed.ensure_recaps(session, now=datetime(2026, 7, 26, 18, 59, tzinfo=feed._MESZ))
    assert session.exec(
        select(FeedEvent).where(FeedEvent.type == "recap_week")
    ).all() == []

    feed.ensure_recaps(session, now=datetime(2026, 7, 26, 19, 1, tzinfo=feed._MESZ))
    recaps = session.exec(
        select(FeedEvent).where(FeedEvent.type == "recap_week")
    ).all()
    assert len(recaps) == 1
    p = json.loads(recaps[0].payload_json)
    assert p["period"] == "2026-W30"
    assert p["von"] == "2026-07-20"  # erste Woche beginnt am Saisonstart
    assert p["bis"] == "2026-07-26"


def test_zwei_verpasste_wochen_werden_aufgefuellt(session):
    _setup_saison(session, start=date(2026, 7, 20))
    user = make_user(session)
    cat = make_category(session, factor=1.0)
    _act_mit_event(session, user, cat, 8.0, tag=date(2026, 7, 22))  # KW 30
    _act_mit_event(session, user, cat, 5.0, tag=date(2026, 7, 29))  # KW 31

    feed.ensure_recaps(session, now=datetime(2026, 8, 4, 12, 0, tzinfo=feed._MESZ))
    recaps = session.exec(
        select(FeedEvent).where(FeedEvent.type == "recap_week")
    ).all()
    periods = sorted(json.loads(r.payload_json)["period"] for r in recaps)
    assert periods == ["2026-W30", "2026-W31"]
    faellig = sorted(_utc(r.created_at) for r in recaps)
    assert faellig == [
        datetime(2026, 7, 26, 17, 0, tzinfo=timezone.utc),  # So 26.07. 19:00 MESZ
        datetime(2026, 8, 2, 17, 0, tzinfo=timezone.utc),  # So 02.08. 19:00 MESZ
    ]


def test_kein_rueckblick_ohne_events_im_zeitraum(session):
    _setup_saison(session, start=date(2026, 7, 20))
    make_user(session)
    feed.ensure_recaps(session, now=datetime(2026, 8, 3, 8, 0, tzinfo=feed._MESZ))
    assert session.exec(
        select(FeedEvent).where(FeedEvent.type == "recap_week")
    ).all() == []


def test_monatsrueckblick_am_monatsersten(session):
    _setup_saison(session, start=date(2026, 7, 20))
    user = make_user(session)
    cat = make_category(session, factor=1.0)
    _act_mit_event(session, user, cat, 10.0, tag=date(2026, 8, 15))

    feed.ensure_recaps(session, now=datetime(2026, 9, 1, 0, 5, tzinfo=feed._MESZ))
    recaps = session.exec(
        select(FeedEvent).where(FeedEvent.type == "recap_month")
    ).all()
    assert len(recaps) == 1
    assert json.loads(recaps[0].payload_json)["period"] == "2026-08"
    # created_at = Fälligkeit Monatserster 00:00 MESZ (= 31.08. 22:00 UTC)
    assert _utc(recaps[0].created_at) == datetime(2026, 8, 31, 22, 0, tzinfo=timezone.utc)


# Abweichung vom Plan: Datum "2026-07-24" statt "2026-08-03" — Zukunftsdaten
# geben 422 (not_in_future), siehe Kommentar bei test_create_activity_emittiert_events.
def test_feed_api_paginierung_und_reaktionen(client, session):
    _setup_saison(session)
    user = make_user(session)
    cat = make_category(session, factor=1.0)
    login(client)
    for _ in range(35):
        client.post("/api/activities", json={
            "category_id": cat.id, "date": "2026-07-24", "distance_km": 6.0,
        })
    page = client.get("/api/feed?year=2026").json()
    assert len(page["events"]) == 30
    assert page["next_before"] is not None
    page2 = client.get(f"/api/feed?year=2026&before={page['next_before']}").json()
    assert 0 < len(page2["events"]) <= 30

    ev_id = page["events"][0]["id"]
    r = client.post(f"/api/feed/{ev_id}/reactions", json={"emoji": "🔥"}).json()
    fire = next(x for x in r if x["emoji"] == "🔥")
    assert fire["count"] == 1 and fire["mine"] is True
    r = client.post(f"/api/feed/{ev_id}/reactions", json={"emoji": "🔥"}).json()
    assert all(x["emoji"] != "🔥" for x in r)  # Toggle aus
    assert client.post(
        f"/api/feed/{ev_id}/reactions", json={"emoji": "🍕"}
    ).status_code == 422


def _backfill_szenario(session):
    """Zwei User, drei Aktivitäten + ein Achievement-Unlock vor dem Backfill."""
    _setup_saison(session)  # Meilenstein bei 50 km
    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    cat = make_category(session, factor=1.0)
    session.add(Activity(user_id=a.id, category_id=cat.id, date=date(2026, 7, 21),
                         start_time=time(7, 30), distance_km=30.0))
    session.add(Activity(user_id=b.id, category_id=cat.id, date=date(2026, 7, 22),
                         distance_km=40.0))  # ohne start_time → 12:00
    session.add(Activity(user_id=a.id, category_id=cat.id, date=date(2026, 7, 23),
                         start_time=time(18, 0), distance_km=25.0))  # 55 > 50-Meilenstein
    session.add(AchievementUnlock(user_id=a.id, key="hattrick",
                                  unlocked_at=datetime(2026, 7, 23, 18, 30,
                                                       tzinfo=timezone.utc)))
    session.commit()
    return a, b


def test_backfill_erzeugt_events_mit_zeitstempeln(session):
    a, b = _backfill_szenario(session)
    feed.backfill_feed_events(session)

    acts = session.exec(
        select(FeedEvent).where(FeedEvent.type == "activity")
    ).all()
    assert [_utc(e.created_at) for e in acts] == [
        datetime(2026, 7, 21, 5, 30, tzinfo=timezone.utc),  # 07:30 MESZ
        datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc),  # 12:00 MESZ (Default)
        datetime(2026, 7, 23, 16, 0, tzinfo=timezone.utc),  # 18:00 MESZ
    ]
    assert json.loads(acts[0].payload_json)["mm"] == 30.0

    mile = session.exec(
        select(FeedEvent).where(FeedEvent.type == "milestone")
    ).one()
    assert mile.user_id == a.id
    assert _utc(mile.created_at) == datetime(2026, 7, 23, 16, 0, tzinfo=timezone.utc)
    assert json.loads(mile.payload_json)["label"] == "Ärmelkanal"

    ranks = session.exec(
        select(FeedEvent).where(FeedEvent.type == "rank_change")
    ).all()
    assert [(r.user_id, _utc(r.created_at)) for r in ranks] == [
        (b.id, datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc)),  # Ben überholt Anna
        (a.id, datetime(2026, 7, 23, 16, 0, tzinfo=timezone.utc)),  # Anna zurück
    ]
    assert json.loads(ranks[0].payload_json)["ueberholt_user_id"] == a.id

    ach = session.exec(
        select(FeedEvent).where(FeedEvent.type == "achievement")
    ).one()
    assert ach.user_id == a.id
    assert _utc(ach.created_at) == datetime(2026, 7, 23, 18, 30, tzinfo=timezone.utc)
    p = json.loads(ach.payload_json)
    assert p["key"] == "hattrick" and p["title"] == "Hattrick" and p["emoji"] == "🎩"


def test_backfill_zweiter_aufruf_erzeugt_nichts_neues(session):
    _backfill_szenario(session)
    feed.backfill_feed_events(session)
    anzahl = len(session.exec(select(FeedEvent)).all())
    feed.backfill_feed_events(session)
    assert len(session.exec(select(FeedEvent)).all()) == anzahl


def test_backfill_tut_nichts_bei_nicht_leerer_tabelle(session):
    a, _ = _backfill_szenario(session)
    act = session.exec(select(Activity)).first()
    feed.activity_event(session, act)  # Tabelle nicht mehr leer
    feed.backfill_feed_events(session)
    assert len(session.exec(select(FeedEvent)).all()) == 1


def test_backfill_dann_ensure_recaps_fuellt_wochen_auf(session):
    _backfill_szenario(session)
    feed.backfill_feed_events(session)
    feed.ensure_recaps(session, now=datetime(2026, 7, 27, 9, 0, tzinfo=feed._MESZ))
    recaps = session.exec(
        select(FeedEvent).where(FeedEvent.type == "recap_week")
    ).all()
    assert len(recaps) == 1
    p = json.loads(recaps[0].payload_json)
    assert p["period"] == "2026-W30"
    assert p["total_mm"] == 95.0  # 30 + 40 + 25


def test_feed_unseen_und_seen(client, session):
    _setup_saison(session)
    make_user(session)
    cat = make_category(session, factor=1.0)
    login(client)
    client.post("/api/activities", json={
        "category_id": cat.id, "date": "2026-07-24", "distance_km": 6.0,
    })
    assert client.get("/api/feed/unseen").json() == {"has_new": True}
    client.post("/api/feed/seen")
    assert client.get("/api/feed/unseen").json() == {"has_new": False}
