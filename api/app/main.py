"""Mini-Predix ingestion API.

Plays the role of Predix Cloud: receives sensor readings from the edge
(our simulator), stores them, and serves them to the dashboard.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import config, db


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.open_pool()
    db.init_schema()
    yield
    db.pool.close()


app = FastAPI(title="Mini-Predix API", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health():
    db.fetch_one("SELECT 1 AS ok")
    return {"status": "ok", "deployment": config.DEPLOYMENT_NAME}
