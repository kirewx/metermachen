import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..deps import get_current_user, get_session
from ..models import FeedEvent, FeedReaction, FeedSeen, User, utcnow
from ..schemas import FeedEventOut, FeedPage, FeedReactionIn, FeedReactionOut
from ..services.feed import REACTION_EMOJIS, ensure_recaps

router = APIRouter(prefix="/api/feed", tags=["feed"])

PAGE_SIZE = 30


def _reactions_for(
    session: Session, event_ids: list[int], me: User
) -> dict[int, list[FeedReactionOut]]:
    users = {u.id: u for u in session.exec(select(User)).all()}
    rows = session.exec(
        select(FeedReaction).where(FeedReaction.event_id.in_(event_ids))  # type: ignore[attr-defined]
    ).all() if event_ids else []
    out: dict[int, list[FeedReactionOut]] = {}
    for eid in event_ids:
        mine = [r for r in rows if r.event_id == eid]
        per_emoji: dict[str, list[FeedReaction]] = {}
        for r in mine:
            per_emoji.setdefault(r.emoji, []).append(r)
        out[eid] = [
            FeedReactionOut(
                emoji=emoji,
                count=len(rs),
                mine=any(r.user_id == me.id for r in rs),
                users=[
                    users[r.user_id].display_name
                    for r in rs if r.user_id in users
                ],
            )
            for emoji, rs in sorted(per_emoji.items())
        ]
    return out


def _to_out(session, events, me) -> list[FeedEventOut]:
    users = {u.id: u for u in session.exec(select(User)).all()}
    reactions = _reactions_for(session, [e.id for e in events], me)
    out = []
    for e in events:
        u = users.get(e.user_id)
        out.append(FeedEventOut(
            id=e.id, type=e.type, user_id=e.user_id,
            display_name=u.display_name if u else None,
            avatar=u.avatar if u else None,
            created_at=e.created_at,
            payload=json.loads(e.payload_json),
            reactions=reactions.get(e.id, []),
        ))
    return out


@router.get("", response_model=FeedPage)
def feed_page(
    year: int,
    before: int | None = None,
    session: Session = Depends(get_session),
    me: User = Depends(get_current_user),
):
    ensure_recaps(session)
    stmt = select(FeedEvent).where(FeedEvent.season_year == year)
    if before is not None:
        stmt = stmt.where(FeedEvent.id < before)
    events = session.exec(
        stmt.order_by(FeedEvent.id.desc()).limit(PAGE_SIZE)  # type: ignore[attr-defined]
    ).all()
    next_before = events[-1].id if len(events) == PAGE_SIZE else None
    return FeedPage(events=_to_out(session, events, me), next_before=next_before)


@router.get("/unseen")
def feed_unseen(
    session: Session = Depends(get_session),
    me: User = Depends(get_current_user),
):
    seen = session.exec(
        select(FeedSeen).where(FeedSeen.user_id == me.id)
    ).first()
    stmt = select(FeedEvent)
    newest = session.exec(
        stmt.order_by(FeedEvent.created_at.desc()).limit(1)  # type: ignore[attr-defined]
    ).first()
    has_new = newest is not None and (seen is None or newest.created_at > seen.seen_at)
    return {"has_new": has_new}


@router.post("/seen", status_code=204)
def mark_feed_seen(
    session: Session = Depends(get_session),
    me: User = Depends(get_current_user),
):
    seen = session.exec(
        select(FeedSeen).where(FeedSeen.user_id == me.id)
    ).first()
    if seen is None:
        seen = FeedSeen(user_id=me.id)
    seen.seen_at = utcnow()
    session.add(seen)
    session.commit()


@router.post("/{event_id}/reactions", response_model=list[FeedReactionOut])
def toggle_reaction(
    event_id: int,
    data: FeedReactionIn,
    session: Session = Depends(get_session),
    me: User = Depends(get_current_user),
):
    if data.emoji not in REACTION_EMOJIS:
        raise HTTPException(status_code=422, detail="Unbekanntes Reaktions-Emoji")
    if session.get(FeedEvent, event_id) is None:
        raise HTTPException(status_code=404)
    existing = session.exec(
        select(FeedReaction).where(
            FeedReaction.event_id == event_id,
            FeedReaction.user_id == me.id,
            FeedReaction.emoji == data.emoji,
        )
    ).first()
    if existing is not None:
        session.delete(existing)
    else:
        session.add(FeedReaction(event_id=event_id, user_id=me.id, emoji=data.emoji))
    session.commit()
    return _reactions_for(session, [event_id], me)[event_id]
