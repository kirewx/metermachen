from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI
from sqlmodel import Session

from . import config
from .db import engine, init_db
from .routers import activities, auth_router, categories, comparison, seasons, users
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
app.include_router(auth_router.router)
app.include_router(activities.router)
app.include_router(categories.router)
app.include_router(comparison.router)
app.include_router(seasons.router)
app.include_router(users.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
