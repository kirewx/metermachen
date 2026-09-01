import json
from collections import defaultdict
from datetime import date as date_type
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..deps import get_current_user, get_session
from ..models import (
    AchievementUnlock,
    Activity,
    Category,
    ComparisonSeen,
    Season,
    User,
    utcnow,
)
from ..services.achievements import SHOWCASE_INFO
from ..services.factors import FactorResolver
from ..services.season_window import in_window, season_window
from ..schemas import (
    Auszeichnung,
    CategoryShare,
    ComparisonOut,
    ComparisonUser,
    CumulativePoint,
    LastSeenEntry,
    LastSeenOut,
    MonthElevation,
    Segment,
)

router = APIRouter(prefix="/api/comparison", tags=["comparison"])


def _monatsschluessel(tag: date_type) -> str:
    return f"{tag.year:04d}-{tag.month:02d}"


def _monatsachse(erster: date_type, letzter: date_type) -> list[str]:
    """Lückenlose Monatsliste von `erster` bis `letzter`, jeweils als 'YYYY-MM'."""
    monate: list[str] = []
    jahr, monat = erster.year, erster.month
    while (jahr, monat) <= (letzter.year, letzter.month):
        monate.append(f"{jahr:04d}-{monat:02d}")
        monat += 1
        if monat == 13:
            jahr, monat = jahr + 1, 1
    return monate


# Hinweis: "challenge" meint hier die SAISON (Jahreswertung), nicht das
# Challenges-Feature aus Spec 2026-08-04. Bezeichner bleiben aus
# Kompatibilitaetsgruenden unveraendert, nur die Anzeigetexte heissen "Saison".
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
    window = season_window(season)
    rows = [(a, c) for a, c in rows if in_window(a.date, window)]

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

    emoji_rows = session.exec(
        select(AchievementUnlock).where(AchievementUnlock.showcased == True)  # noqa: E712
    ).all()
    emojis_by_user: dict[int, list[str]] = defaultdict(list)
    auszeichnungen_by_user: dict[int, list[Auszeichnung]] = defaultdict(list)
    for ul in emoji_rows:
        info = SHOWCASE_INFO.get(ul.key)
        if info is None:
            continue
        emoji, titel, desc = info
        emojis_by_user[ul.user_id].append(emoji)
        auszeichnungen_by_user[ul.user_id].append(
            Auszeichnung(emoji=emoji, title=titel, description=desc)
        )

    # Gemeinsame Monatsachse für die Höhenmeter-Ansicht: ab Challenge-Start (bzw. ab
    # der ersten Aktivität) bis zum laufenden Monat. Alle Personen teilen sie sich,
    # damit ein Monat überall dieselbe Farbe bekommt.
    alle_daten = [a.date for a, _ in rows]
    if phase == "challenge" and start is not None and date_type.today() >= start:
        erster_tag = start
    elif alle_daten:
        erster_tag = min(alle_daten)
    else:
        erster_tag = None
    if erster_tag is None:
        elevation_months: list[str] = []
    else:
        letzter_tag = max(alle_daten) if alle_daten else erster_tag
        heute = date_type.today()
        if phase == "challenge" and in_window(heute, window) and heute > letzter_tag:
            letzter_tag = heute
        elevation_months = _monatsachse(erster_tag, max(letzter_tag, erster_tag))

    resolver = FactorResolver.load(session)
    result_users = []
    for user in users:
        acts = by_user.get(user.id, [])
        segments, cumulative = [], []
        shares, real_shares = defaultdict(float), defaultdict(float)
        hm_pro_monat: dict[str, float] = defaultdict(float)
        running = 0.0
        real_running = 0.0
        hm_running = 0.0
        factor = user.km_factor if phase == "challenge" else 1.0
        for a, c in acts:
            scaled = round(a.distance_km * resolver.factor(c.id, a.date) * factor, 2)
            running = round(running + scaled, 2)
            real_running = round(real_running + a.distance_km, 2)
            # Höhenmeter bleiben roh: weder Kategorie- noch Personen-Faktor.
            hm_running = round(hm_running + (a.elevation_m or 0.0), 1)
            hm_pro_monat[_monatsschluessel(a.date)] += a.elevation_m or 0.0
            segments.append(
                Segment(date=a.date, category_id=c.id, color=c.color, scaled_km=scaled)
            )
            cumulative.append(
                CumulativePoint(
                    date=a.date,
                    scaled_km=running,
                    real_km=real_running,
                    elevation_m=hm_running,
                )
            )
            shares[c.id] += scaled
            real_shares[c.id] += a.distance_km
        by_category = [
            CategoryShare(
                category_id=c.id,
                name=c.name,
                color=c.color,
                icon=c.icon,
                scaled_km=round(km, 2),
                real_km=round(real_shares[c.id], 2),
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
                emojis=emojis_by_user.get(user.id, []),
                auszeichnungen=auszeichnungen_by_user.get(user.id, []),
                rank=0,
                total_scaled_km=running,
                total_real_km=real_running,
                total_elevation_m=hm_running,
                by_category=by_category,
                segments=segments,
                cumulative=cumulative,
                elevation_by_month=[
                    MonthElevation(month=m, meters=round(hm_pro_monat[m], 1))
                    for m in sorted(hm_pro_monat)
                    if hm_pro_monat[m] > 0
                ],
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
        elevation_months=elevation_months,
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
