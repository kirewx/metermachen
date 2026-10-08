import logging

from sqlmodel import Session, select

from ..models import Activity, ActivityTrack, StravaIgnored
from . import feed, together


def delete_activity(session: Session, act: Activity, *, ignore_strava: bool) -> None:
    """Gemeinsamer Lösch-Helfer: entfernt Feed-Events, Track und die
    Aktivität selbst. Bei ignore_strava=True wird eine importierte
    Strava-Aktivität zusätzlich auf die Ignore-Liste gesetzt, damit sie beim
    nächsten Webhook-Event nicht erneut importiert wird. Eine
    Together-Teilnahme der Aktivität wird ebenfalls entfernt.
    """
    try:
        together.remove_activity(session, act.id)
    except Exception:
        # Löschen darf nie an Together scheitern.
        logging.getLogger(__name__).exception(
            "together: remove_activity fehlgeschlagen fuer activity_id=%s", act.id
        )
        session.rollback()
    feed.remove_activity_events(session, act.id)
    track = session.exec(
        select(ActivityTrack).where(ActivityTrack.activity_id == act.id)
    ).first()
    if track is not None:
        session.delete(track)
    if ignore_strava and act.source == "strava" and act.external_id:
        exists = session.exec(
            select(StravaIgnored).where(
                StravaIgnored.user_id == act.user_id,
                StravaIgnored.external_id == act.external_id,
            )
        ).first()
        if exists is None:
            session.add(
                StravaIgnored(user_id=act.user_id, external_id=act.external_id)
            )
    session.delete(act)
    session.commit()
