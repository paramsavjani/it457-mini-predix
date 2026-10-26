"""Load test a Mini-Predix deployment and record latency, throughput and server load.

For each concurrency level, N virtual users hit the API in a loop for a
fixed duration. The traffic mix imitates real use:
  * 30% ingest: POST a batch of readings (like edge gateways)
  * 70% reads:  fleet health, latest readings and alerts (like dashboards)

While the test runs we sample /api/system every 2 seconds to capture the
server's CPU, load average and memory.

Example:
  python benchmark.py --url http://1.2.3.4:8090 --label vps-4gb
"""
import argparse
import asyncio
import json
import random
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ASSETS = ["GT-01", "GT-02", "GT-03", "WT-01", "WT-02", "JE-01", "JE-02", "LC-01"]
READ_PATHS = ["/api/twin", "/api/readings/latest", "/api/alerts?limit=12"]


def reading_batch() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {"readings": [{
        "asset_id": a, "ts": now,
        "temperature": round(random.gauss(72, 2), 2),
        "vibration": round(random.gauss(3.5, 0.3), 2),
        "rpm": round(random.gauss(3000, 20), 1),
        "pressure": round(random.gauss(21, 0.4), 2),
    } for a in random.sample(ASSETS, 6)]}


def percentile(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    values = sorted(values)
    k = (len(values) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


async def user(client: httpx.AsyncClient, stop_at: float, samples: list) -> None:
    while time.perf_counter() < stop_at:
        is_write = random.random() < 0.3
        start = time.perf_counter()
        try:
            if is_write:
                resp = await client.post("/api/readings", json=reading_batch())
            else:
                resp = await client.get(random.choice(READ_PATHS))
            ok = resp.status_code < 400
            server_ms = float(resp.headers.get("x-process-time-ms", "nan"))
        except httpx.HTTPError:
            ok, server_ms = False, float("nan")
        samples.append({
            "kind": "write" if is_write else "read",
            "ms": (time.perf_counter() - start) * 1000,
            "server_ms": server_ms,
            "ok": ok,
        })


async def monitor(client: httpx.AsyncClient, stop: asyncio.Event, out: list) -> None:
    while not stop.is_set():
        try:
            data = (await client.get("/api/system")).json()
            out.append({
                "load_1m": data["load_average"]["1m"],
                "cpu": data["cpu_percent"],
                "mem_percent": (data.get("memory") or {}).get("used_percent"),
            })
        except (httpx.HTTPError, ValueError, KeyError):
            pass
        try:
            await asyncio.wait_for(stop.wait(), timeout=2)
        except asyncio.TimeoutError:
            pass


async def network_rtt(client: httpx.AsyncClient, n: int = 15) -> dict:
    """Sequential /health calls: mostly network round-trip time."""
    times = []
    for _ in range(n):
        start = time.perf_counter()
        await client.get("/health")
        times.append((time.perf_counter() - start) * 1000)
    return {"median_ms": round(statistics.median(times), 1), "min_ms": round(min(times), 1)}


def mean(values):
    values = [v for v in values if v is not None and v == v]
    return round(statistics.fmean(values), 2) if values else None


async def run_level(base_url: str, users: int, duration: float) -> dict:
    limits = httpx.Limits(max_connections=users + 2, max_keepalive_connections=users + 2)
    async with httpx.AsyncClient(base_url=base_url, timeout=30, limits=limits) as client:
        samples: list = []
        system: list = []
        stop = asyncio.Event()
        mon = asyncio.create_task(monitor(client, stop, system))
        started = time.perf_counter()
        stop_at = started + duration
        await asyncio.gather(*(user(client, stop_at, samples) for _ in range(users)))
        elapsed = time.perf_counter() - started
        stop.set()
        await mon

    ok = [s for s in samples if s["ok"]]
    lat = [s["ms"] for s in ok]
    result = {
        "users": users,
        "requests": len(samples),
        "errors": len(samples) - len(ok),
        "error_rate": round((len(samples) - len(ok)) / max(1, len(samples)), 4),
        "rps": round(len(ok) / elapsed, 1),
        "latency_ms": {
            "mean": mean(lat),
            "p50": round(percentile(lat, 50), 1),
            "p95": round(percentile(lat, 95), 1),
            "p99": round(percentile(lat, 99), 1),
        },
        "read_p50_ms": round(percentile([s["ms"] for s in ok if s["kind"] == "read"], 50), 1),
        "write_p50_ms": round(percentile([s["ms"] for s in ok if s["kind"] == "write"], 50), 1),
        "server_ms_mean": mean([s["server_ms"] for s in ok]),
        "server": {
            "load_1m_max": max((s["load_1m"] for s in system if s["load_1m"] is not None), default=None),
            "cpu_mean": mean([s["cpu"] for s in system]),
            "cpu_max": max((s["cpu"] for s in system if s["cpu"] is not None), default=None),
            "mem_percent_mean": mean([s["mem_percent"] for s in system]),
        },
    }
    return result


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", required=True, help="base URL of the deployment")
    parser.add_argument("--label", required=True, help="name for this deployment, e.g. vps-4gb")
    parser.add_argument("--levels", default="1,5,10,25,50", help="comma-separated concurrent users")
    parser.add_argument("--duration", type=float, default=20, help="seconds per level")
    parser.add_argument("--out", default=str(Path(__file__).parent / "results"))
    args = parser.parse_args()

    base_url = args.url.rstrip("/")
    async with httpx.AsyncClient(base_url=base_url, timeout=15) as client:
        info = (await client.get("/api/system")).json()
        rtt = await network_rtt(client)
    print(f"{args.label}: host {info['host']}, {info['cpu_count']} CPUs, "
          f"{info['memory']['total_mb']} MB RAM, network RTT ~{rtt['median_ms']} ms")

    levels = []
    for users in [int(x) for x in args.levels.split(",")]:
        result = await run_level(base_url, users, args.duration)
        levels.append(result)
        lat = result["latency_ms"]
        print(f"  {users:>3} users: {result['rps']:>7} req/s  p50 {lat['p50']:>7} ms  "
              f"p95 {lat['p95']:>7} ms  errors {result['error_rate']:.1%}  "
              f"cpu {result['server']['cpu_mean']}%  load {result['server']['load_1m_max']}")
        await asyncio.sleep(3)  # let the server settle between levels

    report = {
        "label": args.label,
        "url": base_url,
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "duration_per_level_s": args.duration,
        "server": {k: info[k] for k in ("host", "cpu_count", "memory", "deployment")},
        "network_rtt": rtt,
        "levels": levels,
    }
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{args.label}.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"saved {path}")


if __name__ == "__main__":
    asyncio.run(main())
