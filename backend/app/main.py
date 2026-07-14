import os
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import config
from .db import engine, init_db
from .routers import (
    achievements,
    activities,
    addons,
    auth_router,
    bets_router,
    categories,
    comparison,
    invites,
    seasons,
    strava_router,
    users,
)
from .seed import seed_all


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not config.SKIP_SEED:
        init_db()
        with Session(engine) as session:
            seed_all(
                session,
                admin_user=config.ADMIN_USER,
                admin_password=config.ADMIN_PASSWORD,
                year=date.today().year,
            )
    yield


app = FastAPI(title="MeterMachen", lifespan=lifespan)
app.include_router(achievements.router)
app.include_router(auth_router.router)
app.include_router(activities.router)
app.include_router(addons.router)
app.include_router(bets_router.router)
app.include_router(bets_router.points_router)
app.include_router(categories.router)
app.include_router(comparison.router)
app.include_router(invites.router)
app.include_router(seasons.router)
app.include_router(strava_router.router)
app.include_router(users.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


class SPAStaticFiles(StaticFiles):
    """Liefert index.html für alle unbekannten Pfade (Client-Side-Routing)."""

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and not path.startswith("api/"):
                return await super().get_response("index.html", scope)
            raise


def mount_static(app: FastAPI) -> None:
    dist = Path(os.environ.get("FRONTEND_DIST", "../frontend/dist"))
    if dist.is_dir():
        app.mount("/", SPAStaticFiles(directory=dist, html=True), name="spa")


mount_static(app)
