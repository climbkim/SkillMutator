"""Plot IER dynamics with broken y-axis variants.

Reads:
  ier_dynamics.csv

Outputs:
  ier_dynamics_v1.pdf/png  — aggressive break [22, 65]; gpt-4o-mini LLM clipped
  ier_dynamics_v2.pdf/png  — safe break [22, 26]; gpt-4o-mini LLM preserved

Layout: 1 row x 3 cols (oracle), each col split top/bottom (broken y-axis).
Colors: per scanner identity (ss, snyk, llm).
Line styles: rule-based (ss, snyk) = dashed; LLM-based (llm) = solid.
Iter labels: iter 1 ~ iter 5 (1-indexed display).
"""
import csv
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib import gridspec

# Outputs land in evaluate/outputs/ ; the per-variant CSVs are produced by
# figure_ier_dynamics_compute.py.
ROOT = Path(__file__).resolve().parents[2] / "outputs"
CSV_IN = ROOT / "ier_dynamics.csv"

ORACLES = ["gpt-4o-mini", "gpt-5.4-mini", "gpt-5.4"]
ORACLE_TITLES = {
    "gpt-4o-mini": "GPT-4o-mini oracle",
    "gpt-5.4-mini": "GPT-5.4-mini oracle",
    "gpt-5.4": "GPT-5.4 oracle",
}
SCANNERS = ["ss", "snyk", "llm"]
SCANNER_LABELS = {
    "ss": "skill-security-scan",
    "snyk": "Snyk Agent Scan",
    "llm": "LLM scanner (self)",
}
SCANNER_COLORS = {
    "ss":   "#d62728",   # red
    "snyk": "#1f77b4",   # blue
    "llm":  "#2ca02c",   # green
}
SCANNER_STYLES = {
    "ss":   "--",
    "snyk": "--",
    "llm":  "-",
}
SCANNER_MARKERS = {
    "ss":   "s",
    "snyk": "^",
    "llm":  "o",
}

# Annotation placement (in axis coords + points offset).
ANN_Y_BASE = 7
ANN_Y_BUMP = 14
ANN_CLOSE_PP = 5.0
ANN_X_OFFSET = 3
ANN_Y_TIGHT = 2

# Iter indices used internally (data column "iter" is 0..4).
ITER_VALS = [0, 1, 2, 3, 4]
# Display labels (1-indexed per user decision: iter 0..4 -> iter 1..5).
ITER_LABELS = ["iter\\,1", "iter\\,2", "iter\\,3", "iter\\,4", "iter\\,5"]


def load(csv_path=None):
    """Returns dict[oracle][scanner] -> list of (iter, rate%)."""
    if csv_path is None:
        csv_path = CSV_IN
    data = {o: {s: [] for s in SCANNERS} for o in ORACLES}
    with Path(csv_path).open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            o = r["oracle"]
            s = r["scanner"]
            if o in data and s in data[o]:
                data[o][s].append((int(r["iter"]), float(r["rate_pct"])))
    for o in data:
        for s in data[o]:
            data[o][s].sort()
    return data


def plot_oracle_panel(ax_top, ax_bot, oracle, data, break_low, break_high, ann_iters):
    """Plot one oracle panel with broken y-axis (top + bottom subplot pair)."""
    # Plot identical data on both axes; matplotlib auto-clips to ylim.
    for sc in SCANNERS:
        pts = data[oracle][sc]
        if not pts:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        for ax in (ax_top, ax_bot):
            ax.plot(
                xs, ys,
                color=SCANNER_COLORS[sc],
                linestyle=SCANNER_STYLES[sc],
                marker=SCANNER_MARKERS[sc],
                markersize=6,
                linewidth=1.6,
                label=SCANNER_LABELS[sc] if ax is ax_top else None,
            )

    # Annotate i0, i3, i4 on whichever pane the point falls into.
    ss_y_by_iter = dict(data[oracle].get("ss", []))
    ann_placement = {
        0: (-ANN_X_OFFSET, "right"),
        3: (-ANN_X_OFFSET, "right"),
        4: ( ANN_X_OFFSET, "left"),
    }
    tight_overrides = {
        ("gpt-4o-mini", "snyk", 3),
        ("gpt-4o-mini", "ss",   3),
    }

    for sc in SCANNERS:
        pts = data[oracle][sc]
        if not pts:
            continue
        pts_by_iter = dict(pts)
        color = SCANNER_COLORS[sc]
        for it in ann_iters:
            if it not in pts_by_iter:
                continue
            yv = pts_by_iter[it]
            # Choose which axis the annotation belongs to.
            if yv >= break_high:
                ax = ax_top
            elif yv <= break_low:
                ax = ax_bot
            else:
                # Value lies in the gap — clipped; skip annotation.
                continue
            y_off = ANN_Y_BASE
            va = "bottom"
            if yv >= 90:
                y_off = -ANN_Y_BASE
                va = "top"
            elif (oracle, sc, it) in tight_overrides:
                y_off = ANN_Y_TIGHT
            elif sc == "snyk":
                other = ss_y_by_iter.get(it)
                if other is not None and abs(yv - other) < ANN_CLOSE_PP:
                    y_off = ANN_Y_BUMP
            x_off, ha = ann_placement[it]
            ax.annotate(
                f"{yv:.1f}",
                xy=(it, yv),
                xytext=(x_off, y_off),
                textcoords="offset points",
                fontsize=8.5,
                color=color,
                ha=ha,
                va=va,
                fontweight="bold",
            )

    # Y-axis ranges
    ax_top.set_ylim(break_high, 100)
    ax_bot.set_ylim(0, break_low)

    # Hide adjacent spines for break effect
    ax_top.spines["bottom"].set_visible(False)
    ax_bot.spines["top"].set_visible(False)
    ax_top.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
    ax_bot.tick_params(axis="x", which="both", top=False)

    # Break markers (diagonal lines)
    d = 0.018
    kwargs = dict(transform=ax_top.transAxes, color="k", clip_on=False, linewidth=1)
    ax_top.plot((-d, +d), (-d, +d), **kwargs)
    ax_top.plot((1 - d, 1 + d), (-d, +d), **kwargs)
    kwargs["transform"] = ax_bot.transAxes
    ax_bot.plot((-d, +d), (1 - d, 1 + d), **kwargs)
    ax_bot.plot((1 - d, 1 + d), (1 - d, 1 + d), **kwargs)

    # x ticks and labels (only on bottom)
    ax_bot.set_xticks(ITER_VALS)
    ax_bot.set_xticklabels([lbl.replace("\\,", " ") for lbl in ITER_LABELS], fontsize=9)
    ax_bot.set_xlim(-0.6, 4.6)
    ax_top.set_xlim(-0.6, 4.6)

    # Grid
    for ax in (ax_top, ax_bot):
        ax.grid(True, axis="y", alpha=0.3, linestyle=":")
        ax.set_axisbelow(True)

    ax_top.set_title(ORACLE_TITLES[oracle], fontsize=11)


def make_figure(break_low, break_high, out_pdf, out_png, suffix="", csv_path=None):
    data = load(csv_path)
    fig = plt.figure(figsize=(11.5, 3.0))
    # height_ratios reflect zone heights for visual proportion.
    top_h = max(1.0, 100 - break_high)
    bot_h = max(1.0, break_low)
    gs = gridspec.GridSpec(
        2, 3,
        height_ratios=[top_h, bot_h],
        hspace=0.10,
        wspace=0.10,
        left=0.07, right=0.99, top=0.92, bottom=0.20,
    )

    axes_top = []
    axes_bot = []
    for col, oracle in enumerate(ORACLES):
        ax_top = fig.add_subplot(gs[0, col])
        ax_bot = fig.add_subplot(gs[1, col])
        axes_top.append(ax_top)
        axes_bot.append(ax_bot)
        ann_iters = [0, 3, 4]
        plot_oracle_panel(ax_top, ax_bot, oracle, data, break_low, break_high, ann_iters)
        # Hide y-tick labels on middle/right panels (sharey-like effect).
        if col > 0:
            ax_top.tick_params(axis="y", labelleft=False)
            ax_bot.tick_params(axis="y", labelleft=False)

    # Shared y-label on leftmost panel
    fig.text(
        0.015, 0.52,
        "Detection rate (%)",
        rotation=90, ha="center", va="center", fontsize=10,
    )

    # Single legend at bottom
    handles, labels = axes_top[0].get_legend_handles_labels()
    fig.legend(
        handles, labels,
        loc="lower center",
        ncol=3,
        bbox_to_anchor=(0.5, -0.05),
        frameon=False,
        fontsize=9.5,
    )

    fig.savefig(out_pdf, bbox_inches="tight")
    fig.savefig(out_png, bbox_inches="tight", dpi=150)
    plt.close(fig)
    print(f"wrote {out_pdf}")
    print(f"wrote {out_png}")


BREAKS = {
    "v1": (22, 65),   # aggressive — gpt-4o-mini LLM (26-44%) hidden in gap
    "v2": (22, 26),   # safe — preserves all data; 4pp gap
    "v3": (45, 68),   # mid — rule-based + gpt-4o-mini LLM bottom vs gpt-5.4(-mini) top
}

DATA_VARIANTS = {
    "":      ROOT / "ier_dynamics.csv",       # raw
    "pinA_": ROOT / "ier_dynamics_pinA.csv",  # iter 4 re-pinned to cross_matrix
    "pinD_": ROOT / "ier_dynamics_pinD.csv",  # full refusal-aware re-pin
}


def main():
    for data_prefix, csv_path in DATA_VARIANTS.items():
        for variant, (break_low, break_high) in BREAKS.items():
            out_stem = ROOT / f"ier_dynamics_{data_prefix}{variant}"
            make_figure(
                break_low=break_low,
                break_high=break_high,
                out_pdf=out_stem.with_suffix(".pdf"),
                out_png=out_stem.with_suffix(".png"),
                suffix=variant,
                csv_path=csv_path,
            )


if __name__ == "__main__":
    main()
