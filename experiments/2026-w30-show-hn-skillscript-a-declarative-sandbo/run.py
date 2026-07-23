#!/usr/bin/env python3
"""Skillcage CLI: parse a .sky file, execute its DAG, print the log,
write the final step's result as JSON."""
import json
import sys

from dsl import load_sky, SkyError
from executor import run_sky, run_sky_parallel, StepFailure


def main(argv):
    args = [a for a in argv[1:] if a != "--parallel"]
    parallel = len(args) != len(argv[1:])
    if len(args) != 1:
        print("usage: python3 run.py [--parallel] <path/to/file.sky>", file=sys.stderr)
        return 2

    sky_path = args[0]
    try:
        sky = load_sky(sky_path)
    except (SkyError, FileNotFoundError) as e:
        print(f"[PARSE ERROR] {e}", file=sys.stderr)
        return 1

    mode = "parallel (thread pool per DAG wave)" if parallel else "sequential"
    print(f"[RUN] loading {sky_path} ({len(sky['steps'])} steps, mode={mode})")
    try:
        run = run_sky_parallel if parallel else run_sky
        results, final_step, order = run(sky)
    except StepFailure as e:
        print(f"[BLOCKED] {e}", file=sys.stderr)
        return 1

    final_result = results[final_step]
    out_path = sky["output"]
    with open(out_path, "w") as f:
        json.dump(final_result, f, indent=2)
        f.write("\n")

    if isinstance(final_result, dict) and final_result.get("status") in ("blocked", "partial"):
        blocked, total, escaped = final_result["blocked"], final_result["total"], final_result["escaped"]
        print(f"[SCOREBOARD] {blocked}/{total} attack vectors blocked, {escaped} escapes -> {out_path}")
        if escaped:
            print(f"[ESCAPE] {escaped} attack(s) were NOT blocked by the sandbox", file=sys.stderr)
            return 1
        return 0

    print(f"[DONE] {len(order)} steps executed, final='{final_step}' -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
