from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlmodel import Session, select

from .. import config
from ..db import engine
from ..deps import get_current_user, get_session
from ..models import StravaConnection, User
from ..services import strava

router = APIRouter(prefix="/api/strava", tags=["strava"])
_state_serializer = URLSafeTimedSerializer(config.SECRET_KEY, salt="strava-oauth")


def _require_enabled() -> None:
    if not config.strava_enabled():
        raise HTTPException(status_code=404, detail="Strava ist nicht konfiguriert")


@router.get("/status")
def status(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if not config.strava_enabled():
        return {"enabled": False, "connected": False}
    conn = session.exec(
        select(StravaConnection).where(StravaConnection.user_id == user.id)
    ).first()
    return {
        "enabled": True,
        "connected": conn is not None,
        "athlete_id": conn.athlete_id if conn else None,
    }


@router.get("/connect")
def connect(user: User = Depends(get_current_user)):
    _require_enabled()
    state = _state_serializer.dumps(user.id)
    return RedirectResponse(strava.authorize_url(state))


@router.get("/callback")
def callback(
    code: str | None = None,
    state: str | None = None,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_enabled()
    if not code or not state:
        raise HTTPException(status_code=400, detail="Fehlende OAuth-Parameter")
    try:
        state_user_id = _state_serializer.loads(state, max_age=600)
    except BadSignature:
        raise HTTPException(status_code=400, detail="Ungültiger State")
    if state_user_id != user.id:
        raise HTTPException(status_code=400, detail="State passt nicht zum angemeldeten User")
    data = strava.exchange_code(code)
    conn = session.exec(
        select(StravaConnection).where(StravaConnection.user_id == user.id)
    ).first()
    if conn is None:
        conn = StravaConnection(
            user_id=user.id, athlete_id=0, access_token="", refresh_token="", expires_at=0
        )
    conn.athlete_id = data["athlete"]["id"]
    strava.apply_tokens(conn, data)
    session.add(conn)
    session.commit()
    return RedirectResponse("/?strava=connected")


@router.delete("/disconnect", status_code=204)
def disconnect(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    _require_enabled()
    conn = session.exec(
        select(StravaConnection).where(StravaConnection.user_id == user.id)
    ).first()
    if conn is not None:
        session.delete(conn)
        session.commit()


@router.get("/webhook")
def webhook_verify(request: Request):
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == config.STRAVA_WEBHOOK_VERIFY_TOKEN
    ):
        return JSONResponse({"hub.challenge": params.get("hub.challenge")})
    raise HTTPException(status_code=403, detail="Verify-Token falsch")


def process_event(payload: dict) -> None:
    with Session(engine) as session:
        strava.handle_webhook_event(session, payload)


@router.post("/webhook")
async def webhook_event(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    background_tasks.add_task(process_event, payload)
    return {"ok": True}
