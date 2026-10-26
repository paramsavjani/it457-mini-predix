"""Asset registry: the machines we monitor (like the Predix Asset service)."""
from fastapi import APIRouter, HTTPException

from . import db

router = APIRouter(prefix="/api/assets", tags=["assets"])

SEED_ASSETS = [
    ("GT-01", "Gas Turbine 1", "gas_turbine", "Plant A - Ahmedabad"),
    ("GT-02", "Gas Turbine 2", "gas_turbine", "Plant A - Ahmedabad"),
    ("GT-03", "Gas Turbine 3", "gas_turbine", "Plant B - Mumbai"),
    ("WT-01", "Wind Turbine 1", "wind_turbine", "Wind Farm - Kutch"),
    ("WT-02", "Wind Turbine 2", "wind_turbine", "Wind Farm - Kutch"),
    ("JE-01", "Jet Engine 1", "jet_engine", "Hangar - Delhi"),
    ("JE-02", "Jet Engine 2", "jet_engine", "Hangar - Delhi"),
    ("LC-01", "Locomotive 1", "locomotive", "Rail Yard - Vadodara"),
]


def seed_assets(conn) -> None:
    conn.cursor().executemany(
        """INSERT INTO assets (id, name, asset_type, location)
           VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING""",
        SEED_ASSETS,
    )


@router.get("")
def list_assets():
    return db.fetch_all("SELECT * FROM assets ORDER BY id")


@router.get("/{asset_id}")
def get_asset(asset_id: str):
    asset = db.fetch_one("SELECT * FROM assets WHERE id = %s", (asset_id,))
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return asset
