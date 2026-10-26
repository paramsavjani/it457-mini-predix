from app.rules import evaluate

NORMAL = {"temperature": 70.0, "vibration": 3.0, "rpm": 3000.0, "pressure": 20.0}


def test_normal_reading_has_no_alerts():
    assert evaluate("GT-01", NORMAL) == []


def test_warning_level():
    alerts = evaluate("GT-01", {**NORMAL, "temperature": 95.0})
    assert len(alerts) == 1
    assert alerts[0].metric == "temperature"
    assert alerts[0].severity == "warning"


def test_critical_level_and_exact_limit():
    alerts = evaluate("GT-01", {**NORMAL, "vibration": 10.0})
    assert alerts[0].severity == "critical"


def test_multiple_metrics_alert_together():
    alerts = evaluate("GT-01", {**NORMAL, "temperature": 110.0, "pressure": 29.0})
    assert {(a.metric, a.severity) for a in alerts} == {
        ("temperature", "critical"),
        ("pressure", "warning"),
    }
