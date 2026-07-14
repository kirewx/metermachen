from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..deps import get_current_user, get_session, require_admin
from ..models import AddOn
from ..schemas import AddOnCreate, AddOnOut, AddOnPatch

router = APIRouter(prefix="/api/addons", tags=["addons"])


@router.get("", response_model=list[AddOnOut], dependencies=[Depends(get_current_user)])
def list_addons(session: Session = Depends(get_session)):
    addons = session.exec(select(AddOn).order_by(AddOn.key)).all()
    return [AddOnOut.from_addon(a) for a in addons]


@router.post(
    "", response_model=AddOnOut, status_code=201, dependencies=[Depends(require_admin)]
)
def create_addon(data: AddOnCreate, session: Session = Depends(get_session)):
    if session.exec(select(AddOn).where(AddOn.key == data.key)).first():
        raise HTTPException(status_code=409, detail="Add-on-Key existiert bereits")
    addon = AddOn(
        key=data.key,
        label=data.label,
        description=data.description,
        enabled=data.enabled,
        active_from=data.active_from,
        active_until=data.active_until,
    )
    session.add(addon)
    session.commit()
    session.refresh(addon)
    return AddOnOut.from_addon(addon)


@router.patch(
    "/{addon_id}", response_model=AddOnOut, dependencies=[Depends(require_admin)]
)
def patch_addon(
    addon_id: int, data: AddOnPatch, session: Session = Depends(get_session)
):
    addon = session.get(AddOn, addon_id)
    if addon is None:
        raise HTTPException(status_code=404, detail="Add-on nicht gefunden")
    if data.label is not None:
        addon.label = data.label
    if data.description is not None:
        addon.description = data.description
    if data.enabled is not None:
        addon.enabled = data.enabled
    if "active_from" in data.model_fields_set:
        addon.active_from = data.active_from
    if "active_until" in data.model_fields_set:
        addon.active_until = data.active_until
    session.add(addon)
    session.commit()
    session.refresh(addon)
    return AddOnOut.from_addon(addon)


@router.delete("/{addon_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_addon(addon_id: int, session: Session = Depends(get_session)):
    addon = session.get(AddOn, addon_id)
    if addon is not None:
        session.delete(addon)
        session.commit()
