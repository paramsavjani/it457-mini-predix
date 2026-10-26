"""Cost comparison: our VPS servers vs the same workload on AWS.

Combines the prices in costs.json with the measured capacity in results/
(peak requests/second from the on-server "-localhost" benchmarks) and
writes results/cost_summary.md plus graphs in results/graphs/.

Usage: python cost_model.py
"""
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).parent
RESULTS = HERE / "results"
GRAPHS = RESULTS / "graphs"

cfg = json.loads((HERE / "costs.json").read_text())
AWS = cfg["aws_prices"]
VPS = cfg["vps"]
HOURS = cfg["hours_per_month"]
INR = VPS["usd_inr"]
EGRESS_GB = cfg["assumptions"]["monthly_egress_gb"]


def ec2(instance: str, disk_gb: float) -> float:
    return AWS["ec2_hourly"][instance] * HOURS + AWS["ebs_gp3_gb_month"] * disk_gb


def rds(instance: str, storage_gb: float = 20) -> float:
    return AWS["rds_postgres_hourly"][instance] * HOURS + AWS["rds_storage_gb_month"] * storage_gb


def egress(gb: float = EGRESS_GB) -> float:
    """AWS charges for internet traffic out; our VPS plans include it."""
    return max(0.0, gb - AWS["data_transfer_free_gb"]) * AWS["data_transfer_out_gb"]


def peak_rps(label: str) -> float | None:
    path = RESULTS / f"{label}-localhost.json"
    if not path.exists():
        return None
    return max(level["rps"] for level in json.loads(path.read_text())["levels"])


def inr(usd: float) -> int:
    return round(usd * INR)


# --- 1. What each tested deployment costs per month -------------------------
tested = [
    # label, description, monthly USD
    ("vps-mumbai-16gb", "Mumbai VPS 4 vCPU / 16 GB (Docker + local PostgreSQL)", VPS["vps-mumbai-16gb"]["monthly_inr"] / INR),
    ("vps-africa-4gb", "Africa VPS 3 vCPU / 4 GB (Docker + local PostgreSQL)", VPS["vps-africa-4gb"]["monthly_inr"] / INR),
    ("aws-ec2-t3micro", "AWS t3.micro 2 vCPU / 1 GB + local PostgreSQL", ec2("t3.micro", 20) + egress()),
    ("aws-ec2-rds", "AWS t3.micro + RDS db.t4g.micro (managed DB)", ec2("t3.micro", 20) + rds("db.t4g.micro") + egress()),
    ("aws-ec2-t3medium", "AWS t3.medium 2 vCPU / 4 GB + local PostgreSQL", ec2("t3.medium", 20) + egress()),
]

# --- 2. Same-size AWS machine for each VPS -----------------------------------
same_size = [
    # vps key, AWS instance, managed-DB option
    ("vps-africa-4gb", "t3.medium", "db.t4g.medium"),
    ("vps-africa-8gb", "t3.large", "db.t4g.large"),
    ("vps-mumbai-16gb", "m6a.xlarge", "db.t4g.large"),
]


def same_size_rows():
    rows = []
    for key, inst, db in same_size:
        v = VPS[key]
        disk = v["disk_gb"]
        on_demand = ec2(inst, disk) + egress()
        ri = AWS["ec2_reserved_monthly_effective"][inst]
        reserved_3yr = ri["3yr_all_upfront"] + AWS["ebs_gp3_gb_month"] * disk + egress()
        with_rds = ec2(inst, 20) + rds(db, 50) + egress()
        rows.append({
            "key": key, "vps_inr": v["monthly_inr"], "spec": f"{v['vcpu']} vCPU / {v['ram_gb']} GB / {disk} GB disk",
            "aws": inst, "on_demand": on_demand, "reserved_3yr": reserved_3yr, "with_rds": with_rds, "db": db,
        })
    return rows


# --- 3. Scaling scenario: a daily traffic spike --------------------------------
# Like a cricket match on Hotstar or a Tatkal window on IRCTC: 10x traffic for
# 4 hours a day. A VPS fleet must be sized for the peak all month; AWS Auto
# Scaling adds instances only during the spike (plus a load balancer).
BASE_RPS, PEAK_RPS, PEAK_HOURS_PER_DAY = 200, 2000, 4


def spike_scenario():
    vps_rps = peak_rps("vps-mumbai-16gb")
    vps_count = math.ceil(PEAK_RPS / vps_rps)
    vps_cost = vps_count * VPS["vps-mumbai-16gb"]["monthly_inr"] / INR

    aws_rps = peak_rps("aws-ec2-t3medium")
    base_n = math.ceil(BASE_RPS / aws_rps)
    peak_n = math.ceil(PEAK_RPS / aws_rps)
    hourly = AWS["ec2_hourly"]["t3.medium"]
    extra_hours = (peak_n - base_n) * PEAK_HOURS_PER_DAY * 30
    alb = AWS["alb_hourly"] * HOURS + AWS["alb_lcu_hourly"] * 5 * HOURS  # ~5 LCU average
    aws_cost = base_n * hourly * HOURS + extra_hours * hourly + alb + egress(EGRESS_GB * 5)
    return {
        "vps_rps": vps_rps, "vps_count": vps_count, "vps_cost": vps_cost,
        "aws_rps": aws_rps, "base_n": base_n, "peak_n": peak_n, "aws_cost": aws_cost,
    }


def bar_chart(labels, values, title, ylabel, filename, colors):
    fig, ax = plt.subplots(figsize=(8, 4.4), dpi=150)
    bars = ax.bar(labels, values, color=colors)
    ax.bar_label(bars, labels=[f"₹{v:,.0f}" for v in values], padding=3, fontsize=8)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", alpha=0.3)
    plt.setp(ax.get_xticklabels(), rotation=15, ha="right", fontsize=8)
    fig.tight_layout()
    fig.savefig(GRAPHS / filename)
    plt.close(fig)


def main() -> None:
    GRAPHS.mkdir(parents=True, exist_ok=True)
    out = [f"# Cost analysis\n\nPrices: AWS Mumbai on-demand (public price list, Oct 2026); VPS prices from our invoices. "
           f"1 USD = ₹{INR}. AWS rows include {EGRESS_GB} GB/month of internet traffic "
           f"(${egress():.2f}); the VPS plans include bandwidth.\n"]

    out.append("## 1. Tested deployments\n")
    out.append("| Deployment | Monthly cost | Peak req/s (measured) | Cost per 100 req/s |")
    out.append("|---|---|---|---|")
    chart = []
    for label, desc, usd in tested:
        rps = peak_rps(label)
        per100 = f"₹{inr(usd) / rps * 100:,.0f}" if rps else "-"
        out.append(f"| {desc} | ₹{inr(usd):,} (${usd:.2f}) | {rps or '-'} | {per100} |")
        if rps:
            chart.append((label, inr(usd) / rps * 100))
    bar_chart([c[0] for c in chart], [c[1] for c in chart], "Monthly cost per 100 req/s of capacity (lower is better)",
              "₹ per month", "cost_per_capacity.png", ["#dc2626", "#dc2626", "#2563eb", "#2563eb", "#2563eb"])

    out.append("\n## 2. Same-size machine on AWS\n")
    out.append("| Our VPS | Specs | VPS / month | AWS equivalent | AWS on-demand | AWS 3-yr reserved | AWS with RDS (managed DB) |")
    out.append("|---|---|---|---|---|---|---|")
    rows = same_size_rows()
    for r in rows:
        out.append(f"| {r['key']} | {r['spec']} | ₹{r['vps_inr']:,} | {r['aws']} | ₹{inr(r['on_demand']):,} | "
                   f"₹{inr(r['reserved_3yr']):,} | ₹{inr(r['with_rds']):,} ({r['aws']} + {r['db']}) |")

    # 3-year total cost for the Mumbai-size machine
    m = next(r for r in rows if r["key"] == "vps-mumbai-16gb")
    tco = {
        "VPS (Hostinger)": m["vps_inr"] * 36,
        "AWS on-demand": inr(m["on_demand"]) * 36,
        "AWS 3-yr reserved": inr(m["reserved_3yr"]) * 36,
        "AWS + RDS": inr(m["with_rds"]) * 36,
    }
    bar_chart(list(tco), list(tco.values()), "3-year cost for a 4 vCPU / 16 GB server", "₹ over 3 years",
              "tco_3yr.png", ["#dc2626", "#2563eb", "#60a5fa", "#1e40af"])
    out.append("\n**3-year total for the 16 GB server:** " +
               ", ".join(f"{k} ₹{v:,}" for k, v in tco.items()) + "\n")

    s = spike_scenario()
    out.append("## 3. Scaling scenario: 10x traffic spike 4 hours a day\n")
    out.append(f"Normal load {BASE_RPS} req/s, peak {PEAK_RPS} req/s for {PEAK_HOURS_PER_DAY} h/day "
               f"(like a cricket match or a Tatkal booking window).\n")
    out.append("| Option | How it handles the peak | Monthly cost |")
    out.append("|---|---|---|")
    out.append(f"| Mumbai VPS fleet | {s['vps_count']} servers ({s['vps_rps']:.0f} req/s each) running all month, manual setup | ₹{inr(s['vps_cost']):,} |")
    out.append(f"| AWS Auto Scaling (t3.medium, {s['aws_rps']:.0f} req/s each) | {s['base_n']} always on, scales to {s['peak_n']} during the spike, + load balancer | ₹{inr(s['aws_cost']):,} |")
    bar_chart(["VPS fleet sized for peak", "AWS Auto Scaling"], [inr(s["vps_cost"]), inr(s["aws_cost"])],
              "Monthly cost with a daily 10x traffic spike", "₹ per month", "spike_scenario.png", ["#dc2626", "#2563eb"])

    text = "\n".join(out) + "\n"
    (RESULTS / "cost_summary.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
