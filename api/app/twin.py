"""A very small "digital twin" for each asset.

GE's digital twins combine live data with physics/ML models to estimate an
asset's present health and predict future failures. Ours does the same idea
with simple statistics over the most recent readings:

* health score (0-100) from how close each metric runs to its limits
* temperature trend (degrees per minute) using a least-squares slope
* a rough "time to critical" prediction if the trend continues
"""
from fastapi import APIRouter, HTTPException

from . import db
from .rules import THRESHOLDS

router = APIRouter(prefix="/api/twin", tags=["digital-twin"])

WINDOW = 30  # number of recent readings the twin looks at


def slope_per_minute(points: list[tuple[float, float]]) -> float:
    """Least-squares slope of (seconds, value) points, returned per minute."""
    n = len(points)
    if n < 2:
        return 0.0
    mean_t = sum(t for t, _ in points) / n
    mean_v = sum(v for _, v in points) / n
    var_t = sum((t - mean_t) ** 2 for t, _ in points)
    if var_t == 0:
        return 0.0
    cov = sum((t - mean_t) * (v - mean_v) for t, v in points)
    return cov / var_t * 60


def compute_health(rows: list[dict]) -> dict:
    """rows: recent readings, oldest first, each with ts + metric values."""
    if not rows:
        return {"health": None, "status": "no-data", "temp_trend": 0.0, "minutes_to_critical": None}

    penalty = 0.0
    for metric, (warn, crit, _) in THRESHOLDS.items():
        values = [r[metric] for r in rows]
        avg = sum(values) / len(values)
        # 0 penalty well below the warning limit, rising steeply past it
        ratio = avg / warn
        if ratio > 0.8:
            penalty += min(40.0, (ratio - 0.8) * 100)
        # extra penalty for each reading past the critical limit
        penalty += 30.0 * sum(v >= crit for v in values) / len(values)

    t0 = rows[0]["ts"]
    temps = [((r["ts"] - t0).total_seconds(), r["temperature"]) for r in rows]
    trend = slope_per_minute(temps)

    crit_temp = THRESHOLDS["temperature"][1]
    current = rows[-1]["temperature"]
    minutes_to_critical = None
    if trend > 0.05 and current < crit_temp:
        minutes_to_critical = round((crit_temp - current) / trend, 1)
        if minutes_to_critical < 30:
            penalty += 15.0

    health = max(0.0, round(100.0 - penalty, 1))
    status = "healthy" if health >= 80 else "degraded" if health >= 50 else "critical"
    return {
        "health": health,
        "status": status,
        "temp_trend": round(trend, 3),
        "minutes_to_critical": minutes_to_critical,
    }


def recent_rows(asset_id: str) -> list[dict]:
    rows = db.fetch_all(
        """SELECT ts, temperature, vibration, rpm, pressure FROM readings
           WHERE asset_id = %s ORDER BY ts DESC LIMIT %s""",
        (asset_id, WINDOW),
    )
    return list(reversed(rows))


@router.get("")
def fleet_health():
    assets = db.fetch_all("SELECT id, name, asset_type FROM assets ORDER BY id")
    return [{**a, **compute_health(recent_rows(a["id"]))} for a in assets]


@router.get("/{asset_id}")
def asset_health(asset_id: str):
    asset = db.fetch_one("SELECT id, name, asset_type FROM assets WHERE id = %s", (asset_id,))
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return {**asset, **compute_health(recent_rows(asset_id))}
