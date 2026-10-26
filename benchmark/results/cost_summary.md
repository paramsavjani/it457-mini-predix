# Cost analysis

Prices: AWS Mumbai on-demand (public price list, Oct 2026); VPS prices from our invoices. 1 USD = ₹96.5. AWS rows include 200 GB/month of internet traffic ($10.93); the VPS plans include bandwidth.

## 1. Tested deployments

| Deployment | Monthly cost | Peak req/s (measured) | Cost per 100 req/s |
|---|---|---|---|
| Mumbai VPS 4 vCPU / 16 GB (Docker + local PostgreSQL) | ₹2,399 ($24.86) | 379.3 | ₹632 |
| Africa VPS 3 vCPU / 4 GB (Docker + local PostgreSQL) | ₹1,700 ($17.62) | 193.2 | ₹880 |
| AWS t3.micro 2 vCPU / 1 GB + local PostgreSQL | ₹2,020 ($20.93) | 113.2 | ₹1,784 |
| AWS t3.micro + RDS db.t4g.micro (managed DB) | ₹3,752 ($38.88) | 266.4 | ₹1,408 |
| AWS t3.medium 2 vCPU / 4 GB + local PostgreSQL | ₹4,387 ($45.46) | 183.8 | ₹2,387 |

## 2. Same-size machine on AWS

| Our VPS | Specs | VPS / month | AWS equivalent | AWS on-demand | AWS 3-yr reserved | AWS with RDS (managed DB) |
|---|---|---|---|---|---|---|
| vps-africa-4gb | 3 vCPU / 4 GB / 72 GB disk | ₹1,700 | t3.medium | ₹4,844 | ₹2,849 | ₹10,936 (t3.medium + db.t4g.medium) |
| vps-africa-8gb | 4 vCPU / 8 GB / 242 GB disk | ₹4,667 | t3.large | ₹9,496 | ₹5,503 | ₹19,939 (t3.large + db.t4g.large) |
| vps-mumbai-16gb | 4 vCPU / 16 GB / 193 GB disk | ₹2,399 | m6a.xlarge | ₹10,580 | ₹5,852 | ₹21,454 (m6a.xlarge + db.t4g.large) |

**3-year total for the 16 GB server:** VPS (Hostinger) ₹86,364, AWS on-demand ₹380,880, AWS 3-yr reserved ₹210,672, AWS + RDS ₹772,344

## 3. Scaling scenario: 10x traffic spike 4 hours a day

Normal load 200 req/s, peak 2000 req/s for 4 h/day (like a cricket match or a Tatkal booking window).

| Option | How it handles the peak | Monthly cost |
|---|---|---|
| Mumbai VPS fleet | 6 servers (379 req/s each) running all month, manual setup | ₹14,394 |
| AWS Auto Scaling (t3.medium, 184 req/s each) | 2 always on, scales to 11 during the spike, + load balancer | ₹24,975 |
