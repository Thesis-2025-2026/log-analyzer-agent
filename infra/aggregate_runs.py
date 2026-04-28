#!/usr/bin/env python3
"""
Aggregates per-run JSON data from the experiment into summary statistics.
Output: thesis/Resources/experiment_summary.json
"""

import json
import os
import statistics
import sys
from pathlib import Path

RUNS_DIR = Path(__file__).resolve().parent.parent.parent / "thesis" / "Resources" / "runs"
OUTPUT_PATH = RUNS_DIR.parent / "experiment_summary.json"


def load_runs():
    runs = []
    for p in sorted(RUNS_DIR.glob("run_*.json")):
        with open(p) as f:
            runs.append(json.load(f))
    return runs


def compute_stats(values):
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "mean": round(statistics.mean(values), 1),
        "median": round(statistics.median(values), 1),
        "min": min(values),
        "max": max(values),
        "stdev": round(statistics.stdev(values), 1) if len(values) > 1 else 0,
    }


def main():
    runs = load_runs()
    if not runs:
        print(f"No run files found in {RUNS_DIR}", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(runs)} runs from {RUNS_DIR}")

    durations = []
    entry_counts = []
    tool_counts = []
    agent_counts = []
    http_counts = []
    content_lengths = []
    services_queried = []
    root_cause_correct = []

    per_run_summary = []

    for run in runs:
        ts = run["trace_summary"]
        rpt = run["report"]

        dur = ts.get("total_duration_ms")
        if dur:
            durations.append(dur)

        entry_counts.append(ts["total_entries"])
        tool_counts.append(ts["tool_call_count"])
        agent_counts.append(ts["agent_call_count"])
        http_counts.append(ts["http_call_count"])
        content_lengths.append(rpt["content_length"])
        services_queried.append(ts["services_involved"])
        root_cause_correct.append(rpt["root_cause_correct"])

        per_run_summary.append({
            "run": run["run_number"],
            "duration_ms": dur,
            "duration_s": round(dur / 1000, 1) if dur else None,
            "trace_entries": ts["total_entries"],
            "tool_calls": ts["tool_call_count"],
            "agent_calls": ts["agent_call_count"],
            "http_calls": ts["http_call_count"],
            "services": ts["services_involved"],
            "num_services_queried": len(ts["services_involved"]),
            "report_length_chars": rpt["content_length"],
            "root_cause_correct": rpt["root_cause_correct"],
            "report_title": rpt.get("title", ""),
        })

    # Cross-service pattern analysis
    patterns = {}
    for svcs in services_queried:
        key = "+".join(sorted(svcs))
        patterns[key] = patterns.get(key, 0) + 1

    # Runs that queried specific services
    queried_deployments = sum(1 for s in services_queried if "deployments-service" in s)
    queried_idp = sum(1 for s in services_queried if "idp-service" in s)
    queried_both = sum(1 for s in services_queried if "deployments-service" in s and "idp-service" in s)

    summary = {
        "experiment_metadata": {
            "total_runs": len(runs),
            "model": "gpt-4o-mini",
            "scenario": "OAuth deployment cascade (auth_login flow)",
            "date": runs[0]["start_time"][:10] if runs else None,
        },
        "timing": compute_stats(durations),
        "trace_entries": compute_stats(entry_counts),
        "tool_calls": compute_stats(tool_counts),
        "agent_calls": compute_stats(agent_counts),
        "http_calls": compute_stats(http_counts),
        "report_length_chars": compute_stats(content_lengths),
        "root_cause_identification": {
            "correct": sum(root_cause_correct),
            "total": len(root_cause_correct),
            "rate": round(sum(root_cause_correct) / len(root_cause_correct) * 100, 1),
        },
        "cross_service_patterns": {
            "distribution": patterns,
            "queried_deployments": queried_deployments,
            "queried_idp": queried_idp,
            "queried_both_deployments_and_idp": queried_both,
            "auth_only": len(runs) - queried_deployments - queried_idp + queried_both,
        },
        "per_run": per_run_summary,
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nSaved summary to {OUTPUT_PATH}")
    print(f"\n{'='*60}")
    print(f" EXPERIMENT SUMMARY (N={len(runs)})")
    print(f"{'='*60}")
    print(f"\nTiming (ms):  mean={summary['timing']['mean']}, "
          f"median={summary['timing']['median']}, "
          f"min={summary['timing']['min']}, max={summary['timing']['max']}, "
          f"stdev={summary['timing']['stdev']}")
    print(f"Timing (s):   mean={summary['timing']['mean']/1000:.1f}, "
          f"median={summary['timing']['median']/1000:.1f}")
    print(f"\nTool calls:   mean={summary['tool_calls']['mean']}, "
          f"min={summary['tool_calls']['min']}, max={summary['tool_calls']['max']}")
    print(f"Trace entries: mean={summary['trace_entries']['mean']}, "
          f"min={summary['trace_entries']['min']}, max={summary['trace_entries']['max']}")
    print(f"\nRoot cause correct: {summary['root_cause_identification']['correct']}/"
          f"{summary['root_cause_identification']['total']} "
          f"({summary['root_cause_identification']['rate']}%)")
    print(f"\nCross-service patterns:")
    for pattern, count in sorted(patterns.items()):
        print(f"  {pattern}: {count} runs")
    print(f"\nPer-run:")
    for r in per_run_summary:
        print(f"  Run {r['run']:2d}: {r['duration_s']:5.1f}s | "
              f"{r['tool_calls']:2d} tools | {r['num_services_queried']} svcs | "
              f"correct={r['root_cause_correct']}")


if __name__ == "__main__":
    main()
