# SwarmDeck build log

## iter 1 — 2026-07-13T17:23:30Z
Implemented Slice 1 (Core primitives) from prd.md.

What I built:
- `swarmdeck/core.py`: `Task` dataclass, `Router` (round-robin across N simulated worker ids), `RetryPolicy` (exponential backoff, max attempts), `SimWorker` (seeded failure-rate + latency jitter simulation), `Observer` (JSONL logger writing `ts, task_id, state, attempt, worker_id, latency_ms, mode` per line), and `run_task_sequential` which drives one task through queued→running→(failed→retrying)*→done, with `run_mode="control"` (routes + retries via RetryPolicy) vs `run_mode="naive"` (always worker 0, single attempt, no recovery) sharing the identical seeded RNG so the two modes are directly comparable.
- `swarmdeck/cli.py`: sequential (no threading yet, per slice 1 scope) demo CLI — runs the naive batch then the control batch with the same seed/failure-rate, writes `events.jsonl`, prints a summary table of success/total/success_rate per mode.

Test result: PASS
```
$ python3 -m swarmdeck.cli --tasks 50 --failure-rate 0.3 --seed 42
mode      success   total     success_rate
naive     31        50        62.00%
control   49        50        98.00%

events written to events.jsonl
```
Verified via test-plan steps 2-4:
- exit code 0 confirmed (`echo $?` → 0)
- `python3 -c "import json; [json.loads(l) for l in open('events.jsonl')]"` — all 372 lines parse as valid JSON, all contain `task_id, state, attempt, worker_id, latency_ms`.
- control-mode events with `attempt > 1`: 54 (retries fired); naive-mode events with `attempt > 1`: 0 (confirms naive never retries) — matches success criteria bullet 3 exactly.
- Only stdlib imports used across both files (`argparse, random, json, time, dataclasses`) — zero third-party deps, no network calls.

STATUS: slice 1 done
TG: Built the core retry/routing engine for SwarmDeck and ran it on 50 simulated tasks with a 30% failure rate. Without the control plane only 62% of tasks succeeded (no retries); with the control plane routing and retrying failures, 98% succeeded — same seed, same failures, just smarter handling. Next: add real concurrency (threading) with a worker pool and a "naive mode" toggle so both runs happen live side-by-side, per slice 2.

## iter 2 — 2026-07-13T17:41:00Z
Implemented Slice 2 (Concurrency + fault injection) from prd.md.

What I built:
- `swarmdeck/core.py`: added `run_batch_concurrent(tasks, workers, router, retry_policy, observer, run_mode, n_workers)` — a real stdlib `threading` + `queue.Queue` worker pool. In `control` mode, N worker threads pull tasks from one shared queue; a failed task is requeued and picked up by whichever worker becomes free next (genuine dynamic routing across the pool, not a fixed schedule), retried per `RetryPolicy` until attempts are exhausted. In `naive` mode, a single thread pinned to worker 0 processes tasks with one attempt each, no requeue, no recovery — same degenerate-pool shape but with the control plane switched off. Termination uses the standard `queue.Queue.join()` + sentinel-`STOP` pattern so retries requeued mid-run are correctly waited on before shutdown.
- Made `Observer` thread-safe: added a `threading.Lock` around the file write+flush so concurrent worker threads logging simultaneously never interleave/corrupt JSONL lines.
- `swarmdeck/cli.py`: rewired to call `run_batch_concurrent` instead of the slice-1 sequential loop, opens one shared `Observer` for both runs, and now also times and prints wall-clock elapsed seconds per mode (demonstrates the concurrency win, not just the success-rate win).

Test result: PASS
```
$ time python3 -m swarmdeck.cli --tasks 50 --failure-rate 0.3 --seed 42
mode      success   total     success_rate  elapsed_s
naive     31        50        62.00%        1.82
control   49        50        98.00%        0.51

events written to events.jsonl
real 0m2.37s
EXIT: 0
```
Verified via test-plan steps 2-4, extended for concurrency:
- exit code 0.
- `events.jsonl`: 363 lines, all valid JSON, all contain `task_id, state, attempt, worker_id, latency_ms`.
- control-mode events with `attempt > 1`: 46 (retries fired, requeued across the pool); naive-mode events with `attempt > 1`: 0.
- distinct `worker_id`s touched: naive = `{0}` only (no routing, as required); control = `{0,1,2,3,4}` (all 5 threads/workers actually used).
- Re-ran 3x with the same seed/out-file target: identical success counts, identical event-line counts each time — confirms the thread pool is reproducible, not flaky, despite real concurrency.
- Control mode (0.51s) finished ~3.6x faster than naive (1.82s) on the same 50 tasks — real parallel speedup from the thread pool, not just a better success rate.
- `pip list` diff before/after: empty (0 new packages). Only stdlib imports across both files (`json, queue, random, threading, time, dataclasses, argparse`) — zero third-party deps, no network calls.

STATUS: slice 2 done
TG: Swapped SwarmDeck's engine to a real multi-threaded worker pool: 5 workers running concurrently instead of one-at-a-time. Same 50-task test as before still shows 98% success with the control plane vs 62% without it, but now the control-plane run also finishes 3.6x faster (0.5s vs 1.8s) because failed tasks get picked up by whichever worker frees up next. Next: build the live terminal dashboard (the actual wow-shot visual) so this comparison is watchable in real time, not just a table.
