-- Mini-Predix database schema.
-- assets   : the "Asset service" (what machines exist)
-- readings : the "Time-Series service" (sensor data over time)
-- alerts   : threshold violations raised during ingestion

CREATE TABLE IF NOT EXISTS assets (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    asset_type  TEXT NOT NULL,
    location    TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS readings (
    id           BIGSERIAL PRIMARY KEY,
    asset_id     TEXT NOT NULL REFERENCES assets(id),
    ts           TIMESTAMPTZ NOT NULL DEFAULT now(),
    temperature  DOUBLE PRECISION NOT NULL,  -- degrees C
    vibration    DOUBLE PRECISION NOT NULL,  -- mm/s RMS
    rpm          DOUBLE PRECISION NOT NULL,
    pressure     DOUBLE PRECISION NOT NULL   -- bar
);

CREATE INDEX IF NOT EXISTS idx_readings_asset_ts ON readings (asset_id, ts DESC);

CREATE TABLE IF NOT EXISTS alerts (
    id        BIGSERIAL PRIMARY KEY,
    asset_id  TEXT NOT NULL REFERENCES assets(id),
    ts        TIMESTAMPTZ NOT NULL DEFAULT now(),
    metric    TEXT NOT NULL,
    value     DOUBLE PRECISION NOT NULL,
    severity  TEXT NOT NULL,  -- warning | critical
    message   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts (ts DESC);
