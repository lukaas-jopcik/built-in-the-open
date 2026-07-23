#!/usr/bin/env python3
"""Depth extension 4: text-based asciinema-style replay of the same three
runs dashboard.html animates (clean / attack / parallel), for viewers who
can't open an HTML file -- e.g. pasted straight into a terminal recorder:

    asciinema rec skillcage-demo.cast -c 'python3 replay.py'

stdlib only. Re-uses gen_trace.build_events() so this is the *same* trace
data the dashboard plays, not a separate simulation -- and mirrors its
pacing constants (STEP_DELAY_MS/END_DELAY_MS/RUN_GAP_MS) and scoreboard/
speedup wording verbatim so the two artifacts tell the same story.

`--fast` (or env SKILLCAGE_REPLAY_FAST=1) zeroes every sleep, for tests and
for piping through `| cat` when you just want the text, not the pacing.
"""
import os
import sys
import time

from gen_trace import build_events

PERIWINKLE = "\033[94m"
GREEN = "\033[92m"
BURGUNDY = "\033[91m"
CREAM = "\033[1;97m"
MUTED = "\033[90m"
RESET = "\033[0m"

STEP_DELAY_S = 0.550
END_DELAY_S = 0.650
WAVE_DELAY_S = 0.300
DONE_DELAY_S = 0.400
RUN_GAP_S = 1.400

RUN_LABELS = {"clean": "clean run", "attack": "attack run", "parallel": "parallel fan-out"}
RUN_COLORS = {"clean": GREEN, "attack": BURGUNDY, "parallel": PERIWINKLE}


def group_by_run(events):
    runs = []
    order = []
    by_run = {}
    for ev in events:
        name = ev["run"]
        if name not in by_run:
            by_run[name] = []
            order.append(name)
        by_run[name].append(ev)
    for name in order:
        runs.append((name, by_run[name]))
    return runs


def collect_wave_batch(events, i, kind):
    """Mirror dashboard.js's collectWaveBatch: group consecutive same-kind
    events sharing a wave number into one concurrent batch."""
    batch = [events[i]]
    wave = events[i].get("wave")
    j = i + 1
    while (
        j < len(events)
        and events[j]["event"] == kind
        and wave is not None
        and events[j].get("wave") == wave
    ):
        batch.append(events[j])
        j += 1
    return batch


def pace(seconds, scale):
    if scale:
        time.sleep(seconds * scale)


def play_run(name, events, scale, out):
    color = RUN_COLORS.get(name, PERIWINKLE)
    label = RUN_LABELS.get(name, name)
    out.write(f"\n{color}═══ {label.upper()} ═══{RESET}\n")
    i = 0
    while i < len(events):
        ev = events[i]
        kind = ev["event"]
        if kind == "start":
            batch = collect_wave_batch(events, i, "start")
            if len(batch) > 1:
                names = ", ".join(e["step_id"] for e in batch)
                out.write(f"{MUTED}  wave {ev['wave']}: running {names} concurrently{RESET}\n")
            for e in batch:
                out.write(f"{color}  → {e['step_id']}  ({e['tool']}){RESET}\n")
            pace(STEP_DELAY_S, scale)
            i += len(batch)
        elif kind == "end":
            batch = collect_wave_batch(events, i, "end")
            for e in batch:
                if e["status"] == "ok":
                    out.write(f"{GREEN}  ✓ {e['step_id']}  OK  ({e['elapsed_ms']:.3f}ms){RESET}\n")
                else:
                    out.write(
                        f"{BURGUNDY}  ✕ {e['step_id']}  BLOCKED  {e['reason']} "
                        f"({e['elapsed_ms']:.3f}ms){RESET}\n"
                    )
            pace(END_DELAY_S, scale)
            i += len(batch)
        elif kind == "wave_done":
            out.write(
                f"{MUTED}  wave {ev['wave']} wall-clock: {ev['elapsed_ms']:.1f}ms "
                f"for {ev['size']} concurrent step(s){RESET}\n"
            )
            pace(WAVE_DELAY_S, scale)
            i += 1
        elif kind == "done":
            if name == "attack":
                r = ev["result"]
                out.write(
                    f"{BURGUNDY}  [SCOREBOARD] {r['blocked']}/{r['total']} attack vectors "
                    f"blocked, {r['escaped']} escapes{RESET}\n"
                )
            elif name == "parallel":
                wave_events = [e for e in events if e["event"] == "wave_done"]
                end_events = [e for e in events if e["event"] == "end"]
                actual_ms = sum(e["elapsed_ms"] for e in wave_events)
                sequential_equiv_ms = sum(e["elapsed_ms"] for e in end_events)
                speedup = sequential_equiv_ms / actual_ms if actual_ms > 0 else 0.0
                branch_count = wave_events[0]["size"] if wave_events else len(end_events)
                out.write(
                    f"{PERIWINKLE}  [SPEEDUP] {branch_count} independent branches ran in one DAG wave\n"
                    f"  wall-clock: {actual_ms:.1f}ms concurrent vs {sequential_equiv_ms:.1f}ms one-at-a-time\n"
                    f"  {speedup:.1f}x real speedup -- measured, not simulated{RESET}\n"
                )
            else:
                r = ev["result"]
                out.write(
                    f"{GREEN}  [REPORT] status={r.get('status')} total={r.get('total')} "
                    f"count={r.get('count')}{RESET}\n"
                )
            out.write(f"{CREAM}  {label} complete.{RESET}\n")
            pace(DONE_DELAY_S, scale)
            i += 1
        else:
            i += 1


def main(argv):
    fast = "--fast" in argv or bool(os.environ.get("SKILLCAGE_REPLAY_FAST"))
    scale = 0.0 if fast else 1.0
    out = sys.stdout

    out.write(f"{CREAM}Skillcage — terminal replay (same trace dashboard.html animates){RESET}\n")
    events = build_events()
    runs = group_by_run(events)
    for idx, (name, run_events) in enumerate(runs):
        if idx > 0:
            pace(RUN_GAP_S, scale)
        play_run(name, run_events, scale, out)
    out.write(f"\n{MUTED}[REPLAY] done -- record with: asciinema rec demo.cast -c 'python3 replay.py'{RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
