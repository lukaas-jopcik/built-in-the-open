# SwarmDeck: a zero-dependency control plane for AI-agent swarms

## Goal
Build a stdlib-only Python control plane (routing, retries, observability) that turns a swarm of failure-prone simulated agent tasks into a near-100%-success run, proven with a live terminal dashboard and a branded benchmark report — no API keys, no third-party repo, no cost.

## Wow shot
**The moment:** a terminal recording (asciinema-style, via `script`/ANSI redraw) shows a 5x10 grid of 50 task nodes. Each node cycles color live as the control plane processes it: amber (queued) → periwinkle (running) → burgundy-red (failed) → amber (retrying) → cream-green (done). Raw/naive mode (left half of a split run) shows the grid stalling with a wall of red — dead tasks, no recovery. Control-plane mode (right half / second run) shows the same seeded failure pattern resolve into a converging wall of green in under 15 seconds. The recording ends on a stat card flipping in: **"31% raw task failure rate → 98% success rate after control-plane retries — 0 extra lines in the agent code."** That card, rendered as the branded HTML report, is the LinkedIn screenshot.

## Slices (max 4)
1. **Core primitives** — `Task`, `Router` (round-robin across N simulated workers), `RetryPolicy` (exponential backoff, max attempts), and a JSONL `Observer` that logs every state transition (`queued`/`running`/`failed`/`retrying`/`done`) with task id, worker id, attempt, latency. CLI runs a fixed batch sequentially, no concurrency yet — demoable by reading the JSONL output.
2. **Concurrency + fault injection** — worker pool (Python `threading`), each simulated worker has a configurable, seeded random failure rate and latency jitter. Control plane retries failed tasks via the router; a "naive mode" flag disables retries/routing entirely (calls workers directly, no recovery) so the two modes are directly comparable on the identical seeded failure sequence.
3. **Wow shot** — live terminal dashboard (stdlib `curses` or raw ANSI redraw, no deps) rendering the task grid described above in real time from the Observer's live event stream, plus a `report.html` generator matching brand aesthetics (deep burgundy `#7E1621` bg, `#6A1119` panel, cream `#F2E8D6` text, periwinkle `#AEC3E8` accent, Fraunces display font w/ one periwinkle accent word, Inter body, JetBrains Mono for numbers, uppercase kicker top-left with middle dots, footer "Lukas Jopcik · built in the open") showing the naive-vs-control-plane comparison stat card.
4. **Benchmark hardening** — a `run_benchmark.py --runs N` harness that repeats the seeded naive-vs-control-plane comparison across N runs (default 20) at a configurable failure rate, aggregates success-rate delta, mean latency delta, and total retry count into the report with confidence range (min/max across runs), so the headline number isn't a single lucky seed.

## Success criteria
- [ ] `python3 swarmdeck/run_benchmark.py --tasks 50 --failure-rate 0.3 --runs 1` exits 0 and prints a naive-vs-control-plane summary table to stdout
- [ ] A JSONL file is produced with ≥1 line per task-state-transition; every line parses via `json.loads` and contains `task_id`, `state`, `attempt`, `worker_id`, `latency_ms`
- [ ] At `failure_rate > 0`, the log contains at least one event with `attempt > 1` (proves retries actually fire) in control-plane mode, and zero such events in naive mode
- [ ] Control-plane success rate is measurably higher than naive success rate on the same seed (report shows both numbers + delta)
- [ ] `report.html` is generated, contains the exact hex codes `#7E1621`, `#6A1119`, `#F2E8D6`, `#AEC3E8`, loads Fraunces/Inter/JetBrains Mono, and renders the stat card with the computed delta
- [ ] The live terminal dashboard runs for the full batch duration (≥10s at default settings) and visibly updates node colors at least 3 times per node lifecycle (queued→running→(failed→retrying)*→done) — verifiable by piping the ANSI output through `script -c` and grepping for ≥3 distinct color codes per task id
- [ ] `run_benchmark.py --runs 20` completes and reports min/max/mean success-rate delta across runs, not just one seed
- [ ] Entire tool runs with zero third-party pip installs (`pip list` diff before/after is empty) and zero network calls (verifiable by running with network disabled)

## Test plan
From a clean shell in the repo directory:
1. `python3 -m venv /tmp/sd-check && source /tmp/sd-check/bin/activate` — confirm no packages get installed by the tool itself (`pip freeze` before and after running SwarmDeck should be identical).
2. `python3 swarmdeck/run_benchmark.py --tasks 50 --failure-rate 0.3 --runs 1 --seed 42` — check exit code 0, inspect stdout table, confirm `events.jsonl` written.
3. `python3 -c "import json; [json.loads(l) for l in open('events.jsonl')]"` — confirms every log line is valid JSON with required fields.
4. `python3 -c "import json; assert any(json.loads(l).get('attempt',1)>1 for l in open('events.jsonl') if json.loads(l).get('mode')=='control')"` — confirms retries fired.
5. Open `report.html` in a browser (or `grep -c '#7E1621\|#AEC3E8' report.html`) — confirms brand styling and confirms the stat-card numbers match the stdout table.
6. `unset ANTHROPIC_API_KEY OPENAI_API_KEY; python3 swarmdeck/run_benchmark.py ...` with network disabled (e.g. `unshare -n` or airplane mode) — confirms zero external dependency.
7. `python3 swarmdeck/dashboard.py --tasks 50 --failure-rate 0.3` piped through `script -qc "..." /tmp/out.log` for 15s, then grep the log for the expected ANSI color sequences to confirm live redraws happened.
8. `python3 swarmdeck/run_benchmark.py --tasks 50 --failure-rate 0.3 --runs 20` — confirm min/max/mean lines appear in output.

## Run instructions
```bash
cd swarmdeck
python3 run_benchmark.py --tasks 50 --failure-rate 0.3 --runs 1 --seed 42   # quick check
python3 dashboard.py --tasks 50 --failure-rate 0.3 --seed 42                # the wow shot, live in terminal
open report.html                                                            # branded LinkedIn screenshot
python3 run_benchmark.py --tasks 50 --failure-rate 0.3 --runs 20            # the quantified number
```
Record the dashboard with `asciinema rec demo.cast` (or `script`) for the LinkedIn video asset; screenshot `report.html` at ≥1280×800 for the static asset.

## Out of scope
- Actually cloning/integrating the real BoundFlow GitHub repo — we build a minimal from-scratch analog to stay dependency-free and self-contained.
- Real LLM API calls (Anthropic/OpenAI/etc.) — all "agents" are simulated workers with seeded latency/failure injection; this keeps the whole experiment free and reproducible.
- Distributed/multi-machine routing, persistence beyond JSONL + static HTML, auth, or any deployed service.
- Production-grade retry semantics (circuit breakers, rate limiting) beyond what's needed to demonstrate the wow shot and the benchmark number.

## Kill criteria
- Terminal dashboard rendering (curses/ANSI) proves flaky/inconsistent across 2 iterations of attempts → drop to a simpler static-frame GIF-from-log wow shot instead of live terminal; if that also fails within 1 more iteration, write up as "broke: rendering, not the control plane."
- Core routing/retry logic doesn't produce a measurable success-rate delta over naive mode after 2 iterations of debugging → stop and publish as "broke": the concept didn't hold up under a fair benchmark.
- If reproducing a believable failure-injection model (workers failing in a way that retries can actually fix) turns out to require more realism than stdlib randomness can give in 2 iterations → simplify to a fixed failure schedule and note the simplification; only kill if even that can't show a delta.