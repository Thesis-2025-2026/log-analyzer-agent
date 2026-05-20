#!/usr/bin/env python3
"""
Aggregates experiment results from multiple model directories into a single
comparison JSON with per-model statistics (accuracy, token usage, duration, cost).
Stats are computed over successful runs only (root_cause_correct = true).
"""

import argparse
import json
import statistics
from pathlib import Path

MODEL_PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-5.4-mini": {"input": 0.75, "output": 4.50},
    "gpt-5.4-nano": {"input": 0.20, "output": 1.25},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}

MODEL_DISPLAY_NAMES = {
    "gpt-4o-mini": "GPT-4o-mini",
    "gpt-5.4-mini": "GPT-5.4-mini",
    "gpt-5.4-nano": "GPT-5.4-nano",
    "claude-haiku-4-5": "Claude Haiku 4.5",
}

MODEL_SELECTION = {
    "gpt-4o-mini": ("first", 50),
    "gpt-5.4-mini": ("last", 40),
    "gpt-5.4-nano": ("last", 40),
    "claude-haiku-4-5": ("last", 40),
}

DURATION_AVAILABLE = {
    "gpt-4o-mini": True,
    "gpt-5.4-mini": False,
    "gpt-5.4-nano": True,
    "claude-haiku-4-5": False,
}


def load_runs(directory: str) -> list:
    runs = []
    dir_path = Path(directory)
    if not dir_path.exists():
        return runs
    for f in sorted(dir_path.glob("run_*.json")):
        with open(f) as fh:
            runs.append(json.load(fh))
    return runs


def select_runs(runs: list, mode: str, n: int) -> list:
    if mode == "first" and n > 0:
        return runs[:n]
    elif mode == "last" and n > 0 and len(runs) > n:
        return runs[-n:]
    return runs


def compute_cost(prompt_tokens: int, completion_tokens: int, model_name: str) -> float:
    pricing = MODEL_PRICING.get(model_name, {"input": 0.15, "output": 0.60})
    return (prompt_tokens * pricing["input"] + completion_tokens * pricing["output"]) / 1_000_000


def compute_stats(values: list) -> dict:
    if not values:
        return {"mean": 0, "median": 0, "min": 0, "max": 0, "stdev": 0, "count": 0}
    return {
        "mean": round(statistics.mean(values), 2),
        "median": round(statistics.median(values), 2),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "stdev": round(statistics.stdev(values), 2) if len(values) > 1 else 0,
        "count": len(values),
    }


def analyze_model(runs: list, model_name: str) -> dict:
    total_runs = len(runs)
    if total_runs == 0:
        return {"model": model_name, "total_runs": 0}

    successes = [r for r in runs if r.get("report", {}).get("root_cause_correct", False)]
    accuracy = len(successes) / total_runs

    success_durations = [r["trace_summary"]["total_duration_ms"] for r in successes
                         if r.get("trace_summary", {}).get("total_duration_ms")]
    success_prompt = [r["trace_summary"]["prompt_tokens"] for r in successes
                      if r.get("trace_summary", {}).get("prompt_tokens")]
    success_completion = [r["trace_summary"]["completion_tokens"] for r in successes
                          if r.get("trace_summary", {}).get("completion_tokens")]
    success_total_tok = [r["trace_summary"]["total_tokens"] for r in successes
                         if r.get("trace_summary", {}).get("total_tokens")]

    success_costs = []
    for r in successes:
        ts = r.get("trace_summary", {})
        pt = ts.get("prompt_tokens", 0)
        ct = ts.get("completion_tokens", 0)
        if pt or ct:
            success_costs.append(compute_cost(pt, ct, model_name))

    all_costs = []
    for r in runs:
        ts = r.get("trace_summary", {})
        pt = ts.get("prompt_tokens", 0)
        ct = ts.get("completion_tokens", 0)
        if pt or ct:
            all_costs.append(compute_cost(pt, ct, model_name))

    duration_available = DURATION_AVAILABLE.get(model_name, True)

    return {
        "model": model_name,
        "display_name": MODEL_DISPLAY_NAMES.get(model_name, model_name),
        "total_runs": total_runs,
        "successful_runs": len(successes),
        "accuracy": round(accuracy * 100, 1),
        "duration_available": duration_available,
        "duration_ms": compute_stats(success_durations),
        "prompt_tokens": compute_stats(success_prompt),
        "completion_tokens": compute_stats(success_completion),
        "total_tokens": compute_stats(success_total_tok),
        "cost_usd": compute_stats(success_costs),
        "total_cost_usd": round(sum(all_costs), 4),
    }


def main():
    parser = argparse.ArgumentParser(description="Aggregate multi-model experiment results")
    parser.add_argument("--base-dir", default="../../thesis/Resources",
                        help="Base directory containing runs_* subdirectories")
    parser.add_argument("--output", default="../../thesis/Resources/multi_model_summary.json",
                        help="Output JSON path")
    args = parser.parse_args()

    base = Path(args.base_dir)

    model_dirs = {
        "gpt-4o-mini": base / "runs_4omini",
        "gpt-5.4-mini": base / "runs_gpt54mini",
        "gpt-5.4-nano": base / "runs_gpt54nano",
        "claude-haiku-4-5": base / "runs_haiku",
    }

    results = []
    for model_name, dir_path in model_dirs.items():
        all_runs = load_runs(str(dir_path))
        mode, n = MODEL_SELECTION.get(model_name, ("all", 0))
        runs = select_runs(all_runs, mode, n)
        if runs:
            stats = analyze_model(runs, model_name)
            results.append(stats)
            print(f"\n{'='*50}")
            print(f" {stats['display_name']}  ({mode} {n or len(runs)}, N={stats['total_runs']})")
            print(f"{'='*50}")
            print(f"  Accuracy: {stats['accuracy']}%  ({stats['successful_runs']}/{stats['total_runs']})")
            dur_label = "N/A (rate-limited)" if not stats["duration_available"] else f"{stats['duration_ms']['median']}ms"
            print(f"  Duration (successful): {dur_label}")
            print(f"  Tokens (successful): median={stats['total_tokens']['median']}")
            print(f"  Cost (successful): median=${stats['cost_usd']['median']:.4f}")
            print(f"  Total experiment cost: ${stats['total_cost_usd']:.4f}")
        else:
            print(f"\n  {model_name}: NO DATA (directory {dir_path} empty or missing)")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({"models": results}, f, indent=2)

    print(f"\n\nSummary written to: {output_path}")


if __name__ == "__main__":
    main()
