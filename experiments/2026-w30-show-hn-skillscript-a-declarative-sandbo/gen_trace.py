#!/usr/bin/env python3
"""Runs the clean report.sky and the attack malicious.sky recipes back to
back and writes a combined trace.jsonl for dashboard.html to replay.

Each line is one JSON event: {"run": "clean"|"attack", "event": "start"|
"end"|"done", ...}. dashboard.html fetches this file (serve with
`python3 -m http.server`, since `fetch()` of a local file:// path is blocked
by browsers) and animates the DAG from it.
"""
import json
import sys

from dsl import load_sky
from executor import run_sky, run_sky_parallel

RUNS = [
    ("clean", "examples/report.sky", run_sky),
    ("attack", "examples/malicious.sky", run_sky),
    ("parallel", "examples/parallel_fanout.sky", run_sky_parallel),
]


def build_events():
    events = []
    for run_name, path, run_fn in RUNS:
        sky = load_sky(path)
        trace = []
        results, final_step, order = run_fn(sky, log=lambda *a, **k: None, trace=trace)
        for ev in trace:
            ev["run"] = run_name
            events.append(ev)
        events.append({
            "run": run_name,
            "event": "done",
            "final_step": final_step,
            "result": results[final_step],
        })
    return events


def main(argv):
    out_path = argv[1] if len(argv) > 1 else "trace.jsonl"
    events = build_events()
    with open(out_path, "w") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")
    print(f"[TRACE] wrote {len(events)} events -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
