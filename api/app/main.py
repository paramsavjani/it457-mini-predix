"""Mini-Predix ingestion API.

Plays the role of Predix Cloud: receives sensor readings from the edge
(our simulator), stores them, and serves them to the dashboard.
"""
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import alerts, assets, config, db, readings, system, twin


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.open_pool()
    db.init_schema()
    assets.seed_assets()
    yield
    db.pool.close()


app = FastAPI(title="Mini-Predix API", version="1.0.0", lifespan=lifespan)
app.include_router(assets.router)
app.include_router(readings.router)
app.include_router(alerts.router)
app.include_router(twin.router)
app.include_router(system.router)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(STATIC_DIR / "index.html")


@app.middleware("http")
async def time_requests(request: Request, call_next):
    """Measure server-side processing time, separate from network latency."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    system.record_request(elapsed_ms)
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
    return response


@app.get("/health")
def health():
    db.fetch_one("SELECT 1 AS ok")
    return {"status": "ok", "deployment": config.DEPLOYMENT_NAME}
