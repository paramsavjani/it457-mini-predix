import pytest
from pydantic import ValidationError

from app.readings import Reading, ReadingBatch

GOOD = {"asset_id": "GT-01", "temperature": 70.0, "vibration": 3.0, "rpm": 3000.0, "pressure": 21.0}


def test_valid_reading_is_accepted():
    r = Reading(**GOOD)
    assert r.asset_id == "GT-01"
    assert r.ts is None


@pytest.mark.parametrize("field,value", [
    ("temperature", 500.0),
    ("vibration", -1.0),
    ("rpm", 50000.0),
    ("pressure", -5.0),
])
def test_out_of_range_values_are_rejected(field, value):
    with pytest.raises(ValidationError):
        Reading(**{**GOOD, field: value})


def test_empty_asset_id_is_rejected():
    with pytest.raises(ValidationError):
        Reading(**{**GOOD, "asset_id": ""})


def test_batch_must_not_be_empty():
    with pytest.raises(ValidationError):
        ReadingBatch(readings=[])
