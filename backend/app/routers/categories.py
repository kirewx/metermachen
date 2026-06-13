import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..deps import get_current_user, get_session, require_admin
from ..models import Category
from ..schemas import CategoryCreate, CategoryOut, CategoryPatch

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get(
    "", response_model=list[CategoryOut], dependencies=[Depends(get_current_user)]
)
def list_categories(session: Session = Depends(get_session)):
    cats = session.exec(select(Category).order_by(Category.id)).all()
    return [CategoryOut.from_category(c) for c in cats]


@router.post(
    "", response_model=CategoryOut, status_code=201, dependencies=[Depends(require_admin)]
)
def create_category(data: CategoryCreate, session: Session = Depends(get_session)):
    values = data.model_dump()
    values["strava_sport_types"] = json.dumps(values.get("strava_sport_types") or [])
    cat = Category(**values)
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return CategoryOut.from_category(cat)


@router.patch(
    "/{category_id}", response_model=CategoryOut, dependencies=[Depends(require_admin)]
)
def patch_category(
    category_id: int, data: CategoryPatch, session: Session = Depends(get_session)
):
    cat = session.get(Category, category_id)
    if cat is None:
        raise HTTPException(status_code=404)
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if "strava_sport_types" in changes:
        changes["strava_sport_types"] = json.dumps(changes["strava_sport_types"])
    for key, value in changes.items():
        setattr(cat, key, value)
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return CategoryOut.from_category(cat)
