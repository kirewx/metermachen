from fastapi import FastAPI

app = FastAPI(title="MeterMachen")


@app.get("/api/health")
def health():
    return {"status": "ok"}
