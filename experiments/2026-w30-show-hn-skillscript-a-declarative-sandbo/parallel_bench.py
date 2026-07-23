#!/usr/bin/env python3
"""Depth extension 2 benchmark: proves run_sky_parallel does *real* concurrent
execution, not just a DAG shape that could theoretically run in parallel.

examples/parallel_fanout.sky has 5 independent slow_step branches (each a
genuine time.sleep(0.06s), no I/O) feeding into one aggregate+report. Run
sequentially, 5 branches must take >= 5*60ms wall-clock. Run through the
thread-pool executor, all 5 sit in the same DAG "wave" (dag.topological_waves)
and should overlap almost entirely, so wall-clock should land close to a
*single* branch's delay instead of the sum.

Also re-checks correctness: the parallel path must produce the exact same
aggregate/report result as the sequential path (same total, same count, same
item order) -- concurrency must not change the answer, only the wall time.

Writes parallel_report.json/.md (same PASS/FAIL convention as benchmark.py)
and prints a [PARALLEL] summary. Exit 0 iff results match AND measured
speedup >= 2.0x (5 branches at equal delay should give ~5x; 2x is a
conservative floor that tolerates a slow/loaded CI machine).
"""
import json
import os
import sys
import time

from dsl import load_sky
from executor import run_sky, run_sky_parallel

FANOUT_SKY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples", "parallel_fanout.sky")
MIN_SPEEDUP = 2.0


def _timed(run_fn, sky):
    trace = []
    start = time.perf_counter()
    results, final_step, order = run_fn(sky, log=lambda *a, **kw: None, trace=trace)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return results, final_step, order, trace, elapsed_ms


def build_report():
    sky_seq = load_sky(FANOUT_SKY)
    sky_par = load_sky(FANOUT_SKY)

    seq_results, seq_final, seq_order, seq_trace, seq_ms = _timed(run_sky, sky_seq)
    par_results, par_final, par_order, par_trace, par_ms = _timed(run_sky_parallel, sky_par)

    seq_report = seq_results[seq_final]
    par_report = par_results[par_final]
    same_total = seq_report.get("total") == par_report.get("total")
    same_count = seq_report.get("count") == par_report.get("count")
    same_names = ([it["name"] for it in seq_report.get("items", [])]
                   == [it["name"] for it in par_report.get("items", [])])
    correctness_ok = same_total and same_count and same_names

    speedup = seq_ms / par_ms if par_ms > 0 else float("inf")
    waves = [ev for ev in par_trace if ev["event"] == "wave_done"]

    return {
        "sequential": {"elapsed_ms": seq_ms, "order": seq_order, "result": seq_report},
        "parallel": {"elapsed_ms": par_ms, "order": par_order, "result": par_report, "waves": waves},
        "correctness": {
            "same_total": same_total, "same_count": same_count, "same_item_order": same_names,
            "ok": correctness_ok,
        },
        "speedup": speedup,
        "min_speedup_required": MIN_SPEEDUP,
        "pass": correctness_ok and speedup >= MIN_SPEEDUP,
    }


def write_json(report, path="parallel_report.json"):
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
        f.write("\n")


def write_markdown(report, path="parallel_report.md"):
    seq, par, corr = report["sequential"], report["parallel"], report["correctness"]
    lines = [
        "# Skillcage Parallel Fan-out Benchmark",
        "",
        f"**Sequential wall-clock:** {seq['elapsed_ms']:.1f}ms (5 independent slow_step branches, one at a time)",
        f"**Parallel wall-clock:** {par['elapsed_ms']:.1f}ms (same 5 branches, one DAG wave, thread pool)",
        f"**Speedup:** {report['speedup']:.2f}x",
        f"**Correctness:** identical total/count/item-order between sequential and parallel runs: "
        f"{'yes' if corr['ok'] else 'NO -- MISMATCH'}",
        f"**Verdict:** {'PASS' if report['pass'] else 'FAIL'}",
        "",
        "## Wave detail (parallel run)",
        "",
        "| wave | steps | wall-clock |",
        "|------|-------|------------|",
    ]
    for w in par["waves"]:
        lines.append(f"| {w['wave']} | {w['size']} | {w['elapsed_ms']:.1f}ms |")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    report = build_report()
    write_json(report)
    write_markdown(report)
    print(f"[PARALLEL] sequential={report['sequential']['elapsed_ms']:.1f}ms "
          f"parallel={report['parallel']['elapsed_ms']:.1f}ms speedup={report['speedup']:.2f}x")
    print(f"[PARALLEL] correctness: {'ok' if report['correctness']['ok'] else 'MISMATCH'}")
    print(f"[PARALLEL] wrote parallel_report.json, parallel_report.md -- "
          f"verdict={'PASS' if report['pass'] else 'FAIL'}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
