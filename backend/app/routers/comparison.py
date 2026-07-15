import json
from collections import defaultdict
from datetime import date as date_type
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..deps import get_current_user, get_session
from ..models import Activity, Category, ComparisonSeen, Season, User, utcnow
from ..schemas import (
    CategoryShare,
    ComparisonOut,
    ComparisonUser,
    CumulativePoint,
    LastSeenEntry,
    LastSeenOut,
    Segment,
)

router = APIRouter(prefix="/api/comparison", tags=["comparison"])


def compute_comparison(
    session: Session, year: int, phase: Literal["challenge", "warmup"] = "challenge"
) -> ComparisonOut:
    season = session.exec(select(Season).where(Season.year == year)).first()
    if season is None:
        raise HTTPException(status_code=404, detail="Kein Jahr konfiguriert")

    users = session.exec(select(User).where(User.is_active).order_by(User.id)).all()
    rows = session.exec(
        select(Activity, Category)
        .join(Category, Activity.category_id == Category.id)
        .order_by(Activity.date, Activity.id)
    ).all()
    rows = [(a, c) for a, c in rows if a.date.year == year]

    start = season.start_date
    if phase == "warmup":
        if start is None:
            raise HTTPException(status_code=404, detail="Keine Warm-up-Phase konfiguriert")
        rows = [(a, c) for a, c in rows if a.date < start]
    elif start is not None and date_type.today() >= start:
        rows = [(a, c) for a, c in rows if a.date >= start]

    by_user: dict[int, list[tuple[Activity, Category]]] = defaultdict(list)
    for a, c in rows:
        by_user[a.user_id].append((a, c))

    result_users = []
    for user in users:
        acts = by_user.get(user.id, [])
        segments, cumulative, shares = [], [], defaultdict(float)
        running = 0.0
        factor = user.km_factor if phase == "challenge" else 1.0
        for a, c in acts:
            scaled = round(a.distance_km * c.factor * factor, 2)
            running = round(running + scaled, 2)
            segments.append(
                Segment(date=a.date, category_id=c.id, color=c.color, scaled_km=scaled)
            )
            cumulative.append(CumulativePoint(date=a.date, scaled_km=running))
            shares[c.id] += scaled
        by_category = [
            CategoryShare(
                category_id=c.id,
                name=c.name,
                color=c.color,
                icon=c.icon,
                scaled_km=round(km, 2),
            )
            for c, km in (
                (session.get(Category, cid), km) for cid, km in shares.items()
            )
        ]
        result_users.append(
            ComparisonUser(
                user_id=user.id,
                display_name=user.display_name,
                avatar=user.avatar,
                km_factor=user.km_factor,
                rank=0,
                total_scaled_km=running,
                by_category=by_category,
                segments=segments,
                cumulative=cumulative,
            )
        )

    result_users.sort(key=lambda u: -u.total_scaled_km)
    for i, u in enumerate(result_users):
        u.rank = i + 1

    return ComparisonOut(
        year=year,
        goal_km=season.goal_km,
        milestones=json.loads(season.milestones_json),
        users=result_users,
        start_date=season.start_date,
        phase=phase,
    )


@router.get(
    "/{year}", response_model=ComparisonOut, dependencies=[Depends(get_current_user)]
)
def comparison(
    year: int,
    phase: Literal["challenge", "warmup"] = "challenge",
    session: Session = Depends(get_session),
):
    return compute_comparison(session, year, phase)


@router.get("/{year}/last-seen", response_model=LastSeenOut | None)
def last_seen(
    year: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    row = session.exec(
        select(ComparisonSeen).where(
            ComparisonSeen.user_id == user.id, ComparisonSeen.year == year
        )
    ).first()
    if row is None:
        return None
    return LastSeenOut(
        seen_at=row.seen_at,
        entries=[LastSeenEntry(**e) for e in json.loads(row.snapshot_json)],
    )


@router.post("/{year}/seen", response_model=LastSeenOut)
def mark_seen(
    year: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    data = compute_comparison(session, year, "challenge")
    entries = [
        LastSeenEntry(user_id=u.user_id, scaled_km=u.total_scaled_km, rank=u.rank)
        for u in data.users
    ]
    row = session.exec(
        select(ComparisonSeen).where(
            ComparisonSeen.user_id == user.id, ComparisonSeen.year == year
        )
    ).first()
    payload = json.dumps([e.model_dump() for e in entries])
    now = utcnow()
    if row is None:
        row = ComparisonSeen(
            user_id=user.id, year=year, seen_at=now, snapshot_json=payload
        )
    else:
        row.seen_at = now
        row.snapshot_json = payload
    session.add(row)
    session.commit()
    return LastSeenOut(seen_at=now, entries=entries)
