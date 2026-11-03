import json
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..deps import get_session, require_admin
from ..models import Category, CategoryElevationChange, CategoryFactorChange
from ..services.factors import default_counts_elevation, set_counts_elevation
from ..schemas import (
    CategoryCreate,
    CategoryOut,
    CategoryPatch,
    FactorChangeCreate,
    FactorChangeOut,
)

router = APIRouter(prefix="/api/categories", tags=["categories"])


# Öffentlich (kein Login): Die Regeln-Seite zeigt die Faktor-Tabelle auch
# ohne Anmeldung an.
@router.get("", response_model=list[CategoryOut])
def list_categories(session: Session = Depends(get_session)):
    cats = session.exec(select(Category).order_by(Category.id)).all()
    by_cat: dict[int, list[CategoryFactorChange]] = defaultdict(list)
    for ch in session.exec(select(CategoryFactorChange)).all():
        by_cat[ch.category_id].append(ch)
    hm_by_cat: dict[int, list[CategoryElevationChange]] = defaultdict(list)
    for ec in session.exec(select(CategoryElevationChange)).all():
        hm_by_cat[ec.category_id].append(ec)
    return [
        CategoryOut.from_category(c, by_cat.get(c.id), hm_by_cat.get(c.id)) for c in cats
    ]


def _out(session: Session, cat: Category) -> CategoryOut:
    return CategoryOut.from_category(
        cat,
        list(session.exec(
            select(CategoryFactorChange).where(CategoryFactorChange.category_id == cat.id)
        ).all()),
        list(session.exec(
            select(CategoryElevationChange).where(
                CategoryElevationChange.category_id == cat.id
            )
        ).all()),
    )


@router.post(
    "", response_model=CategoryOut, status_code=201, dependencies=[Depends(require_admin)]
)
def create_category(data: CategoryCreate, session: Session = Depends(get_session)):
    values = data.model_dump(exclude={"counts_elevation"})
    values["strava_sport_types"] = json.dumps(values.get("strava_sport_types") or [])
    cat = Category(**values)  # zählt bis zum Stichtag keine Höhenmeter
    session.add(cat)
    session.flush()
    hm = data.counts_elevation
    if hm is None:
        hm = default_counts_elevation(data.name, data.icon, data.strava_sport_types)
    set_counts_elevation(session, cat, hm)
    session.commit()
    session.refresh(cat)
    return _out(session, cat)


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
    hm = changes.pop("counts_elevation", None)
    if hm is not None:  # datierte Änderung ab heute, nie rückwirkend
        set_counts_elevation(session, cat, hm)
    for key, value in changes.items():
        setattr(cat, key, value)
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return _out(session, cat)


@router.post(
    "/{category_id}/factor-changes",
    response_model=FactorChangeOut,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def create_factor_change(
    category_id: int, data: FactorChangeCreate, session: Session = Depends(get_session)
):
    cat = session.get(Category, category_id)
    if cat is None:
        raise HTTPException(status_code=404)
    if data.valid_from < date.today():
        raise HTTPException(
            status_code=400, detail="Faktor-Änderungen gelten nicht rückwirkend"
        )
    doppelt = session.exec(
        select(CategoryFactorChange).where(
            CategoryFactorChange.category_id == category_id,
            CategoryFactorChange.valid_from == data.valid_from,
        )
    ).first()
    if doppelt is not None:
        raise HTTPException(
            status_code=409,
            detail="Für diesen Tag existiert schon eine Änderung — erst löschen",
        )
    ch = CategoryFactorChange(
        category_id=category_id, factor=data.factor, valid_from=data.valid_from
    )
    session.add(ch)
    session.commit()
    session.refresh(ch)
    return FactorChangeOut(id=ch.id, factor=ch.factor, valid_from=ch.valid_from)


@router.delete(
    "/{category_id}/factor-changes/{change_id}",
    status_code=204,
    dependencies=[Depends(require_admin)],
)
def delete_factor_change(
    category_id: int, change_id: int, session: Session = Depends(get_session)
):
    ch = session.get(CategoryFactorChange, change_id)
    if ch is None or ch.category_id != category_id:
        raise HTTPException(status_code=404)
    if ch.valid_from < date.today():
        raise HTTPException(
            status_code=409, detail="Wirksam gewordene Änderungen sind Historie"
        )
    session.delete(ch)
    session.commit()
