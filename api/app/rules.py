"""Threshold alert rules applied to every incoming reading.

This is the simplest form of industrial analytics: compare each sensor
value with a warning and a critical limit.
"""
from dataclasses import dataclass

# metric -> (warning limit, critical limit, unit)
THRESHOLDS: dict[str, tuple[float, float, str]] = {
    "temperature": (90.0, 105.0, "C"),
    "vibration": (7.0, 10.0, "mm/s"),
    "rpm": (3700.0, 3900.0, "rpm"),
    "pressure": (28.0, 32.0, "bar"),
}


@dataclass
class Alert:
    asset_id: str
    metric: str
    value: float
    severity: str
    message: str


def evaluate(asset_id: str, values: dict[str, float]) -> list[Alert]:
    alerts = []
    for metric, (warn, crit, unit) in THRESHOLDS.items():
        value = values.get(metric)
        if value is None:
            continue
        if value >= crit:
            severity, limit = "critical", crit
        elif value >= warn:
            severity, limit = "warning", warn
        else:
            continue
        alerts.append(
            Alert(asset_id, metric, value, severity,
                  f"{metric} {value:.1f} {unit} above {severity} limit {limit:g} {unit}")
        )
    return alerts
