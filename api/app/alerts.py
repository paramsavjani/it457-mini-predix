"""Alert storage and listing."""
from fastapi import APIRouter, Query

from . import db
from .rules import Alert

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def store_alerts(conn, alerts: list[Alert]) -> None:
    if not alerts:
        return
    conn.cursor().executemany(
        """INSERT INTO alerts (asset_id, metric, value, severity, message)
           VALUES (%s, %s, %s, %s, %s)""",
        [(a.asset_id, a.metric, a.value, a.severity, a.message) for a in alerts],
    )


@router.get("")
def list_alerts(
    limit: int = Query(default=20, ge=1, le=200),
    asset_id: str | None = None,
    severity: str | None = Query(default=None, pattern="^(warning|critical)$"),
):
    return db.fetch_all(
        """SELECT * FROM alerts
           WHERE (%(asset)s::text IS NULL OR asset_id = %(asset)s)
             AND (%(sev)s::text IS NULL OR severity = %(sev)s)
           ORDER BY ts DESC LIMIT %(limit)s""",
        {"asset": asset_id, "sev": severity, "limit": limit},
    )


@router.get("/summary")
def alert_summary():
    """Alert counts per asset and severity, for a quick fleet overview."""
    rows = db.fetch_all(
        """SELECT asset_id, severity, count(*) AS total, max(ts) AS last_seen
           FROM alerts GROUP BY asset_id, severity ORDER BY asset_id, severity"""
    )
    return {
        "total": sum(r["total"] for r in rows),
        "by_asset": rows,
    }
