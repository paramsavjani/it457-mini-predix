"""Sensor reading ingestion and queries (like the Predix Time-Series service)."""
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from . import db, rules
from .alerts import store_alerts

router = APIRouter(prefix="/api/readings", tags=["readings"])


class Reading(BaseModel):
    asset_id: str = Field(min_length=1, max_length=32)
    ts: datetime | None = None
    # Physical limits: anything outside these is a broken sensor, not a fault
    temperature: float = Field(ge=-50, le=300)   # degrees C
    vibration: float = Field(ge=0, le=100)       # mm/s RMS
    rpm: float = Field(ge=0, le=20000)
    pressure: float = Field(ge=0, le=200)        # bar


class ReadingBatch(BaseModel):
    readings: list[Reading] = Field(min_length=1, max_length=500)


def store_readings(readings: list[Reading]) -> None:
    known = {row["id"] for row in db.fetch_all("SELECT id FROM assets")}
    unknown = {r.asset_id for r in readings} - known
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown assets: {sorted(unknown)}")
    with db.pool.connection() as conn:
        conn.cursor().executemany(
            """INSERT INTO readings (asset_id, ts, temperature, vibration, rpm, pressure)
               VALUES (%s, COALESCE(%s, now()), %s, %s, %s, %s)""",
            [(r.asset_id, r.ts, r.temperature, r.vibration, r.rpm, r.pressure) for r in readings],
        )
        alerts = []
        for r in readings:
            alerts += rules.evaluate(r.asset_id, r.model_dump(exclude={"asset_id", "ts"}))
        store_alerts(conn, alerts)


@router.post("", status_code=201)
def ingest(batch: ReadingBatch):
    store_readings(batch.readings)
    return {"stored": len(batch.readings)}


@router.get("")
def query_readings(
    asset_id: str,
    limit: int = Query(default=60, ge=1, le=1000),
):
    rows = db.fetch_all(
        """SELECT ts, temperature, vibration, rpm, pressure FROM readings
           WHERE asset_id = %s ORDER BY ts DESC LIMIT %s""",
        (asset_id, limit),
    )
    return list(reversed(rows))


@router.get("/latest")
def latest_per_asset():
    return db.fetch_all(
        """SELECT DISTINCT ON (asset_id) asset_id, ts, temperature, vibration, rpm, pressure
           FROM readings ORDER BY asset_id, ts DESC"""
    )
