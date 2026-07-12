import json
from datetime import date, timedelta

from sqlmodel import select

from app.models import Activity, Bet, BetParticipant, PointTransaction, Season
from app.services import bets, points
from tests.conftest import make_category, make_user

HEUTE = date.today()
START = HEUTE - timedelta(days=30)  # Challenge läuft seit einem Monat
P_START = HEUTE - timedelta(days=8)
P_ENDE = HEUTE - timedelta(days=1)  # Zeitraum vorbei -> fällig


def _setup(session, extra_user=None):
    session.add(
        Season(year=HEUTE.year, goal_km=1000, milestones_json="[]", start_date=START)
    )
    users = [make_user(session), make_user(session, username="lisa")]
    if extra_user:
        users.append(make_user(session, username=extra_user))
    cat = make_category(session, factor=1.0)
    session.commit()
    for u in users:
        points.ensure_start_credit(session, u.id)
    return (*users, cat)


def _mk_bet(session, creator, typ, stake, params, participants):
    """Fällige Wette direkt anlegen (Zeitraum liegt in der Vergangenheit)."""
    bet = Bet(
        type=typ,
        creator_id=creator.id,
        title="Test",
        stake=stake,
        period_start=P_START,
        period_end=P_ENDE,
        status="laufend" if typ != "duell" else "laufend",
        params_json=json.dumps(params),
    )
    session.add(bet)
    session.commit()
    session.refresh(bet)
    for user, role, p_stake, choice in participants:
        session.add(
            BetParticipant(
                bet_id=bet.id,
                user_id=user.id,
                role=role,
                stake=p_stake,
                choice_json=json.dumps(choice or {}),
            )
        )
        session.add(
            PointTransaction(
                user_id=user.id, amount=-p_stake, reason="einsatz", bet_id=bet.id
            )
        )
    session.commit()
    return bet


def _act(session, user, cat, km, d):
    session.add(Activity(user_id=user.id, category_id=cat.id, date=d, distance_km=km))
    session.commit()


def test_duell_gewinner_bekommt_pott(session):
    erik, lisa, cat = _setup(session)
    _act(session, erik, cat, 10, P_START)
    _act(session, lisa, cat, 5, P_START)
    bet = _mk_bet(
        session, erik, "duell", 20,
        {"opponent_id": lisa.id},
        [(erik, "ersteller", 20, None), (lisa, "gegner", 20, None)],
    )
    bets.resolve_due(session)
    session.refresh(bet)
    assert bet.status == "entschieden"
    assert points.balance(session, erik.id) == 120
    assert points.balance(session, lisa.id) == 80
    assert json.loads(bet.result_json)["winner_ids"] == [erik.id]


def test_duell_handicap_faktor_und_vorsprung(session):
    erik, lisa, cat = _setup(session)
    _act(session, erik, cat, 10, P_START)
    _act(session, lisa, cat, 4, P_START)
    # Lisa kriegt 2 km Vorsprung und Faktor 2: (4+2)*2 = 12 > 10 -> Lisa gewinnt
    bet = _mk_bet(
        session, erik, "duell", 20,
        {"opponent_id": lisa.id, "vorsprung_km": 2.0, "factor_opponent": 2.0},
        [(erik, "ersteller", 20, None), (lisa, "gegner", 20, None)],
    )
    bets.resolve_due(session)
    session.refresh(bet)
    assert json.loads(bet.result_json)["winner_ids"] == [lisa.id]
    assert points.balance(session, lisa.id) == 120


def test_duell_gleichstand_einsaetze_zurueck(session):
    erik, lisa, cat = _setup(session)
    bet = _mk_bet(
        session, erik, "duell", 20,
        {"opponent_id": lisa.id},
        [(erik, "ersteller", 20, None), (lisa, "gegner", 20, None)],
    )
    bets.resolve_due(session)
    session.refresh(bet)
    assert bet.status == "entschieden"
    assert points.balance(session, erik.id) == 100
    assert points.balance(session, lisa.id) == 100


def test_duell_david_flag(session):
    erik, lisa, cat = _setup(session)
    # Lisa führt das Jahresranking deutlich an ...
    _act(session, lisa, cat, 100, START + timedelta(days=1))
    # ... aber Erik gewinnt das Duell im Zeitraum.
    _act(session, erik, cat, 5, P_START)
    _act(session, lisa, cat, 4, P_START)
    bet = _mk_bet(
        session, erik, "duell", 10,
        {"opponent_id": lisa.id},
        [(erik, "ersteller", 10, None), (lisa, "gegner", 10, None)],
    )
    bets.resolve_due(session)
    session.refresh(bet)
    assert json.loads(bet.result_json)["david"] is True


def test_ziel_erreicht_ersteller_kassiert(session):
    erik, lisa, cat = _setup(session)
    _act(session, erik, cat, 12, P_START)
    bet = _mk_bet(
        session, erik, "ziel", 20,
        {"target_km": 10.0},
        [(erik, "ersteller", 20, None), (lisa, "gegenhalter", 15, None)],
    )
    bets.resolve_due(session)
    session.refresh(bet)
    assert points.balance(session, erik.id) == 115  # 100 - 20 + 35
    assert points.balance(session, lisa.id) == 85


def test_ziel_verfehlt_gegenhalter_teilen_proportional(session):
    session.add(
        Season(year=HEUTE.year, goal_km=1000, milestones_json="[]", start_date=START)
    )
    erik = make_user(session)
    lisa = make_user(session, username="lisa")
    mia = make_user(session, username="mia")
    make_category(session, factor=1.0)
    session.commit()
    for u in (erik, lisa, mia):
        points.ensure_start_credit(session, u.id)
    # Erik verfehlt (keine Aktivität). Gegenhalter: Lisa 7, Mia 6 (Summe 13 <= 20)
    bet = _mk_bet(
        session, erik, "ziel", 20,
        {"target_km": 10.0},
        [
            (erik, "ersteller", 20, None),
            (lisa, "gegenhalter", 7, None),
            (mia, "gegenhalter", 6, None),
        ],
    )
    bets.resolve_due(session)
    session.refresh(bet)
    # Anteile: floor(7/13*20)=10, floor(6/13*20)=9, Rest 1 an frühesten (Lisa)
    assert points.balance(session, erik.id) == 80
    assert points.balance(session, lisa.id) == 100 - 7 + 7 + 10 + 1
    assert points.balance(session, mia.id) == 100 - 6 + 6 + 9


def test_ziel_ohne_gegenhalter_abgebrochen(session):
    erik, lisa, cat = _setup(session)
    bet = _mk_bet(
        session, erik, "ziel", 20, {"target_km": 10.0},
        [(erik, "ersteller", 20, None)],
    )
    bets.resolve_due(session)
    session.refresh(bet)
    assert bet.status == "abgebrochen"
    assert points.balance(session, erik.id) == 100


def test_streak_erreicht(session):
    erik, lisa, cat = _setup(session)
    for i in range(3):
        _act(session, erik, cat, 2, P_START + timedelta(days=i))
    bet = _mk_bet(
        session, erik, "streak", 10,
        {"streak_days": 3},
        [(erik, "ersteller", 10, None), (lisa, "gegenhalter", 10, None)],
    )
    bets.resolve_due(session)
    assert points.balance(session, erik.id) == 110
    assert points.balance(session, lisa.id) == 90


def test_ueber_unter(session):
    erik, lisa, cat = _setup(session)
    _act(session, erik, cat, 7, P_START)
    _act(session, lisa, cat, 5, P_START)  # Gruppe: 12 >= 10 -> Über gewinnt
    bet = _mk_bet(
        session, erik, "ueber_unter", 10,
        {"target_km": 10.0},
        [(erik, "ueber", 10, None), (lisa, "unter", 10, None)],
    )
    bets.resolve_due(session)
    session.refresh(bet)
    assert points.balance(session, erik.id) == 110
    assert points.balance(session, lisa.id) == 90


def test_ueber_unter_eine_seite_leer(session):
    erik, lisa, cat = _setup(session)
    bet = _mk_bet(
        session, erik, "ueber_unter", 10,
        {"target_km": 10.0},
        [(erik, "ueber", 10, None), (lisa, "ueber", 10, None)],
    )
    bets.resolve_due(session)
    session.refresh(bet)
    assert bet.status == "entschieden"
    assert points.balance(session, erik.id) == 100
    assert points.balance(session, lisa.id) == 100


def test_monats_tipp_richtige_teilen_pott(session):
    session.add(
        Season(year=HEUTE.year, goal_km=1000, milestones_json="[]", start_date=START)
    )
    erik = make_user(session)
    lisa = make_user(session, username="lisa")
    mia = make_user(session, username="mia")
    cat = make_category(session, factor=1.0)
    session.commit()
    for u in (erik, lisa, mia):
        points.ensure_start_credit(session, u.id)
    _act(session, lisa, cat, 50, P_START)  # Lisa gewinnt den Zeitraum
    bet = _mk_bet(
        session, erik, "monats_tipp", 10,
        {"month": P_START.strftime("%Y-%m")},
        [
            (erik, "tipper", 10, {"tipp_user_id": lisa.id}),
            (lisa, "tipper", 10, {"tipp_user_id": lisa.id}),
            (mia, "tipper", 10, {"tipp_user_id": erik.id}),
        ],
    )
    bets.resolve_due(session)
    session.refresh(bet)
    # Pott 30, zwei Richtige -> je 15
    assert points.balance(session, erik.id) == 105
    assert points.balance(session, lisa.id) == 105
    assert points.balance(session, mia.id) == 90


def test_monats_tipp_niemand_richtig_jackpot_rollt(session):
    erik, lisa, cat = _setup(session)
    _act(session, lisa, cat, 50, P_START)
    bet = _mk_bet(
        session, erik, "monats_tipp", 10,
        {"month": P_START.strftime("%Y-%m")},
        [(erik, "tipper", 10, {"tipp_user_id": erik.id})],
    )
    bets.resolve_due(session)
    session.refresh(bet)
    assert bet.status == "entschieden"
    assert points.balance(session, erik.id) == 90
    naechste = session.exec(
        select(Bet).where(Bet.type == "monats_tipp", Bet.status == "laufend")
    ).first()
    assert naechste is not None and naechste.jackpot == 10


def test_deaktivierter_teilnehmer_bricht_wette_ab(session):
    erik, lisa, cat = _setup(session)
    bet = _mk_bet(
        session, erik, "duell", 20,
        {"opponent_id": lisa.id},
        [(erik, "ersteller", 20, None), (lisa, "gegner", 20, None)],
    )
    lisa.is_active = False
    session.add(lisa)
    session.commit()
    bets.resolve_due(session)
    session.refresh(bet)
    assert bet.status == "abgebrochen"
    assert points.balance(session, erik.id) == 100
    assert points.balance(session, lisa.id) == 100
