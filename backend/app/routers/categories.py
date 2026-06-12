from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..deps import get_current_user, get_session, require_admin
from ..models import Category
from ..schemas import CategoryCreate, CategoryPatch

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[Category], dependencies=[Depends(get_current_user)])
def list_categories(session: Session = Depends(get_session)):
    return session.exec(select(Category).order_by(Category.id)).all()


@router.post("", response_model=Category, status_code=201, dependencies=[Depends(require_admin)])
def create_category(data: CategoryCreate, session: Session = Depends(get_session)):
    cat = Category(**data.model_dump())
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat


@router.patch("/{category_id}", response_model=Category, dependencies=[Depends(require_admin)])
def patch_category(
    category_id: int, data: CategoryPatch, session: Session = Depends(get_session)
):
    cat = session.get(Category, category_id)
    if cat is None:
        raise HTTPException(status_code=404)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(cat, key, value)
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat
