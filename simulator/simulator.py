"""Turbine sensor simulator: the "edge" of Mini-Predix.

Each virtual machine produces temperature, vibration, RPM and pressure
readings that drift slowly around a normal operating point. Every interval
the simulator sends one batch with a reading per machine to the API,
like a Predix Machine gateway forwarding data to the cloud.
"""
import json
import logging
import os
import random
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

API_URL = os.getenv("API_URL", "http://localhost:8090").rstrip("/")
TURBINES = int(os.getenv("SIM_TURBINES", "6"))
INTERVAL = float(os.getenv("SIM_INTERVAL_SECONDS", "2"))
FAULT_PROBABILITY = float(os.getenv("SIM_FAULT_PROBABILITY", "0.02"))
BUFFER_LIMIT = 500  # batches kept while the API is unreachable

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("simulator")

# Normal operating point per metric: (mean, noise std dev)
NORMAL = {
    "temperature": (72.0, 0.8),
    "vibration": (3.5, 0.25),
    "rpm": (3000.0, 15.0),
    "pressure": (21.0, 0.3),
}


# Fault types: metric -> amount added per tick while the fault is active.
# "overheating" ramps up slowly so the digital twin can predict it early.
FAULTS = {
    "overheating": {"temperature": 1.5},
    "bearing_wear": {"vibration": 0.35, "temperature": 0.3},
    "overspeed": {"rpm": 45.0},
    "pressure_leak": {"pressure": 0.6},
}


@dataclass
class Machine:
    asset_id: str
    drift: dict = field(default_factory=lambda: {m: 0.0 for m in NORMAL})
    fault: str | None = None
    fault_ticks: int = 0
    fault_offset: dict = field(default_factory=lambda: {m: 0.0 for m in NORMAL})

    def update_fault(self) -> None:
        if self.fault is None and random.random() < FAULT_PROBABILITY:
            self.fault = random.choice(list(FAULTS))
            self.fault_ticks = random.randint(15, 40)
            log.info("%s: fault started (%s, %d ticks)", self.asset_id, self.fault, self.fault_ticks)
        if self.fault is not None:
            for metric, step in FAULTS[self.fault].items():
                self.fault_offset[metric] += step
            self.fault_ticks -= 1
            if self.fault_ticks <= 0:
                log.info("%s: fault cleared (%s)", self.asset_id, self.fault)
                self.fault = None
        else:
            # machine recovers gradually after maintenance
            for metric in self.fault_offset:
                self.fault_offset[metric] *= 0.8

    def read(self) -> dict:
        self.update_fault()
        values = {}
        for metric, (mean, std) in NORMAL.items():
            # slow random walk around the mean so the charts look realistic
            self.drift[metric] = 0.95 * self.drift[metric] + random.gauss(0, std * 0.3)
            value = mean + self.drift[metric] + self.fault_offset[metric] + random.gauss(0, std)
            values[metric] = round(value, 2)
        return {"asset_id": self.asset_id, **values}


def post_json(url: str, payload: dict) -> int:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status


def get_json(url: str):
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.load(resp)


def wait_for_api() -> list[str]:
    while True:
        try:
            return [a["id"] for a in get_json(f"{API_URL}/api/assets")]
        except (urllib.error.URLError, OSError) as exc:
            log.info("waiting for API at %s (%s)", API_URL, exc)
            time.sleep(3)


def main() -> None:
    asset_ids = wait_for_api()[:TURBINES]
    machines = [Machine(a) for a in asset_ids]
    log.info("simulating %d machines every %.1fs -> %s", len(machines), INTERVAL, API_URL)

    latencies: deque[float] = deque(maxlen=50)
    # store-and-forward buffer, like Predix Machine when the network drops
    pending: deque[list[dict]] = deque(maxlen=BUFFER_LIMIT)
    sent = 0
    while True:
        now = datetime.now(timezone.utc).isoformat()
        pending.append([{**m.read(), "ts": now} for m in machines])
        while pending:
            start = time.perf_counter()
            try:
                post_json(f"{API_URL}/api/readings", {"readings": pending[0]})
            except (urllib.error.URLError, OSError) as exc:
                log.warning("send failed, %d batches buffered: %s", len(pending), exc)
                break
            pending.popleft()
            latencies.append((time.perf_counter() - start) * 1000)
            sent += 1
            if sent % 30 == 0:
                log.info("sent %d batches, avg latency %.1f ms", sent, sum(latencies) / len(latencies))
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
