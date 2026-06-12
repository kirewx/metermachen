from fastapi import FastAPI

from .routers import auth_router

app = FastAPI(title="MeterMachen")
app.include_router(auth_router.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
