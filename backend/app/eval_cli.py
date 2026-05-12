"""Run the eval harness from the command line.

    python -m app.eval_cli
    python -m app.eval_cli --judge anthropic/claude-opus-4.1 --candidate anthropic/claude-sonnet-4.5
    python -m app.eval_cli --json > runs/eval-$(date +%Y%m%d-%H%M).json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

from app.services.eval_service import AXES, regenerate_missing_baselines, run_eval


def _color(value: float) -> str:
    """Green ≥1, yellow 0.8-1, red <0.8 — for the % of baseline number."""
    if value >= 1.0:
        return "\033[32m"
    if value >= 0.8:
        return "\033[33m"
    return "\033[31m"


RESET = "\033[0m"
BOLD = "\033[1m"


def _print_report(report) -> None:
    pct = report.percent_of_baseline
    print(f"\n{BOLD}=== EVAL REPORT ==={RESET}")
    print(f"Candidate model: {report.candidate_model}")
    print(f"Judge model:     {report.judge_model}")
    print(f"Cases:           {len(report.results)}")
    print()
    print(f"{BOLD}OVERALL:{RESET}")
    print(f"  Baseline mean: {report.baseline_mean:.2f} / 10")
    print(f"  Our mean:      {report.candidate_mean:.2f} / 10")
    print(f"  Ratio:         {_color(pct)}{pct * 100:.1f}% of baseline{RESET}")
    print()

    print(f"{BOLD}PER-AXIS:{RESET}")
    per_axis = report.per_axis_means()
    for axis in AXES:
        if axis not in per_axis:
            continue
        base, cand = per_axis[axis]
        delta = cand - base
        sign = "+" if delta >= 0 else ""
        color = "\033[32m" if delta > 0 else ("\033[31m" if delta < 0 else "")
        print(f"  {axis:32}  baseline={base:5.2f}  ours={cand:5.2f}  {color}{sign}{delta:+.2f}{RESET}")
    print()

    for r in report.results:
        print(f"{BOLD}--- case: {r.case_id} ---{RESET}")
        print(f"  Baseline mean: {r.baseline_mean:.2f}  |  Our mean: {r.candidate_mean:.2f}  |  {_color(r.percent_of_baseline)}{r.percent_of_baseline * 100:.1f}%{RESET}")
        for axis, score in r.axes.items():
            delta = score.delta
            sign = "+" if delta >= 0 else ""
            color = "\033[32m" if delta > 0 else ("\033[31m" if delta < 0 else "")
            print(f"    {axis:32}  base={score.baseline:>4.1f}  ours={score.candidate:>4.1f}  {color}{sign}{delta:+.1f}{RESET}")
        print(f"  Judge: {r.judge_reasoning}")
        print()


def _to_json(report) -> dict:
    return {
        "candidate_model": report.candidate_model,
        "judge_model": report.judge_model,
        "overall": {
            "baseline_mean": round(report.baseline_mean, 3),
            "candidate_mean": round(report.candidate_mean, 3),
            "percent_of_baseline": round(report.percent_of_baseline, 4),
        },
        "per_axis": {
            axis: {"baseline": round(b, 3), "candidate": round(c, 3), "delta": round(c - b, 3)}
            for axis, (b, c) in report.per_axis_means().items()
        },
        "cases": [
            {
                "id": r.case_id,
                "baseline_mean": round(r.baseline_mean, 3),
                "candidate_mean": round(r.candidate_mean, 3),
                "percent_of_baseline": round(r.percent_of_baseline, 4),
                "axes": {axis: asdict(score) for axis, score in r.axes.items()},
                "judge_reasoning": r.judge_reasoning,
                "candidate_subject": r.candidate_subject,
                "candidate_body": r.candidate_body,
                "baseline_subject": r.baseline_subject,
                "baseline_body": r.baseline_body,
            }
            for r in report.results
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the 5-Level personalizer eval.")
    parser.add_argument("--candidate", default=None, help="Candidate model slug for OpenRouter")
    parser.add_argument("--judge", default=None, help="Judge model slug for OpenRouter")
    parser.add_argument("--brand", default="lakeb2b")
    parser.add_argument("--golden", default=None, help="Path to golden_emails.json")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    parser.add_argument("--regen", action="store_true", help="Regenerate missing baselines via Chief's exact prompts before evaluating")
    parser.add_argument("--regen-force", action="store_true", help="Regenerate ALL baselines (overwrite existing)")
    args = parser.parse_args()

    golden_path = Path(args.golden) if args.golden else None

    if args.regen or args.regen_force:
        n = asyncio.run(regenerate_missing_baselines(
            candidate_model=args.candidate,
            path=golden_path,
            force=args.regen_force,
        ))
        sys.stderr.write(f"[regen] generated {n} baseline(s) via chief_replica\n")

    report = asyncio.run(run_eval(
        candidate_model=args.candidate,
        judge_model=args.judge,
        brand_slug=args.brand,
        golden_path=golden_path,
    ))

    if args.json:
        json.dump(_to_json(report), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        _print_report(report)

    return 0 if report.percent_of_baseline >= 0.78 else 1


if __name__ == "__main__":
    sys.exit(main())
