"""Achievement-Ausbau 10/2026: MM-Club, Zeit-Leitern, Monatssieger, neue Hidden."""

from datetime import date, datetime, time, timedelta, timezone

from sqlmodel import select

from app.models import AchievementUnlock, Activity, FeedEvent, Season
from app.services.achievements import check_unlocks, ensure_monatssieger
from tests.conftest import login, make_category, make_user

MESZ = timezone(timedelta(hours=2))


def add_act(session, user, cat, km, d=date(2026, 8, 1), elevation=None,
            start_time=None, duration_min=None):
    session.add(Activity(
        user_id=user.id, category_id=cat.id, date=d, distance_km=km,
        elevation_m=elevation, start_time=start_time, duration_min=duration_min,
    ))
    session.commit()


def keys_of(session, user):
    return {
        u.key for u in session.exec(
            select(AchievementUnlock).where(AchievementUnlock.user_id == user.id)
        ).all()
    }


def make_season(session, start, end=None):
    session.add(Season(year=start.year, goal_km=1000.0, start_date=start,
                       end_date=end, milestones_json="[]"))
    session.commit()


# --- MM-Club -----------------------------------------------------------------

def test_mm_club_zaehlt_gewertete_mm(session):
    user = make_user(session)
    rad = make_category(session, name="Radfahren", icon="rad", factor=1.0)
    schwimm = make_category(session, name="Schwimmen", icon="schwimmen", factor=10.0)
    add_act(session, user, rad, 30.0)
    add_act(session, user, schwimm, 96.9)  # 969 + 30 = 999 MM
    check_unlocks(session, user.id)
    assert "mm_club_1k" not in keys_of(session, user)
    add_act(session, user, rad, 1.0)  # exakt 1000 MM
    check_unlocks(session, user.id)
    assert "mm_club_1k" in keys_of(session, user)
    assert "mm_club_5k" not in keys_of(session, user)


def test_mm_club_leiter_in_der_api(client, session):
    user = make_user(session)
    lauf = make_category(session, name="Laufen", icon="laufen", factor=4.0)
    add_act(session, user, lauf, 30.0)  # 120 MM
    login(client)
    body = {a["key"]: a for a in client.get("/api/achievements").json()}
    club = body["mm_club_1k"]
    assert club["ladder"] == "mm_club"
    assert club["stage"] == "1k"
    assert club["unit"] == "MM"
    assert club["progress"] == 0.12
    assert body["mm_club_10k"]["title"] == "10k MM — Insane"


# --- Zeit-Leitern ------------------------------------------------------------

def test_zeit_leiter_stapelt_je_kategorie(session):
    user = make_user(session)
    rad = make_category(session, name="Radfahren", icon="rad", factor=1.0)
    lauf = make_category(session, name="Laufen", icon="laufen", factor=1.0)
    add_act(session, user, rad, 20.0, duration_min=59)
    add_act(session, user, lauf, 5.0, duration_min=600)  # 10 h Laufen
    add_act(session, user, rad, 20.0)  # ohne Dauer: zählt nicht
    check_unlocks(session, user.id)
    keys = keys_of(session, user)
    assert f"zeit_{rad.id}_1h" not in keys
    assert {f"zeit_{lauf.id}_1h", f"zeit_{lauf.id}_10h"} <= keys
    assert f"zeit_{lauf.id}_100h" not in keys
    add_act(session, user, rad, 1.0, duration_min=1)
    check_unlocks(session, user.id)
    assert f"zeit_{rad.id}_1h" in keys_of(session, user)


def test_zeit_leiter_erst_ab_einer_stunde_sichtbar(client, session):
    user = make_user(session)
    rad = make_category(session, name="Radfahren", icon="rad", factor=1.0)
    lauf = make_category(session, name="Laufen", icon="laufen", factor=1.0)
    add_act(session, user, rad, 100.0, duration_min=300)  # 5 h
    add_act(session, user, lauf, 5.0, duration_min=30)  # 0,5 h → unsichtbar
    login(client)
    body = client.get("/api/achievements").json()
    zeit = {a["key"]: a for a in body if (a["ladder"] or "").startswith("zeit_")}
    assert set(zeit) == {f"zeit_{rad.id}_{h}h" for h in (1, 10, 100, 1000)}
    zehn = zeit[f"zeit_{rad.id}_10h"]
    # 5 h auf dem Weg zu 10 h → Balken in der Mitte
    assert zehn["progress"] == 0.5
    assert zehn["achieved"] is False
    assert zehn["ladder_title"] == "Radfahren"
    assert zehn["unit"] == "h"
    assert zeit[f"zeit_{rad.id}_1h"]["achieved"] is True
    assert zeit[f"zeit_{rad.id}_1000h"]["emoji"] == "⏳"


def test_zeit_unlock_feed_titel_mit_kategorie(session):
    make_season(session, date(2026, 7, 20))
    user = make_user(session)
    rad = make_category(session, name="Radfahren", icon="rad", factor=1.0)
    add_act(session, user, rad, 20.0, duration_min=60)
    check_unlocks(session, user.id)
    ev = session.exec(select(FeedEvent).where(FeedEvent.type == "achievement")).all()
    titel = [e.payload_json for e in ev if f"zeit_{rad.id}_1h" in e.payload_json]
    assert titel and "Radfahren: 1 h" in titel[0]


# --- Monatssieger ------------------------------------------------------------

def test_monatssieger_rueckwirkend_ab_saisonstart(session):
    make_season(session, date(2026, 7, 20))
    erik = make_user(session)
    lisa = make_user(session, username="lisa")
    lauf = make_category(session, name="Laufen", icon="laufen", factor=1.0)
    add_act(session, erik, lauf, 5.0, d=date(2026, 7, 10))  # Warm-up zählt nicht
    add_act(session, lisa, lauf, 3.0, d=date(2026, 7, 25))
    add_act(session, erik, lauf, 10.0, d=date(2026, 8, 3))
    add_act(session, lisa, lauf, 4.0, d=date(2026, 8, 4))
    add_act(session, lisa, lauf, 50.0, d=date(2026, 9, 2))  # laufender Monat
    ensure_monatssieger(session, now=datetime(2026, 9, 15, 12, tzinfo=MESZ))
    assert "monatssieger_2026-07" in keys_of(session, lisa)
    assert "monatssieger_2026-07" not in keys_of(session, erik)
    assert "monatssieger_2026-08" in keys_of(session, erik)
    assert "monatssieger_2026-09" not in keys_of(session, lisa)
    ul = session.exec(select(AchievementUnlock).where(
        AchievementUnlock.key == "monatssieger_2026-08")).one()
    # Freigeschaltet zum Monatsersten 00:00 deutscher Zeit
    assert ul.unlocked_at.replace(tzinfo=timezone.utc) == datetime(
        2026, 9, 1, tzinfo=MESZ)


def test_monatssieger_handicap_gleichstand_idempotent(session):
    make_season(session, date(2026, 7, 20))
    erik = make_user(session)
    lisa = make_user(session, username="lisa")
    lisa.km_factor = 2.0
    session.add(lisa)
    session.commit()
    lauf = make_category(session, name="Laufen", icon="laufen", factor=1.0)
    add_act(session, erik, lauf, 10.0, d=date(2026, 8, 3))
    add_act(session, lisa, lauf, 5.0, d=date(2026, 8, 4))  # ×2 Handicap = 10
    now = datetime(2026, 9, 1, 0, 0, tzinfo=MESZ)
    ensure_monatssieger(session, now=now)
    ensure_monatssieger(session, now=now)
    rows = session.exec(select(AchievementUnlock).where(
        AchievementUnlock.key == "monatssieger_2026-08")).all()
    assert sorted(r.user_id for r in rows) == sorted([erik.id, lisa.id])


def test_monatssieger_krone_im_vergleich_und_profil(client, session):
    heute = date.today()
    start = (heute.replace(day=1) - timedelta(days=1)).replace(day=1)  # Vormonat
    make_season(session, start)
    user = make_user(session)
    lauf = make_category(session, name="Laufen", icon="laufen", factor=1.0)
    add_act(session, user, lauf, 5.0, d=start + timedelta(days=2))
    login(client)
    body = client.get(f"/api/comparison/{start.year}").json()
    me = next(u for u in body["users"] if u["user_id"] == user.id)
    assert "🥇" in me["emojis"]
    key = f"monatssieger_{start:%Y-%m}"
    ach = {a["key"]: a for a in client.get("/api/achievements").json()}
    assert ach[key]["achieved"] is True
    assert ach[key]["title"] == f"Monatssieger {start:%m/%Y}"


# --- Neue Hidden -------------------------------------------------------------

def test_tageszeit_hidden(session):
    user = make_user(session)
    lauf = make_category(session, name="Laufen", icon="laufen")
    for i in range(4):
        add_act(session, user, lauf, 5.0, d=date(2026, 8, 1 + i), start_time=time(5, 30))
        add_act(session, user, lauf, 5.0, d=date(2026, 8, 1 + i), start_time=time(22, 0))
    check_unlocks(session, user.id)
    assert not {"fruehaufsteher", "nachteule"} & keys_of(session, user)
    add_act(session, user, lauf, 5.0, d=date(2026, 8, 9), start_time=time(5, 59))
    add_act(session, user, lauf, 5.0, d=date(2026, 8, 9), start_time=time(23, 0))
    check_unlocks(session, user.id)
    assert {"fruehaufsteher", "nachteule"} <= keys_of(session, user)


def test_vielfalt_hidden(session):
    user = make_user(session)
    cats = [make_category(session, name=f"K{i}", icon="medaille") for i in range(4)]
    # Mo–Sa einer KW je eine andere Kategorie → Allrounder, kein Doppeltag
    for i, cat in enumerate(cats[:3]):
        add_act(session, user, cat, 5.0, d=date(2026, 8, 3 + i))
    check_unlocks(session, user.id)
    assert not {"allrounder", "doppelschicht"} & keys_of(session, user)
    add_act(session, user, cats[3], 5.0, d=date(2026, 8, 9))  # Sonntag derselben KW
    check_unlocks(session, user.id)
    assert "allrounder" in keys_of(session, user)
    assert "doppelschicht" not in keys_of(session, user)
    add_act(session, user, cats[0], 5.0, d=date(2026, 8, 9))
    check_unlocks(session, user.id)
    assert "doppelschicht" in keys_of(session, user)


def test_hoehe_hidden(session):
    user = make_user(session)
    rad = make_category(session, name="Radfahren", icon="rad", factor=1.0)
    add_act(session, user, rad, 50.0, d=date(2026, 8, 1), elevation=1999.0)
    for i in range(4):
        add_act(session, user, rad, 50.0, d=date(2026, 8, 2 + i), elevation=1700.0)
    check_unlocks(session, user.id)
    assert not {"gipfelsturm", "everest"} & keys_of(session, user)  # 8799 Hm
    add_act(session, user, rad, 50.0, d=date(2026, 8, 1), elevation=49.0)
    check_unlocks(session, user.id)
    assert {"gipfelsturm", "everest"} <= keys_of(session, user)


def test_comeback_und_wochenendkrieger(session):
    user = make_user(session)
    lauf = make_category(session, name="Laufen", icon="laufen")
    sa = date(2026, 8, 1)  # Samstag
    for w in range(4):
        add_act(session, user, lauf, 5.0, d=sa + timedelta(weeks=w))
        if w != 2:
            add_act(session, user, lauf, 5.0, d=sa + timedelta(weeks=w, days=1))
    check_unlocks(session, user.id)
    assert "wochenendkrieger" not in keys_of(session, user)  # Lücke in Woche 3
    add_act(session, user, lauf, 5.0, d=sa + timedelta(weeks=2, days=1))
    check_unlocks(session, user.id)
    assert "wochenendkrieger" in keys_of(session, user)
    letzter = sa + timedelta(weeks=3, days=1)
    add_act(session, user, lauf, 5.0, d=letzter + timedelta(days=14))  # 13 Tage Pause
    check_unlocks(session, user.id)
    assert "comeback" not in keys_of(session, user)
    add_act(session, user, lauf, 5.0, d=letzter + timedelta(days=29))  # 14 Tage Pause
    check_unlocks(session, user.id)
    assert "comeback" in keys_of(session, user)


def test_spass_hidden(session):
    user = make_user(session)
    lauf = make_category(session, name="Laufen", icon="laufen", factor=1.0)
    rad = make_category(session, name="Radfahren", icon="rad", factor=1.0)
    add_act(session, user, lauf, 11.1, d=date(2026, 8, 1))
    add_act(session, user, rad, 50.0, d=date(2026, 8, 2))  # kein Lauf
    add_act(session, user, lauf, 42.1, d=date(2026, 8, 3))
    add_act(session, user, lauf, 0.1, d=date(2026, 8, 4), duration_min=2)
    check_unlocks(session, user.id)
    assert not {"schnapszahl", "marathon_am_stueck", "neujahr",
                "der_nimmt_alles_mit"} & keys_of(session, user)
    add_act(session, user, lauf, 22.22, d=date(2027, 1, 1))
    add_act(session, user, lauf, 42.2, d=date(2026, 8, 5))
    add_act(session, user, lauf, 0.5, d=date(2026, 8, 6), duration_min=1)
    check_unlocks(session, user.id)
    assert {"schnapszahl", "marathon_am_stueck", "neujahr",
            "der_nimmt_alles_mit"} <= keys_of(session, user)


def test_ueberholmanoever_drei_an_einem_tag(session):
    heute = date.today()
    start = heute - timedelta(days=5)
    make_season(session, start)
    lauf = make_category(session, name="Laufen", icon="laufen", factor=1.0)
    ich = make_user(session, username="ich")
    andere = [make_user(session, username=n) for n in ("a", "b", "c")]
    for i, u in enumerate(andere):
        add_act(session, u, lauf, 10.0 + i, d=start)
    add_act(session, ich, lauf, 5.0, d=start)
    add_act(session, ich, lauf, 7.0, d=start + timedelta(days=1))  # 12: überholt a, b
    check_unlocks(session, ich.id)
    assert "ueberholmanoever" not in keys_of(session, ich)
    add_act(session, ich, lauf, 20.0, d=start + timedelta(days=2))  # c auch, aber nur 1
    check_unlocks(session, ich.id)
    assert "ueberholmanoever" not in keys_of(session, ich)
    # Gleicher Tag wie oben, aber jetzt mit genug km: a, b, c an Tag 1 überholt
    add_act(session, ich, lauf, 1.0, d=start + timedelta(days=1))
    check_unlocks(session, ich.id)
    assert "ueberholmanoever" in keys_of(session, ich)
