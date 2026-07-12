"""Punkte-Ledger: Kontostand = Summe aller PointTransactions.

Einkommen (+1 Punkt je 5 gewertete km ab Challenge-Start) wird idempotent
nachgebucht: Soll = floor(km/5), gebucht wird nur die Differenz zum bereits
gutgeschriebenen Einkommen. Kein Cron nötig.
"""

import math
from datetime import date as date_type

from sqlmodel import Session, func, select

from ..models import Activity, Category, PointTransaction, Season, User

START_CREDIT = 100
KM_PER_POINT = 5.0


def balance(session: Session, user_id: int) -> int:
    total = session.exec(
        select(func.coalesce(func.sum(PointTransaction.amount), 0)).where(
            PointTransaction.user_id == user_id
        )
    ).one()
    return int(total)


def ensure_start_credit(session: Session, user_id: int) -> None:
    exists = session.exec(
        select(PointTransaction).where(
            PointTransaction.user_id == user_id, PointTransaction.reason == "start"
        )
    ).first()
    if exists is None:
        session.add(
            PointTransaction(user_id=user_id, amount=START_CREDIT, reason="start")
        )
        session.commit()


def challenge_start(session: Session) -> date_type | None:
    season = session.exec(
        select(Season).where(Season.year == date_type.today().year)
    ).first()
    return season.start_date if season else None


def scaled_km_since_start(session: Session, user_id: int) -> float:
    start = challenge_start(session)
    if start is None or date_type.today() < start:
        return 0.0
    user = session.get(User, user_id)
    cats = {c.id: c for c in session.exec(select(Category)).all()}
    acts = session.exec(
        select(Activity).where(Activity.user_id == user_id, Activity.date >= start)
    ).all()
    return sum(
        a.distance_km * cats[a.category_id].factor * user.km_factor
        for a in acts
        if a.category_id in cats
    )


def ensure_income(session: Session, user_id: int) -> None:
    earned = math.floor(scaled_km_since_start(session, user_id) / KM_PER_POINT)
    booked = session.exec(
        select(func.coalesce(func.sum(PointTransaction.amount), 0)).where(
            PointTransaction.user_id == user_id,
            PointTransaction.reason == "einkommen",
        )
    ).one()
    if earned > int(booked):
        session.add(
            PointTransaction(
                user_id=user_id, amount=earned - int(booked), reason="einkommen"
            )
        )
        session.commit()


def refresh_user(session: Session, user_id: int) -> None:
    ensure_start_credit(session, user_id)
    ensure_income(session, user_id)
