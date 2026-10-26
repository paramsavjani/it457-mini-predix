"""Turn benchmark JSON files into comparison graphs and a Markdown table.

Usage:
  python plot_results.py            # reads results/*.json
  python plot_results.py a.json b.json
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).parent
RESULTS = HERE / "results"
GRAPHS = RESULTS / "graphs"

COLORS = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2"]


def load(paths: list[Path]) -> list[dict]:
    reports = [json.loads(p.read_text()) for p in paths]
    return sorted(reports, key=lambda r: r["label"])


def plot(reports: list[dict], title: str, ylabel: str, value, filename: str) -> Path:
    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=150)
    for color, report in zip(COLORS, reports):
        users = [lvl["users"] for lvl in report["levels"]]
        ax.plot(users, [value(lvl) for lvl in report["levels"]], marker="o", color=color,
                linewidth=2, label=report["label"])
    ax.set_title(title)
    ax.set_xlabel("Concurrent users")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    path = GRAPHS / filename
    fig.savefig(path)
    plt.close(fig)
    return path


def markdown_table(reports: list[dict]) -> str:
    lines = [
        "| Deployment | Users | Req/s | p50 ms | p95 ms | p99 ms | Errors | Server ms | CPU % | Max load |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in reports:
        for lvl in r["levels"]:
            lat, srv = lvl["latency_ms"], lvl["server"]
            lines.append(
                f"| {r['label']} | {lvl['users']} | {lvl['rps']} | {lat['p50']} | {lat['p95']} | "
                f"{lat['p99']} | {lvl['error_rate']:.1%} | {lvl['server_ms_mean']} | "
                f"{srv['cpu_mean']} | {srv['load_1m_max']:.2f} |"
            )
    lines.append("")
    lines.append("| Deployment | CPUs | RAM (MB) | Network RTT (ms) |")
    lines.append("|---|---|---|---|")
    for r in reports:
        lines.append(f"| {r['label']} | {r['server']['cpu_count']} | "
                     f"{r['server']['memory']['total_mb']} | {r['network_rtt']['median_ms']} |")
    return "\n".join(lines)


def main() -> None:
    paths = [Path(p) for p in sys.argv[1:]] or sorted(RESULTS.glob("*.json"))
    if not paths:
        sys.exit("no result files found")
    reports = load(paths)
    GRAPHS.mkdir(parents=True, exist_ok=True)

    # "-localhost" runs were made on the server itself (server capacity);
    # the others went over the internet from a laptop (what users feel).
    groups = {
        "internet": ("over the internet", [r for r in reports if not r["label"].endswith("-localhost")]),
        "onserver": ("on the server", [r for r in reports if r["label"].endswith("-localhost")]),
    }
    made = []
    for key, (where, group) in groups.items():
        if not group:
            continue
        made += [
            plot(group, f"Median response time ({where})", "p50 latency (ms)",
                 lambda l: l["latency_ms"]["p50"], f"{key}_latency_p50.png"),
            plot(group, f"95th percentile response time ({where})", "p95 latency (ms)",
                 lambda l: l["latency_ms"]["p95"], f"{key}_latency_p95.png"),
            plot(group, f"Throughput ({where})", "Successful requests / second",
                 lambda l: l["rps"], f"{key}_throughput.png"),
            plot(group, f"Server CPU during test ({where})", "Mean CPU (%)",
                 lambda l: l["server"]["cpu_mean"], f"{key}_cpu.png"),
        ]
    table = markdown_table(reports)
    (RESULTS / "summary.md").write_text(table + "\n")
    print(table)
    for path in made:
        print(f"saved {path}")


if __name__ == "__main__":
    main()
