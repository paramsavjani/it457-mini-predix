from datetime import datetime, timedelta

from app.twin import compute_health, slope_per_minute

T0 = datetime(2026, 1, 1)


def make_rows(temps, **fixed):
    base = {"vibration": 3.0, "rpm": 3000.0, "pressure": 20.0, **fixed}
    return [{"ts": T0 + timedelta(seconds=2 * i), "temperature": t, **base} for i, t in enumerate(temps)]


def test_slope_per_minute():
    # +1 degree every 2 seconds = 30 degrees per minute
    assert abs(slope_per_minute([(0, 0), (2, 1), (4, 2)]) - 30.0) < 1e-9


def test_steady_machine_is_healthy():
    result = compute_health(make_rows([70.0] * 20))
    assert result["status"] == "healthy"
    assert result["minutes_to_critical"] is None


def test_overheating_machine_is_flagged():
    result = compute_health(make_rows([95.0 + i * 0.5 for i in range(20)], vibration=9.0))
    assert result["status"] in ("degraded", "critical")
    assert result["temp_trend"] > 0
    assert result["minutes_to_critical"] is not None


def test_no_data():
    assert compute_health([])["status"] == "no-data"
