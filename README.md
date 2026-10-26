# Mini-Predix

A small industrial IoT monitoring app based on the **GE Predix** case study (IT457 Cloud Computing, Group 27).

Virtual turbines send sensor data to an API, which stores it, raises alerts and predicts failures with a simple digital twin. A live dashboard shows everything.

**Live demo:** http://200.234.36.181:8090 (Mumbai VPS) · http://13.203.224.195:8090 (AWS EC2 + RDS)

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

## Results

| Deployment | Peak throughput | Monthly cost |
|---|---|---|
| Mumbai VPS (4 vCPU, 16 GB) | 379 req/s | ₹2,399 |
| AWS t3.micro + RDS (managed DB) | 266 req/s | ₹3,752 |
| Africa VPS (3 vCPU, 4 GB) | 193 req/s | ₹1,700 |
| AWS t3.medium (2 vCPU, 4 GB) | 184 req/s | ₹4,387 |
| AWS t3.micro (2 vCPU, 1 GB) | 113 req/s | ₹2,020 |

- Same-size machines perform about the same on a VPS and on AWS.
- Moving the database to RDS made the small AWS server 2.4x faster.
- The VPS is about 4x cheaper for steady load; AWS costs more but adds scaling, backups and failover.

Full analysis: [`docs/analysis.md`](docs/analysis.md)

## Team

| Student ID | Name |
|---|---|
| 202303009 | |
| 202303046 | Param |
| 202301436 | |
