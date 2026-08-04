from datetime import date

from app.models import Activity, Challenge, ChallengeParticipant
from tests.conftest import make_category, make_user


def make_challenge(session, **kw) -> Challenge:
    daten = dict(
        title="Test", creator_id=1, mode="ziel", target=100.0, metric="mm",
        join_mode="auto", period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31), status="laufend",
    )
    daten.update(kw)
    ch = Challenge(**daten)
    session.add(ch)
    session.commit()
    session.refresh(ch)
    return ch


def add_activity(session, user_id, cat_id, tag, km):
    session.add(
        Activity(user_id=user_id, category_id=cat_id, date=tag, distance_km=km)
    )
    session.commit()


def test_teilnehmer_auto_sind_alle_aktiven(session):
    from app.services import challenges

    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    c = make_user(session, username="carla")
    c.is_active = False
    session.add(c)
    session.commit()
    ch = make_challenge(session, join_mode="auto")
    assert challenges.teilnehmer_ids(session, ch) == sorted([a.id, b.id])


def test_teilnehmer_opt_in_nur_beigetretene(session):
    from app.services import challenges

    a = make_user(session, username="anna")
    make_user(session, username="ben")
    ch = make_challenge(session, join_mode="opt_in")
    session.add(ChallengeParticipant(challenge_id=ch.id, user_id=a.id))
    session.commit()
    assert challenges.teilnehmer_ids(session, ch) == [a.id]


def test_standings_sortiert_und_markiert_geschafft(session):
    from app.services import challenges

    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    lauf = make_category(session, name="Joggen", factor=1.0)
    ch = make_challenge(session, target=100.0)
    add_activity(session, a.id, lauf.id, date(2026, 8, 5), 120.0)
    add_activity(session, b.id, lauf.id, date(2026, 8, 5), 40.0)
    stand = challenges.standings(session, ch, date(2026, 8, 10))
    assert [e["user_id"] for e in stand] == [a.id, b.id]
    assert [e["rank"] for e in stand] == [1, 2]
    assert [e["geschafft"] for e in stand] == [True, False]


def test_standings_gleichstand_teilt_rang_und_ueberspringt(session):
    from app.services import challenges

    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    c = make_user(session, username="carla")
    lauf = make_category(session, name="Joggen", factor=1.0)
    ch = make_challenge(session, mode="rangliste", target=None, top_n=2)
    add_activity(session, a.id, lauf.id, date(2026, 8, 5), 50.0)
    add_activity(session, b.id, lauf.id, date(2026, 8, 5), 50.0)
    add_activity(session, c.id, lauf.id, date(2026, 8, 5), 10.0)
    stand = challenges.standings(session, ch, date(2026, 8, 10))
    assert [e["rank"] for e in stand] == [1, 1, 3]
    # Bei Gleichstand duerfen mehr als top_n gewinnen — geteilte Plaetze
    # sind bei einem echten Preis besser als ein Zufalls-Stichentscheid.
    assert [e["geschafft"] for e in stand] == [True, True, False]


def test_standings_uebergeht_inaktive_teilnehmer(session):
    from app.services import challenges

    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    lauf = make_category(session, name="Joggen", factor=1.0)
    ch = make_challenge(session, join_mode="opt_in")
    session.add(ChallengeParticipant(challenge_id=ch.id, user_id=a.id))
    session.add(ChallengeParticipant(challenge_id=ch.id, user_id=b.id))
    session.commit()
    add_activity(session, b.id, lauf.id, date(2026, 8, 5), 500.0)
    b.is_active = False
    session.add(b)
    session.commit()
    stand = challenges.standings(session, ch, date(2026, 8, 10))
    assert [e["user_id"] for e in stand] == [a.id]


def test_standings_markiert_nicht_mehr_schaffbar(session):
    from app.services import challenges

    a = make_user(session, username="anna")
    make_category(session, name="Joggen", factor=1.0)
    ch = make_challenge(
        session, metric="streak", target=10.0,
        period_start=date(2026, 8, 1), period_end=date(2026, 8, 31),
    )
    stand = challenges.standings(session, ch, date(2026, 8, 25))
    assert stand[0]["nicht_mehr_schaffbar"] is True
    assert stand[0]["geschafft"] is False


def test_freeze_at_ist_folgetag_sechs_uhr_deutscher_zeit(session):
    from datetime import datetime, timezone

    from app.services import challenges

    ch = make_challenge(session, period_end=date(2026, 8, 31))
    # 01.09.2026 06:00 MESZ == 04:00 UTC
    assert challenges.freeze_at(ch) == datetime(2026, 9, 1, 4, 0, tzinfo=timezone.utc)


def test_resolve_due_startet_geplante_challenge(session):
    from datetime import datetime, timezone

    from app.services import challenges

    ch = make_challenge(
        session, status="geplant",
        period_start=date(2026, 8, 1), period_end=date(2026, 8, 31),
    )
    challenges.resolve_due(session, datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc))
    session.refresh(ch)
    assert ch.status == "laufend"


def test_resolve_due_laesst_zukuenftige_challenge_geplant(session):
    from datetime import datetime, timezone

    from app.services import challenges

    ch = make_challenge(
        session, status="geplant",
        period_start=date(2026, 9, 1), period_end=date(2026, 9, 30),
    )
    challenges.resolve_due(session, datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc))
    session.refresh(ch)
    assert ch.status == "geplant"


def test_resolve_due_friert_erst_nach_der_karenz_ein(session):
    from datetime import datetime, timezone

    from app.services import challenges

    make_user(session, username="anna")
    make_category(session, name="Joggen", factor=1.0)
    ch = make_challenge(session, period_end=date(2026, 8, 31))
    # 01.09. 03:00 UTC = 05:00 MESZ, noch vor der Karenzgrenze
    challenges.resolve_due(session, datetime(2026, 9, 1, 3, 0, tzinfo=timezone.utc))
    session.refresh(ch)
    assert ch.status == "laufend"
    challenges.resolve_due(session, datetime(2026, 9, 1, 5, 0, tzinfo=timezone.utc))
    session.refresh(ch)
    assert ch.status == "beendet"


def test_eingefrorenes_ergebnis_aendert_sich_nicht_mehr(session):
    import json
    from datetime import datetime, timezone

    from app.services import challenges

    anna = make_user(session, username="anna")
    lauf = make_category(session, name="Joggen", factor=1.0)
    ch = make_challenge(session, target=100.0, period_end=date(2026, 8, 31))
    add_activity(session, anna.id, lauf.id, date(2026, 8, 5), 120.0)
    challenges.resolve_due(session, datetime(2026, 9, 1, 5, 0, tzinfo=timezone.utc))
    session.refresh(ch)
    ergebnis = json.loads(ch.result_json)
    assert ergebnis["gewinner_ids"] == [anna.id]
    assert ergebnis["entries"][0]["value"] == 120.0
    assert set(ergebnis["entries"][0]) == {"user_id", "value", "rank", "geschafft"}
    assert ch.resolved_at is not None

    # Nachtraeglich eingetragene Aktivitaet darf nichts mehr aendern.
    add_activity(session, anna.id, lauf.id, date(2026, 8, 6), 500.0)
    challenges.resolve_due(session, datetime(2026, 9, 5, 5, 0, tzinfo=timezone.utc))
    session.refresh(ch)
    assert json.loads(ch.result_json)["entries"][0]["value"] == 120.0


def test_resolve_due_ignoriert_abgebrochene(session):
    from datetime import datetime, timezone

    from app.services import challenges

    ch = make_challenge(session, status="abgebrochen", period_end=date(2026, 8, 31))
    challenges.resolve_due(session, datetime(2026, 9, 2, 5, 0, tzinfo=timezone.utc))
    session.refresh(ch)
    assert ch.status == "abgebrochen"
