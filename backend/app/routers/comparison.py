import json
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..deps import get_current_user, get_session
from ..models import Activity, Category, Season, User
from ..schemas import (
    CategoryShare,
    ComparisonOut,
    ComparisonUser,
    CumulativePoint,
    Segment,
)

router = APIRouter(prefix="/api/comparison", tags=["comparison"])


@router.get(
    "/{year}", response_model=ComparisonOut, dependencies=[Depends(get_current_user)]
)
def comparison(year: int, session: Session = Depends(get_session)):
    season = session.exec(select(Season).where(Season.year == year)).first()
    if season is None:
        raise HTTPException(status_code=404, detail="Kein Jahr konfiguriert")

    users = session.exec(select(User).order_by(User.id)).all()
    rows = session.exec(
        select(Activity, Category)
        .join(Category, Activity.category_id == Category.id)
        .order_by(Activity.date, Activity.id)
    ).all()
    rows = [(a, c) for a, c in rows if a.date.year == year]

    by_user: dict[int, list[tuple[Activity, Category]]] = defaultdict(list)
    for a, c in rows:
        by_user[a.user_id].append((a, c))

    result_users = []
    for user in users:
        acts = by_user.get(user.id, [])
        segments, cumulative, shares = [], [], defaultdict(float)
        running = 0.0
        for a, c in acts:
            scaled = round(a.distance_km * c.factor, 2)
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
    )
