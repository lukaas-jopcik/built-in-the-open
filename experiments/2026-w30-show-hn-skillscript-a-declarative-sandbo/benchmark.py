#!/usr/bin/env python3
"""Slice 4 benchmark + hardening harness.

Three checks, each answering a specific PRD success criterion:
  1. Attack corpus block-rate: every .sky in examples/attacks/ (>=20 distinct
     sandbox-escape techniques) must come back __blocked__ from run_sky.
  2. False-positive check: the 5 legitimate .sky examples must NOT be
     blocked -- a sandbox that blocks real work isn't shippable either.
  3. Overhead: safe_eval (AST-whitelist) vs raw eval() over 100 iterations
     on the same safe expression, to put a number on the "safety tax."

Writes benchmark.json (machine-readable) and benchmark.md (human-readable,
LinkedIn-postable) and prints a summary. Exit 0 iff block-rate >= 90% and
false-positive count == 0 (mirrors run.py's exit-code convention).
"""
import glob
import json
import os
import sys
import time

from dsl import load_sky, SkyError
from executor import run_sky, StepFailure
from safe_eval import safe_eval

ATTACKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples", "attacks")
LEGIT_FILES = [
    "examples/report.sky",
    "examples/legit_single_fetch.sky",
    "examples/legit_evaluate_safe.sky",
    "examples/legit_filter_chain.sky",
    "examples/legit_transform_identity.sky",
]
OVERHEAD_EXPR = "value > 5 and value < 100"
OVERHEAD_NAMES = {"value": 10}
OVERHEAD_ITERATIONS = 100


def run_attack_corpus():
    """Run every .sky in examples/attacks/ and record whether it was blocked."""
    paths = sorted(glob.glob(os.path.join(ATTACKS_DIR, "*.sky")))
    results = []
    for path in paths:
        sky = load_sky(path)
        technique = sky["steps"][0]["args"].get("technique", os.path.basename(path))
        try:
            step_results, final_step, _order = run_sky(sky, log=lambda *a, **kw: None)
            final = step_results[final_step]
            blocked = isinstance(final, dict) and final.get("__blocked__") is True
            reason = final.get("reason") if blocked else None
        except StepFailure as e:
            # A genuine tool error (not a sandbox trip) counts as an escape --
            # the attack broke the executor rather than being safely caged.
            blocked, reason = False, f"unhandled StepFailure: {e}"
        results.append({
            "file": os.path.basename(path),
            "technique": technique,
            "blocked": blocked,
            "reason": reason,
        })
    return results


def check_false_positives():
    """Run the legitimate examples; any __blocked__ step among them is a false positive."""
    results = []
    for rel_path in LEGIT_FILES:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path)
        sky = load_sky(path)
        step_results, _final_step, order = run_sky(sky, log=lambda *a, **kw: None)
        blocked_steps = [sid for sid in order if isinstance(step_results[sid], dict)
                         and step_results[sid].get("__blocked__") is True]
        results.append({"file": rel_path, "false_positive": bool(blocked_steps), "blocked_steps": blocked_steps})
    return results


def measure_overhead(iterations=OVERHEAD_ITERATIONS):
    """Compare safe_eval (AST-whitelist) against raw eval() on the same safe expression."""
    start = time.perf_counter()
    for _ in range(iterations):
        safe_eval(OVERHEAD_EXPR, OVERHEAD_NAMES)
    safe_total = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(iterations):
        eval(OVERHEAD_EXPR, {"__builtins__": {}}, OVERHEAD_NAMES)  # noqa: S307 -- trusted baseline expr, not attacker input
    raw_total = time.perf_counter() - start

    overhead_pct = ((safe_total - raw_total) / raw_total) * 100 if raw_total > 0 else float("inf")
    return {
        "iterations": iterations,
        "expr": OVERHEAD_EXPR,
        "safe_eval_total_ms": safe_total * 1000,
        "raw_eval_total_ms": raw_total * 1000,
        "safe_eval_avg_us": (safe_total / iterations) * 1e6,
        "raw_eval_avg_us": (raw_total / iterations) * 1e6,
        "overhead_pct": overhead_pct,
    }


def build_report():
    attacks = run_attack_corpus()
    legit = check_false_positives()
    overhead = measure_overhead()

    total = len(attacks)
    blocked = sum(1 for a in attacks if a["blocked"])
    escapes = [a for a in attacks if not a["blocked"]]
    false_positives = [l for l in legit if l["false_positive"]]

    block_rate = blocked / total if total else 0.0
    return {
        "attack_corpus": {
            "total": total,
            "blocked": blocked,
            "escaped": len(escapes),
            "block_rate": block_rate,
            "escapes": escapes,
            "techniques": attacks,
        },
        "false_positive_check": {
            "legitimate_examples": len(legit),
            "false_positives": len(false_positives),
            "details": legit,
        },
        "overhead": overhead,
        "pass": block_rate >= 0.90 and len(false_positives) == 0,
    }


def write_json(report, path="benchmark.json"):
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
        f.write("\n")


def write_markdown(report, path="benchmark.md"):
    ac = report["attack_corpus"]
    fp = report["false_positive_check"]
    ov = report["overhead"]
    lines = [
        "# Skillcage Benchmark",
        "",
        f"**Block rate:** {ac['blocked']}/{ac['total']} ({ac['block_rate']*100:.1f}%) attack techniques blocked",
        f"**False positives:** {fp['false_positives']}/{fp['legitimate_examples']} legitimate examples wrongly blocked",
        f"**Sandbox overhead:** {ov['overhead_pct']:+.1f}% vs raw `eval()` "
        f"({ov['safe_eval_avg_us']:.2f}µs vs {ov['raw_eval_avg_us']:.2f}µs per call, "
        f"{ov['iterations']} iterations)",
        f"**Verdict:** {'PASS' if report['pass'] else 'FAIL'}",
        "",
        "## Attack corpus detail",
        "",
        "| # | technique | result |",
        "|---|-----------|--------|",
    ]
    for i, a in enumerate(ac["techniques"], 1):
        status = "BLOCKED" if a["blocked"] else "**ESCAPED**"
        lines.append(f"| {i} | {a['technique']} | {status} |")
    if ac["escapes"]:
        lines += ["", "## Escapes (not blocked)", ""]
        for e in ac["escapes"]:
            lines.append(f"- `{e['file']}` ({e['technique']}): {e['reason']}")
    lines += ["", "## False-positive detail", ""]
    for l in fp["details"]:
        mark = "FALSE POSITIVE" if l["false_positive"] else "ok"
        lines.append(f"- `{l['file']}`: {mark}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    report = build_report()
    write_json(report)
    write_markdown(report)

    ac = report["attack_corpus"]
    fp = report["false_positive_check"]
    ov = report["overhead"]
    print(f"[BENCHMARK] attack corpus: {ac['blocked']}/{ac['total']} blocked "
          f"({ac['block_rate']*100:.1f}%)")
    print(f"[BENCHMARK] false positives: {fp['false_positives']}/{fp['legitimate_examples']} "
          "legitimate examples wrongly blocked")
    print(f"[BENCHMARK] overhead: safe_eval is {ov['overhead_pct']:+.1f}% vs raw eval() "
          f"({ov['safe_eval_avg_us']:.2f}µs vs {ov['raw_eval_avg_us']:.2f}µs/call, "
          f"{ov['iterations']} iters)")
    print(f"[BENCHMARK] wrote benchmark.json, benchmark.md -- verdict={'PASS' if report['pass'] else 'FAIL'}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
