"""Wett-Engine: Lifecycle (erstellen, antworten, stornieren) und Auflösung.

Alle Regeln aus der Spec 2026-07-12-countdown-warmup-sidebets-design.md:
- Einsätze werden sofort als PointTransaction "einsatz" gebucht.
- Auflösung läuft lazy über resolve_due() bei jedem API-Zugriff, kein Cron.
- Gleichstand / leere Seite / kein Gegenhalter -> Einsätze zurück.
- Fehler werden als ValueError mit deutscher Meldung geworfen; der Router
  übersetzt sie in HTTP 400.
"""

import json
import math
from datetime import date as date_type
from datetime import timedelta

from sqlmodel import Session, select

from ..models import Bet, BetParticipant, PointTransaction, Season, User, utcnow
from . import bet_metrics, points

FIRST_TIP_MONTH = date_type(2026, 8, 1)  # Juli-Tippschluss läge vor Challenge-Start
TIP_STAKE = 10
TIP_DEADLINE_DAY = 5

BET_TYPES = ("duell", "monats_tipp", "ziel", "streak", "ueber_unter")


def _params(bet: Bet) -> dict:
    return json.loads(bet.params_json or "{}")


def _participants(session: Session, bet: Bet) -> list[BetParticipant]:
    return list(
        session.exec(
            select(BetParticipant)
            .where(BetParticipant.bet_id == bet.id)
            .order_by(BetParticipant.id)
        ).all()
    )


def _debit(session: Session, user_id: int, amount: int, bet_id: int | None) -> None:
    points.refresh_user(session, user_id)
    if points.balance(session, user_id) < amount:
        raise ValueError("Nicht genug Punkte")
    session.add(
        PointTransaction(user_id=user_id, amount=-amount, reason="einsatz", bet_id=bet_id)
    )


def _credit(
    session: Session, user_id: int, amount: int, bet_id: int, reason: str = "gewinn"
) -> None:
    if amount > 0:
        session.add(
            PointTransaction(user_id=user_id, amount=amount, reason=reason, bet_id=bet_id)
        )


def _month_end(first_day: date_type) -> date_type:
    naechster = (first_day.replace(day=28) + timedelta(days=4)).replace(day=1)
    return naechster - timedelta(days=1)


def _season_start(session: Session) -> date_type | None:
    season = session.exec(
        select(Season).where(Season.year == date_type.today().year)
    ).first()
    return season.start_date if season else None


# ---------------------------------------------------------------- Lifecycle


def create_bet(
    session: Session,
    creator: User,
    *,
    type: str,
    title: str,
    stake: int,
    period_start: date_type,
    period_end: date_type,
    params: dict,
) -> Bet:
    if type not in ("duell", "ziel", "streak", "ueber_unter"):
        raise ValueError("Unbekannter Wett-Typ")
    if stake <= 0:
        raise ValueError("Einsatz muss positiv sein")
    today = date_type.today()
    if period_start <= today:
        raise ValueError("Zeitraum muss in der Zukunft beginnen")
    if period_end < period_start:
        raise ValueError("Zeitraum-Ende liegt vor dem Start")
    start = _season_start(session)
    if start is not None and period_start < start:
        raise ValueError("Wetten gibt es erst ab dem Challenge-Start")

    role = "ersteller"
    if type == "duell":
        opponent = session.get(User, int(params.get("opponent_id", 0)))
        if opponent is None or not opponent.is_active:
            raise ValueError("Gegner nicht gefunden")
        if opponent.id == creator.id:
            raise ValueError("Gegen dich selbst kannst du kein Duell starten")
    elif type == "ziel":
        if float(params.get("target_km", 0)) <= 0:
            raise ValueError("Ziel-km müssen positiv sein")
    elif type == "streak":
        tage = int(params.get("streak_days", 0))
        max_tage = (period_end - period_start).days + 1
        if not 1 <= tage <= max_tage:
            raise ValueError("Streak-Tage passen nicht in den Zeitraum")
    elif type == "ueber_unter":
        if float(params.get("target_km", 0)) <= 0:
            raise ValueError("Gruppen-Ziel muss positiv sein")
        role = params.get("side", "ueber")
        if role not in ("ueber", "unter"):
            raise ValueError("Seite muss 'ueber' oder 'unter' sein")

    bet = Bet(
        type=type,
        creator_id=creator.id,
        title=title,
        stake=stake,
        period_start=period_start,
        period_end=period_end,
        status="offen" if type == "duell" else "laufend",
        params_json=json.dumps(params),
    )
    session.add(bet)
    session.commit()
    session.refresh(bet)
    _debit(session, creator.id, stake, bet.id)
    session.add(
        BetParticipant(bet_id=bet.id, user_id=creator.id, role=role, stake=stake)
    )
    session.commit()
    session.refresh(bet)
    return bet


def respond(
    session: Session,
    bet: Bet,
    user: User,
    *,
    action: str,
    stake: int | None = None,
    choice: dict | None = None,
) -> Bet:
    today = date_type.today()
    p = _params(bet)

    if action in ("accept", "decline"):
        if bet.type != "duell" or bet.status != "offen":
            raise ValueError("Dieses Duell ist nicht mehr offen")
        if user.id != int(p.get("opponent_id", 0)):
            raise ValueError("Nur der Herausgeforderte kann antworten")
        if action == "accept":
            _debit(session, user.id, bet.stake, bet.id)
            session.add(
                BetParticipant(
                    bet_id=bet.id, user_id=user.id, role="gegner", stake=bet.stake
                )
            )
            bet.status = "laufend"
        else:
            _refund_all(session, bet)
            bet.status = "abgelehnt"

    elif action == "dagegenhalten":
        if bet.type not in ("ziel", "streak") or bet.status != "laufend":
            raise ValueError("Hier kann man nicht dagegenhalten")
        if today >= bet.period_start:
            raise ValueError("Der Zeitraum hat schon begonnen")
        if user.id == bet.creator_id:
            raise ValueError("Gegen die eigene Wette geht nicht")
        if stake is None or stake <= 0:
            raise ValueError("Einsatz muss positiv sein")
        bisher = sum(
            t.stake for t in _participants(session, bet) if t.role == "gegenhalter"
        )
        rest = bet.stake - bisher
        if stake > rest:
            raise ValueError(f"Maximal {rest} Punkte können noch dagegenhalten")
        _debit(session, user.id, stake, bet.id)
        session.add(
            BetParticipant(
                bet_id=bet.id, user_id=user.id, role="gegenhalter", stake=stake
            )
        )

    elif action in ("ueber", "unter"):
        if bet.type != "ueber_unter" or bet.status != "laufend":
            raise ValueError("Diese Gruppenwette läuft nicht")
        if today >= bet.period_start:
            raise ValueError("Der Zeitraum hat schon begonnen")
        if any(t.user_id == user.id for t in _participants(session, bet)):
            raise ValueError("Du bist schon dabei")
        _debit(session, user.id, bet.stake, bet.id)
        session.add(
            BetParticipant(bet_id=bet.id, user_id=user.id, role=action, stake=bet.stake)
        )

    elif action == "tippen":
        if bet.type != "monats_tipp" or bet.status != "laufend":
            raise ValueError("Diese Tipprunde läuft nicht")
        if today > bet.period_start.replace(day=TIP_DEADLINE_DAY):
            raise ValueError(f"Tippschluss war am {TIP_DEADLINE_DAY}. des Monats")
        if any(t.user_id == user.id for t in _participants(session, bet)):
            raise ValueError("Du hast schon getippt")
        tipp_id = int((choice or {}).get("tipp_user_id", 0))
        getippter = session.get(User, tipp_id)
        if getippter is None or not getippter.is_active:
            raise ValueError("Getippter Spieler nicht gefunden")
        _debit(session, user.id, bet.stake, bet.id)
        session.add(
            BetParticipant(
                bet_id=bet.id,
                user_id=user.id,
                role="tipper",
                stake=bet.stake,
                choice_json=json.dumps({"tipp_user_id": tipp_id}),
            )
        )

    else:
        raise ValueError("Unbekannte Aktion")

    session.add(bet)
    session.commit()
    session.refresh(bet)
    return bet


def cancel(session: Session, bet: Bet, user: User) -> Bet:
    if bet.type == "monats_tipp":
        raise ValueError("Die Tipprunde kann nicht storniert werden")
    if user.id != bet.creator_id:
        raise ValueError("Nur wer die Wette erstellt hat, kann stornieren")
    if bet.status not in ("offen", "laufend"):
        raise ValueError("Diese Wette läuft nicht mehr")
    if date_type.today() >= bet.period_start:
        raise ValueError("Der Zeitraum hat schon begonnen")
    _refund_all(session, bet)
    bet.status = "abgebrochen"
    session.add(bet)
    session.commit()
    session.refresh(bet)
    return bet


def ensure_monthly_tip(session: Session) -> None:
    today = date_type.today()
    if today < FIRST_TIP_MONTH:
        return
    start = _season_start(session)
    if start is None or today < start:
        return
    month_start = today.replace(day=1)
    exists = session.exec(
        select(Bet).where(
            Bet.type == "monats_tipp", Bet.period_start == month_start
        )
    ).first()
    if exists is not None:
        return
    creator = session.exec(
        select(User).where(User.is_active, User.is_admin).order_by(User.id)
    ).first() or session.exec(select(User).order_by(User.id)).first()
    if creator is None:
        return
    session.add(
        Bet(
            type="monats_tipp",
            creator_id=creator.id,
            title=f"Monats-Tipp {month_start.strftime('%m/%Y')}",
            stake=TIP_STAKE,
            period_start=month_start,
            period_end=_month_end(month_start),
            status="laufend",
            params_json=json.dumps({"month": month_start.strftime("%Y-%m")}),
        )
    )
    session.commit()


# ---------------------------------------------------------------- Auflösung


def _refund_all(session: Session, bet: Bet) -> None:
    for t in _participants(session, bet):
        if t.payout is None:
            _credit(session, t.user_id, t.stake, bet.id, reason="rueckzahlung")
            t.payout = t.stake
            session.add(t)


def _finish(session: Session, bet: Bet, status: str, result: dict) -> None:
    bet.status = status
    bet.resolved_at = utcnow()
    bet.result_json = json.dumps(result)
    session.add(bet)
    session.commit()


def _challenge_totals(session: Session) -> dict[int, float]:
    """Jahres-Challenge-km (inkl. km_factor) je aktivem User — für das David-Flag."""
    today = date_type.today()
    start = _season_start(session) or date_type(today.year, 1, 1)
    users = session.exec(select(User).where(User.is_active)).all()
    return {
        u.id: bet_metrics.scaled_km(session, u.id, start, today) * u.km_factor
        for u in users
    }


def _resolve_duell(session: Session, bet: Bet) -> None:
    p = _params(bet)
    parts = _participants(session, bet)
    ersteller = next(t for t in parts if t.role == "ersteller")
    gegner = next(t for t in parts if t.role == "gegner")
    km_c = bet_metrics.scaled_km(
        session, ersteller.user_id, bet.period_start, bet.period_end
    )
    km_o = bet_metrics.scaled_km(
        session, gegner.user_id, bet.period_start, bet.period_end
    )
    val_c = round(km_c * float(p.get("factor_creator", 1.0)), 2)
    val_o = round(
        (km_o + float(p.get("vorsprung_km", 0.0))) * float(p.get("factor_opponent", 1.0)),
        2,
    )
    result = {"creator_km": km_c, "opponent_km": km_o,
              "creator_value": val_c, "opponent_value": val_o, "david": False}
    if val_c == val_o:
        _refund_all(session, bet)
        result["winner_ids"] = []
    else:
        winner, loser = (ersteller, gegner) if val_c > val_o else (gegner, ersteller)
        _credit(session, winner.user_id, 2 * bet.stake, bet.id)
        winner.payout = 2 * bet.stake
        loser.payout = 0
        session.add(winner)
        session.add(loser)
        result["winner_ids"] = [winner.user_id]
        totals = _challenge_totals(session)
        result["david"] = totals.get(winner.user_id, 0.0) < totals.get(
            loser.user_id, 0.0
        )
    _finish(session, bet, "entschieden", result)


def _resolve_ziel(session: Session, bet: Bet) -> None:
    p = _params(bet)
    parts = _participants(session, bet)
    ersteller = next(t for t in parts if t.role == "ersteller")
    counters = [t for t in parts if t.role == "gegenhalter"]
    if not counters:
        _refund_all(session, bet)
        _finish(session, bet, "abgebrochen", {"grund": "keine Gegenhalter"})
        return
    if bet.type == "streak":
        ist = bet_metrics.longest_streak(
            session, ersteller.user_id, bet.period_start, bet.period_end
        )
        erreicht = ist >= int(p["streak_days"])
    else:
        ist = bet_metrics.scaled_km(
            session, ersteller.user_id, bet.period_start, bet.period_end
        )
        erreicht = ist >= float(p["target_km"])
    result = {"ist": ist, "erreicht": erreicht}
    if erreicht:
        summe = bet.stake + sum(t.stake for t in counters)
        _credit(session, ersteller.user_id, summe, bet.id)
        ersteller.payout = summe
        for t in counters:
            t.payout = 0
            session.add(t)
        session.add(ersteller)
        result["winner_ids"] = [ersteller.user_id]
    else:
        total = sum(t.stake for t in counters)
        shares = [math.floor(t.stake / total * bet.stake) for t in counters]
        shares[0] += bet.stake - sum(shares)  # Rest an den frühesten Gegenhalter
        for t, share in zip(counters, shares):
            t.payout = t.stake + share
            _credit(session, t.user_id, t.payout, bet.id)
            session.add(t)
        ersteller.payout = 0
        session.add(ersteller)
        result["winner_ids"] = [t.user_id for t in counters]
    _finish(session, bet, "entschieden", result)


def _resolve_ueber_unter(session: Session, bet: Bet) -> None:
    p = _params(bet)
    parts = _participants(session, bet)
    aktive = session.exec(select(User).where(User.is_active)).all()
    gruppe = bet_metrics.group_scaled_km(
        session, [u.id for u in aktive], bet.period_start, bet.period_end
    )
    gewinner_rolle = "ueber" if gruppe >= float(p["target_km"]) else "unter"
    winners = [t for t in parts if t.role == gewinner_rolle]
    losers = [t for t in parts if t.role != gewinner_rolle]
    result = {"gruppen_km": gruppe, "gewonnen": gewinner_rolle}
    if not winners or not losers:
        _refund_all(session, bet)
        result["winner_ids"] = []
    else:
        loser_total = sum(t.stake for t in losers)
        winner_total = sum(t.stake for t in winners)
        shares = [math.floor(t.stake / winner_total * loser_total) for t in winners]
        shares[0] += loser_total - sum(shares)
        for t, share in zip(winners, shares):
            t.payout = t.stake + share
            _credit(session, t.user_id, t.payout, bet.id)
            session.add(t)
        for t in losers:
            t.payout = 0
            session.add(t)
        result["winner_ids"] = [t.user_id for t in winners]
    _finish(session, bet, "entschieden", result)


def _resolve_monats_tipp(session: Session, bet: Bet) -> None:
    parts = _participants(session, bet)
    tipper = [t for t in parts if t.role == "tipper"]
    aktive = session.exec(select(User).where(User.is_active)).all()
    totals = {
        u.id: round(
            bet_metrics.scaled_km(session, u.id, bet.period_start, bet.period_end)
            * u.km_factor,
            2,
        )
        for u in aktive
    }
    best = max(totals.values(), default=0.0)
    winner_ids = [uid for uid, km in totals.items() if km == best]
    richtige = [
        t
        for t in tipper
        if int(json.loads(t.choice_json or "{}").get("tipp_user_id", 0)) in winner_ids
    ]
    pot = sum(t.stake for t in tipper) + bet.jackpot
    rest = pot
    if richtige:
        share = math.floor(pot / len(richtige))
        rest = pot - share * len(richtige)
        for t in richtige:
            t.payout = share
            _credit(session, t.user_id, share, bet.id)
            session.add(t)
    for t in tipper:
        if t.payout is None:
            t.payout = 0
            session.add(t)
    if rest > 0:
        _roll_jackpot(session, bet, rest)
    _finish(
        session,
        bet,
        "entschieden",
        {"monats_sieger": winner_ids, "pot": pot, "jackpot_weiter": rest,
         "winner_ids": [t.user_id for t in richtige]},
    )


def _roll_jackpot(session: Session, bet: Bet, rest: int) -> None:
    naechste = session.exec(
        select(Bet).where(
            Bet.type == "monats_tipp",
            Bet.status == "laufend",
            Bet.id != bet.id,
        )
    ).first()
    if naechste is None:
        month_start = date_type.today().replace(day=1)
        naechste = Bet(
            type="monats_tipp",
            creator_id=bet.creator_id,
            title=f"Monats-Tipp {month_start.strftime('%m/%Y')}",
            stake=TIP_STAKE,
            period_start=month_start,
            period_end=_month_end(month_start),
            status="laufend",
            params_json=json.dumps({"month": month_start.strftime("%Y-%m")}),
        )
    naechste.jackpot += rest
    session.add(naechste)


def resolve_due(session: Session) -> None:
    today = date_type.today()
    # Nicht angenommene Duelle verfallen zum Zeitraum-Start.
    for bet in session.exec(
        select(Bet).where(Bet.status == "offen").order_by(Bet.created_at)
    ).all():
        if bet.period_start <= today:
            _refund_all(session, bet)
            _finish(session, bet, "abgebrochen", {"grund": "nicht angenommen"})

    for bet in session.exec(
        select(Bet).where(Bet.status == "laufend").order_by(Bet.created_at)
    ).all():
        if bet.period_end >= today:
            continue
        parts = _participants(session, bet)
        users = [session.get(User, t.user_id) for t in parts]
        if any(u is None or not u.is_active for u in users):
            _refund_all(session, bet)
            _finish(session, bet, "abgebrochen", {"grund": "Teilnehmer inaktiv"})
            continue
        if bet.type == "duell":
            _resolve_duell(session, bet)
        elif bet.type in ("ziel", "streak"):
            _resolve_ziel(session, bet)
        elif bet.type == "ueber_unter":
            _resolve_ueber_unter(session, bet)
        elif bet.type == "monats_tipp":
            _resolve_monats_tipp(session, bet)
