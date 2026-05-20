#!/usr/bin/env python3
"""
Generates comparison charts from multi-model experiment data.
Outputs PNGs to thesis/Images/ and PGFPlots code snippets.
"""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

COLORS = {
    "GPT-4o-mini": "#74b9ff",
    "GPT-5.4-mini": "#a29bfe",
    "GPT-5.4-nano": "#55efc4",
    "Claude Haiku 4.5": "#fd79a8",
}

MODEL_SELECTION = {
    "GPT-4o-mini": ("first", 50),
    "GPT-5.4-mini": ("last", 40),
    "GPT-5.4-nano": ("last", 40),
    "Claude Haiku 4.5": ("last", 40),
}


def load_summary(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def load_all_runs(base_dir: Path) -> dict:
    """Load raw run data for box plots, applying per-model selection and
    filtering to successful runs only (root_cause_correct = true)."""
    model_dirs = {
        "GPT-4o-mini": base_dir / "runs_4omini",
        "GPT-5.4-mini": base_dir / "runs_gpt54mini",
        "GPT-5.4-nano": base_dir / "runs_gpt54nano",
        "Claude Haiku 4.5": base_dir / "runs_haiku",
    }
    all_runs = {}
    for name, d in model_dirs.items():
        if d.exists():
            runs = []
            for f in sorted(d.glob("run_*.json")):
                with open(f) as fh:
                    runs.append(json.load(fh))
            mode, n = MODEL_SELECTION.get(name, ("all", 0))
            if mode == "first" and n > 0:
                runs = runs[:n]
            elif mode == "last" and n > 0 and len(runs) > n:
                runs = runs[-n:]
            successful = [r for r in runs if r.get("report", {}).get("root_cause_correct")]
            if successful:
                all_runs[name] = successful
    return all_runs


def plot_accuracy(models: list, output_dir: Path):
    names = [m["display_name"] for m in models]
    rates = [m["accuracy"] for m in models]
    colors = [COLORS.get(n, "#636e72") for n in names]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(names, rates, color=colors, edgecolor="black", linewidth=0.5)
    ax.set_ylabel("Root-Cause Accuracy (%)")
    ax.set_title("Root-Cause Identification Accuracy by Model")
    ax.set_ylim(0, 100)
    ax.axhline(y=50, color="gray", linestyle="--", alpha=0.3)

    for bar, rate in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                f"{rate:.1f}%", ha="center", va="bottom", fontsize=10, fontweight="bold")

    plt.tight_layout()
    plt.savefig(output_dir / "chart_success_rate.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: chart_success_rate.png")


def plot_median_cost(models: list, output_dir: Path):
    names = [m["display_name"] for m in models]
    costs = [m["cost_usd"]["median"] for m in models]
    colors = [COLORS.get(n, "#636e72") for n in names]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(names, costs, color=colors, edgecolor="black", linewidth=0.5)
    ax.set_ylabel("Cost per Investigation (USD)")
    ax.set_title("Median Cost per Successful Investigation by Model")

    for bar, cost in zip(bars, costs):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.0005,
                f"${cost:.4f}", ha="center", va="bottom", fontsize=10, fontweight="bold")

    plt.tight_layout()
    plt.savefig(output_dir / "chart_median_cost.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: chart_median_cost.png")


def plot_median_duration(models: list, output_dir: Path):
    available = [m for m in models if m.get("duration_available", True)]
    na_models = [m for m in models if not m.get("duration_available", True)]

    names = [m["display_name"] for m in available]
    durations = [m["duration_ms"]["median"] / 1000 for m in available]
    colors = [COLORS.get(n, "#636e72") for n in names]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(names, durations, color=colors, edgecolor="black", linewidth=0.5)
    ax.set_ylabel("Duration (seconds)")
    ax.set_title("Median Investigation Duration by Model (Successful Runs)")

    for bar, dur in zip(bars, durations):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f"{dur:.1f}s", ha="center", va="bottom", fontsize=10, fontweight="bold")

    if na_models:
        na_text = ", ".join(m["display_name"] for m in na_models)
        ax.annotate(f"N/A (rate-limited): {na_text}",
                    xy=(0.5, -0.12), xycoords="axes fraction",
                    ha="center", fontsize=9, fontstyle="italic", color="gray")

    plt.tight_layout()
    plt.savefig(output_dir / "chart_median_duration.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: chart_median_duration.png")


def plot_token_boxplot(all_runs: dict, output_dir: Path):
    fig, ax = plt.subplots(figsize=(8, 5))

    data = []
    labels = []
    colors_list = []
    for name, runs in all_runs.items():
        tokens = [r["trace_summary"]["total_tokens"] for r in runs
                  if r.get("trace_summary", {}).get("total_tokens")]
        if tokens:
            data.append(tokens)
            labels.append(name)
            colors_list.append(COLORS.get(name, "#636e72"))

    bp = ax.boxplot(data, tick_labels=labels, patch_artist=True, notch=True)
    for patch, color in zip(bp["boxes"], colors_list):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.set_ylabel("Total Tokens")
    ax.set_title("Token Usage Distribution by Model (Successful Runs)")
    plt.tight_layout()
    plt.savefig(output_dir / "chart_token_distribution.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: chart_token_distribution.png")


def plot_combined_comparison(models: list, output_dir: Path):
    """Single figure with 3 subplots for the thesis."""
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))

    names = [m["display_name"] for m in models]
    colors = [COLORS.get(n, "#636e72") for n in names]

    # Accuracy
    ax = axes[0]
    rates = [m["accuracy"] for m in models]
    bars = ax.bar(names, rates, color=colors, edgecolor="black", linewidth=0.5)
    ax.set_ylabel("Accuracy (%)")
    ax.set_title("Root-Cause Accuracy")
    ax.set_ylim(0, 100)
    for bar, rate in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{rate:.0f}%", ha="center", va="bottom", fontsize=9)
    ax.tick_params(axis='x', rotation=15)

    # Cost (successful only)
    ax = axes[1]
    costs = [m["cost_usd"]["median"] for m in models]
    bars = ax.bar(names, costs, color=colors, edgecolor="black", linewidth=0.5)
    ax.set_ylabel("Cost (USD)")
    ax.set_title("Median Cost / Investigation")
    for bar, cost in zip(bars, costs):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.0003,
                f"${cost:.4f}", ha="center", va="bottom", fontsize=9)
    ax.tick_params(axis='x', rotation=15)

    # Duration (only models with reliable timing)
    ax = axes[2]
    dur_values = []
    dur_names = []
    dur_colors = []
    for m in models:
        if m.get("duration_available", True):
            dur_values.append(m["duration_ms"]["median"] / 1000)
            dur_names.append(m["display_name"])
            dur_colors.append(COLORS.get(m["display_name"], "#636e72"))

    bars = ax.bar(dur_names, dur_values, color=dur_colors, edgecolor="black", linewidth=0.5)
    ax.set_ylabel("Duration (s)")
    ax.set_title("Median Duration")
    for bar, dur in zip(bars, dur_values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                f"{dur:.0f}s", ha="center", va="bottom", fontsize=9)
    ax.tick_params(axis='x', rotation=15)

    na_models = [m["display_name"] for m in models if not m.get("duration_available", True)]
    if na_models:
        ax.annotate(f"N/A: {', '.join(na_models)}",
                    xy=(0.5, -0.18), xycoords="axes fraction",
                    ha="center", fontsize=8, fontstyle="italic", color="gray")

    plt.tight_layout()
    plt.savefig(output_dir / "chart_model_comparison.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: chart_model_comparison.png")


def generate_pgfplots_cost(models: list, output_dir: Path):
    """Generate PGFPlots LaTeX code for the cost comparison bar chart."""
    lines = [
        r"\begin{figure}[ht]",
        r"\centering",
        r"\begin{tikzpicture}",
        r"\begin{axis}[",
        r"    ybar,",
        r"    bar width=18pt,",
        r"    ylabel={Cost per investigation (USD)},",
        r"    symbolic x coords={" + ",".join(m["display_name"] for m in models) + r"},",
        r"    xtick=data,",
        r"    x tick label style={rotate=15, anchor=east},",
        r"    nodes near coords,",
        r"    nodes near coords align={vertical},",
        r"    every node near coord/.append style={font=\scriptsize},",
        r"    ymin=0,",
        r"    enlarge x limits=0.2,",
        r"    width=0.85\textwidth,",
        r"    height=6cm,",
        r"]",
        r"\addplot coordinates {",
    ]
    for m in models:
        lines.append(f"    ({m['display_name']}, {m['cost_usd']['median']:.5f})")
    lines.extend([
        r"};",
        r"\end{axis}",
        r"\end{tikzpicture}",
        r"\caption{Median cost per successful investigation by LLM model.}",
        r"\label{fig:cost-comparison}",
        r"\end{figure}",
    ])
    pgf_path = output_dir / "pgfplots_cost_comparison.tex"
    with open(pgf_path, "w") as f:
        f.write("\n".join(lines))
    print(f"  Saved: pgfplots_cost_comparison.tex")


def main():
    parser = argparse.ArgumentParser(description="Generate charts from multi-model experiment data")
    parser.add_argument("--summary", default="../../thesis/Resources/multi_model_summary.json",
                        help="Path to aggregated summary JSON")
    parser.add_argument("--base-dir", default="../../thesis/Resources",
                        help="Base directory with runs_* subdirs (for box plots)")
    parser.add_argument("--output-dir", default="../../thesis/Images",
                        help="Output directory for PNG charts")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = load_summary(args.summary)
    models = summary["models"]

    if not models:
        print("No model data found in summary.")
        return

    print("Generating charts...")
    plot_accuracy(models, output_dir)
    plot_median_cost(models, output_dir)
    plot_median_duration(models, output_dir)
    plot_combined_comparison(models, output_dir)

    all_runs = load_all_runs(Path(args.base_dir))
    if all_runs:
        plot_token_boxplot(all_runs, output_dir)

    generate_pgfplots_cost(models, output_dir)

    print("\nAll charts generated successfully.")


if __name__ == "__main__":
    main()
