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
def list_alerts(limit: int = Query(default=20, ge=1, le=200)):
    return db.fetch_all("SELECT * FROM alerts ORDER BY ts DESC LIMIT %s", (limit,))
