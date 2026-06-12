import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlmodel import Session, select

from .. import config
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
    session.add(season)
    session.commit()
    session.refresh(season)
    return SeasonOut.from_season(season)


ALLOWED_IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


@router.post(
    "/{season_id}/map-image",
    response_model=SeasonOut,
    dependencies=[Depends(require_admin)],
)
def upload_map_image(
    season_id: int, file: UploadFile, session: Session = Depends(get_session)
):
    season = session.get(Season, season_id)
    if season is None:
        raise HTTPException(status_code=404)
    ext = ALLOWED_IMAGE_TYPES.get(file.content_type)
    if ext is None:
        raise HTTPException(status_code=422, detail="Nur PNG/JPEG/WebP erlaubt")
    maps_dir = config.DATA_DIR / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)
    target = maps_dir / f"{season.year}{ext}"
    target.write_bytes(file.file.read())
    season.map_image = f"/media/maps/{target.name}"
    session.add(season)
    session.commit()
    session.refresh(season)
    return SeasonOut.from_season(season)
