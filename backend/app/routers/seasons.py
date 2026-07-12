import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..deps import get_current_user, get_session, require_admin
from ..models import Season
from ..schemas import SeasonCreate, SeasonOut, SeasonPatch

router = APIRouter(prefix="/api/seasons", tags=["seasons"])


@router.get(
    "", response_model=list[SeasonOut], dependencies=[Depends(get_current_user)]
)
def list_seasons(session: Session = Depends(get_session)):
    seasons = session.exec(select(Season).order_by(Season.year)).all()
    return [SeasonOut.from_season(s) for s in seasons]


@router.post(
    "", response_model=SeasonOut, status_code=201, dependencies=[Depends(require_admin)]
)
def create_season(data: SeasonCreate, session: Session = Depends(get_session)):
    if session.exec(select(Season).where(Season.year == data.year)).first():
        raise HTTPException(status_code=409, detail="Jahr existiert bereits")
    season = Season(
        year=data.year,
        goal_km=data.goal_km,
        milestones_json=json.dumps([m.model_dump() for m in data.milestones]),
        start_date=data.start_date,
    )
    session.add(season)
    session.commit()
    session.refresh(season)
    return SeasonOut.from_season(season)


@router.patch(
    "/{season_id}", response_model=SeasonOut, dependencies=[Depends(require_admin)]
)
def patch_season(
    season_id: int, data: SeasonPatch, session: Session = Depends(get_session)
):
    season = session.get(Season, season_id)
    if season is None:
        raise HTTPException(status_code=404)
    if data.goal_km is not None:
        season.goal_km = data.goal_km
    if data.milestones is not None:
        season.milestones_json = json.dumps([m.model_dump() for m in data.milestones])
    if "start_date" in data.model_fields_set:
        season.start_date = data.start_date
    session.add(season)
    session.commit()
    session.refresh(season)
    return SeasonOut.from_season(season)
