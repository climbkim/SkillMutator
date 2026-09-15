"""plot_iter_trajectory.py — 3-panel figure (one per oracle, select mode) of
per-iter detection rate per scanner. Reads tab_iter_trajectory.csv.
"""
import csv, sys
from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = Path("outputs/tab_iter_trajectory.csv")
OUT_DIR = Path("outputs")

ORACLE_ORDER = ["gpt-4o-mini", "gpt-5.4-mini", "gpt-5.4"]
ORACLE_TITLE = {
    "gpt-4o-mini":  "GPT-4o-mini dataset",
    "gpt-5.4-mini": "GPT-5.4-mini dataset",
    "gpt-5.4":      "GPT-5.4 dataset",
}
SCANNER_STYLE = {
    "ss":                ("skill-security-scan",   "#7f7f7f", "--", "s"),
    "snyk":              ("Snyk Agent Scan",       "#444444", ":",  "D"),
    "llm/gpt-4o-mini-self":  ("GPT-4o-mini (self)",    "#1f77b4", "-",  "o"),
    "llm/gpt-5.4-mini-self": ("GPT-5.4-mini (self)",   "#ff7f0e", "-",  "o"),
    "llm/gpt-5.4-self":      ("GPT-5.4 (self)",        "#2ca02c", "-",  "o"),
    "llm/gpt-4o-mini":       ("GPT-4o-mini (cross)",   "#1f77b4", "-.", "^"),
    "llm/gpt-5.4-mini":      ("GPT-5.4-mini (cross)",  "#ff7f0e", "-.", "^"),
}


def main():
    data = defaultdict(lambda: defaultdict(list))
    n_at_iter0 = {}
    for r in csv.DictReader(open(SRC, encoding="utf-8")):
        oracle = r["oracle"]; sc = r["scanner"]
        it = int(r["iter"]); rate = float(r["rate_pct"]); n = int(r["n"])
        data[oracle][sc].append((it, rate, n))
        if it == 0: n_at_iter0[oracle] = n

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharey=True)
    for ax, oracle in zip(axes, ORACLE_ORDER):
        if oracle not in data: continue
        n0 = n_at_iter0.get(oracle, 0)
        ax.set_title(f"{ORACLE_TITLE[oracle]} ($n={n0}$)")
        for sc, points in data[oracle].items():
            if sc not in SCANNER_STYLE: continue
            label, color, ls, mk = SCANNER_STYLE[sc]
            points.sort(key=lambda x: x[0])
            xs = [p[0] for p in points]; ys = [p[1] for p in points]
            ax.plot(xs, ys, label=label, color=color, linestyle=ls, marker=mk,
                    linewidth=1.7, markersize=6, markerfacecolor="white",
                    markeredgewidth=1.5)
        ax.set_xlabel("Refinement iteration")
        ax.set_xticks(range(5))
        ax.set_ylim(0, 100)
        ax.grid(True, alpha=0.3, linestyle=":")
    axes[0].set_ylabel("Detection rate (%)")

    handles, labels, seen = [], [], set()
    for ax in axes:
        for h, l in zip(*ax.get_legend_handles_labels()):
            if l not in seen:
                handles.append(h); labels.append(l); seen.add(l)
    fig.legend(handles, labels, loc="lower center", ncol=4,
               bbox_to_anchor=(0.5, -0.02), frameon=False)
    plt.tight_layout(rect=[0, 0.07, 1, 1])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png = OUT_DIR / "fig_iter_trajectory.png"
    pdf = OUT_DIR / "fig_iter_trajectory.pdf"
    fig.savefig(png, dpi=200, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved] {png}")
    print(f"[saved] {pdf}")


if __name__ == "__main__":
    main()
