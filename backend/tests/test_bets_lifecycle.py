from datetime import date, timedelta

import pytest
from sqlmodel import select

from app.models import Bet, Season
from app.services import bets, points
from tests.conftest import make_user

HEUTE = date.today()
MORGEN = HEUTE + timedelta(days=1)
IN_ACHT = HEUTE + timedelta(days=8)


def _setup(session):
    """Season mit laufender Challenge; Erik + Lisa mit je 100 Punkten."""
    session.add(
        Season(
            year=HEUTE.year,
            goal_km=1000,
            milestones_json="[]",
            start_date=HEUTE - timedelta(days=10),
        )
    )
    erik = make_user(session)
    lisa = make_user(session, username="lisa")
    session.commit()
    points.ensure_start_credit(session, erik.id)
    points.ensure_start_credit(session, lisa.id)
    return erik, lisa


def _duell(session, erik, lisa, stake=20, **params):
    return bets.create_bet(
        session,
        erik,
        type="duell",
        title="Erik vs. Lisa",
        stake=stake,
        period_start=MORGEN,
        period_end=IN_ACHT,
        params={"opponent_id": lisa.id, **params},
    )


def test_create_duell_bucht_ersteller_einsatz(session):
    erik, lisa = _setup(session)
    bet = _duell(session, erik, lisa)
    assert bet.status == "offen"
    assert points.balance(session, erik.id) == 80
    assert points.balance(session, lisa.id) == 100


def test_accept_bucht_gegner_einsatz(session):
    erik, lisa = _setup(session)
    bet = _duell(session, erik, lisa)
    bets.respond(session, bet, lisa, action="accept")
    assert bet.status == "laufend"
    assert points.balance(session, lisa.id) == 80


def test_decline_zahlt_ersteller_zurueck(session):
    erik, lisa = _setup(session)
    bet = _duell(session, erik, lisa)
    bets.respond(session, bet, lisa, action="decline")
    assert bet.status == "abgelehnt"
    assert points.balance(session, erik.id) == 100


def test_einsatz_ueber_kontostand_abgelehnt(session):
    erik, lisa = _setup(session)
    with pytest.raises(ValueError, match="Nicht genug Punkte"):
        _duell(session, erik, lisa, stake=101)


def test_period_start_muss_in_zukunft_liegen(session):
    erik, lisa = _setup(session)
    with pytest.raises(ValueError, match="Zukunft"):
        bets.create_bet(
            session,
            erik,
            type="duell",
            title="x",
            stake=10,
            period_start=HEUTE,
            period_end=IN_ACHT,
            params={"opponent_id": lisa.id},
        )


def test_gegenhalten_begrenzt_auf_ersteller_einsatz(session):
    erik, lisa = _setup(session)
    bet = bets.create_bet(
        session,
        erik,
        type="ziel",
        title="30 km diese Woche",
        stake=20,
        period_start=MORGEN,
        period_end=IN_ACHT,
        params={"target_km": 30.0},
    )
    bets.respond(session, bet, lisa, action="dagegenhalten", stake=15)
    with pytest.raises(ValueError, match="[Mm]aximal"):
        bets.respond(session, bet, lisa, action="dagegenhalten", stake=6)
    assert points.balance(session, lisa.id) == 85


def test_cancel_vor_start_zahlt_alle_zurueck(session):
    erik, lisa = _setup(session)
    bet = bets.create_bet(
        session,
        erik,
        type="ziel",
        title="30 km",
        stake=20,
        period_start=MORGEN,
        period_end=IN_ACHT,
        params={"target_km": 30.0},
    )
    bets.respond(session, bet, lisa, action="dagegenhalten", stake=10)
    bets.cancel(session, bet, erik)
    assert bet.status == "abgebrochen"
    assert points.balance(session, erik.id) == 100
    assert points.balance(session, lisa.id) == 100


def test_ensure_monthly_tip_idempotent_und_ab_august(session):
    _setup(session)
    bets.ensure_monthly_tip(session)
    bets.ensure_monthly_tip(session)
    tips = session.exec(select(Bet).where(Bet.type == "monats_tipp")).all()
    if HEUTE >= date(2026, 8, 1):
        assert len(tips) == 1
        assert tips[0].period_start == HEUTE.replace(day=1)
    else:
        assert tips == []  # vor August 2026 keine Tipprunde
