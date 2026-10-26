"""Server metrics used while benchmarking each deployment.

/proc inside a container still reports host-wide numbers for load average,
memory and CPU, which is what we want when comparing servers.
"""
import os
import platform
import time

from fastapi import APIRouter, Request

from . import config, db

router = APIRouter(prefix="/api/system", tags=["system"])

STARTED = time.time()
_last_cpu: tuple[float, float] | None = None
_requests = {"count": 0, "total_ms": 0.0}


def record_request(duration_ms: float) -> None:
    _requests["count"] += 1
    _requests["total_ms"] += duration_ms


def _read_cpu() -> tuple[float, float] | None:
    try:
        with open("/proc/stat") as f:
            fields = [float(x) for x in f.readline().split()[1:]]
    except OSError:
        return None
    idle = fields[3] + fields[4]  # idle + iowait
    return idle, sum(fields)


def cpu_percent() -> float | None:
    """CPU busy % since the previous call to this endpoint."""
    global _last_cpu
    now = _read_cpu()
    if now is None:
        return None
    prev, _last_cpu = _last_cpu, now
    if prev is None or now[1] == prev[1]:
        return None
    busy = 1 - (now[0] - prev[0]) / (now[1] - prev[1])
    return round(100 * busy, 1)


def memory() -> dict | None:
    try:
        with open("/proc/meminfo") as f:
            info = {line.split(":")[0]: int(line.split()[1]) for line in f}
    except OSError:
        return None
    total, available = info["MemTotal"], info["MemAvailable"]
    return {
        "total_mb": total // 1024,
        "used_mb": (total - available) // 1024,
        "used_percent": round(100 * (total - available) / total, 1),
    }


@router.get("")
def system_metrics(request: Request):
    load = os.getloadavg() if hasattr(os, "getloadavg") else (None, None, None)
    counts = db.fetch_one(
        """SELECT (SELECT count(*) FROM readings) AS readings,
                  (SELECT count(*) FROM alerts)   AS alerts"""
    )
    handled = _requests["count"]
    return {
        "deployment": config.DEPLOYMENT_NAME,
        "host": platform.node(),
        "cpu_count": os.cpu_count(),
        "uptime_seconds": round(time.time() - STARTED),
        "load_average": {"1m": load[0], "5m": load[1], "15m": load[2]},
        "cpu_percent": cpu_percent(),
        "memory": memory(),
        "worker_pid": os.getpid(),
        "worker_requests": handled,
        "worker_avg_ms": round(_requests["total_ms"] / handled, 2) if handled else None,
        "db_pool": db.pool.get_stats(),
        **counts,
    }
