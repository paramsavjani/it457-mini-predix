# Mini-Predix

A small industrial IoT monitoring app based on the **GE Predix** case study (IT457 Cloud Computing, Group 27).

Virtual turbines send sensor data to an API, which stores it, raises alerts and predicts failures with a simple digital twin. A live dashboard shows everything.

**Live demo:** http://200.234.36.181:8090

## How it works

```
simulator  ──>  API (FastAPI)  ──>  PostgreSQL
                     │
                     └──>  dashboard
```

- `simulator/`: fake sensor data with random faults
- `api/`: ingestion, alerts, digital twin, dashboard
- `benchmark/`: load test and results
- `deploy/`: deploy to a VPS
- `week1/`, `week2/`: reports

## Run

```bash
cp .env.example .env
docker compose up -d --build
```

Open http://localhost:8090

## Results (Mumbai VPS, 4 vCPU, 16 GB)

| Test | Peak throughput | Median response | Errors |
|---|---|---|---|
| From laptop (internet) | 155 req/s | 82 ms | 0% |
| On the server | 379 req/s | 7 ms | 0% |

Most of the delay for users is network time, not server time. Full results: [`benchmark/results/summary.md`](benchmark/results/summary.md)

## Team

| Student ID | Name |
|---|---|
| 202303009 | |
| 202303046 | Param |
| 202301436 | |
