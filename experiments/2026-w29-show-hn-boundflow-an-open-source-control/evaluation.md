# Evaluation — SwarmDeck

## Verdict: partial

## Depth: shallow — only 2 of 4 planned slices exist, the entire "wow shot" (live dashboard, branded report.html) and the N-run benchmark harness are missing, so the one demonstrable artifact is a synthetic toy comparison with no visual/reusable/comparison deliverable behind it.

## Criteria
- [✗] `python3 swarmdeck/run_benchmark.py --tasks 50 --failure-rate 0.3 --runs 1` exits 0 and prints a naive-vs-control-plane summary table — evidence: file does not exist. `python3 run_benchmark.py ...` → `python3: can't open file '.../swarmdeck/run_benchmark.py': [Errno 2] No such file or directory`, exit code 2.
- [x] JSONL file produced with ≥1 line per task-state-transition, every line parses, contains required fields — evidence: ran `python3 -m swarmdeck.cli --tasks 50 --failure-rate 0.3 --seed 42` (the only CLI that actually exists), produced `events.jsonl` with 363 lines; `json.loads` on all lines succeeds; all lines contain `task_id, state, attempt, worker_id, latency_ms`.
- [x] At failure_rate>0, ≥1 event with attempt>1 in control mode, zero in naive mode — evidence: counted programmatically — control-mode `attempt>1` events: 46; naive-mode `attempt>1` events: 0.
- [x] Control-plane success rate measurably higher than naive on same seed — evidence: stdout table — naive 31/50 (62.00%), control 49/50 (98.00%), delta +36pp, same seed (42).
- [✗] `report.html` generated with brand hex codes, fonts, stat card — evidence: no `report.html` file exists anywhere in the repo (`find . -name '*.html'` returns nothing). Slice 3 was never built.
- [✗] Live terminal dashboard runs ≥10s, updates node colors ≥3x per task, verifiable via `script`+ANSI grep — evidence: `dashboard.py` does not exist (`python3 dashboard.py` → `No such file or directory`). No dashboard, no ANSI grid, no curses/redraw code anywhere in `swarmdeck/`.
- [✗] `run_benchmark.py --runs 20` reports min/max/mean success-rate delta across runs — evidence: same missing file as above; slice 4 (benchmark hardening) was never built.
- [x] Zero third-party pip installs, zero network calls — evidence: `grep -n "^import\|^from" swarmdeck/*.py` shows only `argparse, random, time, json, queue, threading, dataclasses` across both files; `pip list` before/after running the CLI is identical (diff exit 0). No `requests`/`socket`/`urllib` usage anywhere.

Score: 4/8 criteria met. The 4 that pass are all slice-1/2 territory (core retry/routing engine, JSONL logging, stdlib-only). The 4 that fail are exactly slices 3 and 4 — the parts of the PRD explicitly called "the wow shot" and "the quantified number," i.e. the parts meant to make this shareable/credible rather than just a private unit test.

## What broke / limitations
- **The PRD's own "Run instructions" don't work.** Two of the four commands listed (`dashboard.py`, `run_benchmark.py`) reference files that were never created. Anyone following prd.md verbatim hits a hard `FileNotFoundError` on step 2 of 4.
- **No visual artifact exists.** The entire premise of the experiment ("wow shot," "LinkedIn screenshot," branded stat card) has zero implementation — no HTML, no CSS, no dashboard code, no color grid. The build-log's own iter-2 entry ends with "Next: build the live terminal dashboard" — it was never started.
- **No confidence interval / multi-run number.** The only success-rate delta (62%→98%) comes from a single seed (42) on a single run. The PRD itself flags this exact risk ("the headline number isn't a single lucky seed") — and that risk was never mitigated. One seed's number is not a benchmark.
- **build-log.md overstates status vagueness**: it marks "slice 2 done" and stops — there's no iter 3/4 entry, no explanation of why slices 3-4 were dropped, no invocation of the PRD's own kill criteria (e.g., "if rendering proves flaky, drop to a simpler wow shot" — that fallback path was never even attempted, just silently skipped).
- **Simulation-only, acknowledged.** This is explicitly out-of-scope-by-design (no real LLM calls, no real BoundFlow repo integration) — that's not a flaw relative to the PRD, but it does mean nothing here demonstrates the tool working against real agent failures, only a `random.Random()` coin flip standing in for "an agent task."
- **Would break in production**: `RetryPolicy`/`Router`/`Observer` here are toy-sized (in-process threads, single JSONL file, no backpressure, no persistence beyond append-only file, no circuit breaker, no distributed coordination) — fine per the PRD's explicit "out of scope," but means literally nothing here is deployable; it's a proof-of-concept for one afternoon's benchmark table, not infrastructure.
- **Thread-timing based demo is inherently a little flaky**: elapsed-time numbers (0.51s vs 1.82s) depend on OS scheduler noise across only 5 threads; no repeated-run statistics were captured for the timing claim (only for success-rate, informally, per build-log "re-ran 3x").

## Founder translation
If you were sold "SwarmDeck fixes flaky AI-agent pipelines and proves it with a live dashboard," what you'd actually get today is a command-line table showing that retrying failed simulated tasks with worker rotation turns a 62%-success run into a 98%-success run — useful evidence that basic retry/routing logic works, but you can't show it to anyone (no dashboard, no report, no branded screenshot exists yet), and you can't cite "98%" with confidence because it's from one lucky random seed, not a repeated benchmark. In hours: this is roughly half of a planned 2-day build — the boring backend half is real and works, the presentable half (what you'd actually put in front of a customer or on LinkedIn) doesn't exist yet, so budget another day before this is demo-ready.

## Numbers
- Naive mode: 31/50 tasks succeeded (62.00%) with no retries, on seed 42, 30% simulated failure rate.
- Control-plane mode: 49/50 tasks succeeded (98.00%) with 46 retry events, same seed/failure rate — a +36 percentage-point delta from a single run only.
- 2 of 4 PRD slices shipped, 4 of 8 success criteria met — the wow-shot dashboard, the branded report.html, and the 20-run confidence-interval benchmark (the parts meant to make this shareable) are all missing.
