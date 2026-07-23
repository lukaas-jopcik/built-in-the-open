# Skillcage
## Goal
A tiny declarative DSL (`.sky` files) that orchestrates chained "tool calls" inside a pure-Python AST-whitelist sandbox, ending in a live HTML dashboard that shows safe steps lighting up green while a real corpus of sandbox-escape attempts gets caught and flashed red in the same run — proving to a founder that "declarative + sandboxed" orchestration isn't just a slogan, it measurably blocks the exact attacks a raw `eval()`-based tool-runner would fall for.

## Wow shot
A single HTML page (`dashboard.html`, self-contained, no CDN) replays a recorded orchestration run as an animated DAG: 5-6 nodes (`fetch_a`, `fetch_b`, `transform`, `filter`, `aggregate`, `report`) light up sequentially/in-parallel with soft periwinkle glow and a timing readout per node, culminating in an assembled report card sliding into view. Immediately after, a second run plays in the same view using `examples/malicious.sky`, which attempts ~10 real escape techniques (`os.system`, `open("/etc/passwd")`, `socket.connect`, `subprocess`, `__import__`, `eval`, bare `exec`, `globals()` walk, `.__class__.__mro__` sandbox-escape gadget, decorator-based bypass) — each node flashes red with a "BLOCKED: <reason>" cream-on-burgundy banner instead of executing, and the run ends with a scoreboard: "10/10 attack vectors blocked, 0 escapes, +Xms overhead vs raw eval." That before/after — clean DAG completing vs. attack DAG getting caged in real time — is the stop-the-scroll moment.

## Slices (max 4)
1. **Core DSL + executor (hello world scaffold)**: parse a minimal declarative `.sky` file (JSON or YAML-lite, stdlib `json`/`configparser`, no PyYAML) describing steps + dependencies; execute them in topological order against a small registry of whitelisted mock tools (local JSON fixtures for "fetch", pure functions for transform/filter/aggregate); print a plain-text execution log. Demo: `python3 run.py examples/report.sky` prints step-by-step log and final result.
2. **Sandbox layer**: wrap tool bodies (and any user-supplied expressions in the DSL, e.g. filter predicates) in an `ast`-based whitelist — allowed nodes only (no `Import`, `Call` to dunder/`eval`/`exec`/`open`/`__import__`, no attribute access on `__class__`/`__globals__`, etc.) plus a wall-clock timeout per step via `signal` or a subprocess with a hard limit. Demo: `python3 run.py examples/malicious.sky` refuses every dangerous node and reports which line/technique was blocked, without crashing the interpreter.
3. **Wow shot dashboard**: instrument the executor to emit a JSONL trace (`trace.jsonl`) of step start/end/status/timing/blocked-reason; a static `dashboard.html` (brand-styled per aesthetics below) reads the trace and animates the DAG, replaying both the clean run and the malicious run back-to-back, ending on the scoreboard. Demo: `python3 -m http.server` + open `dashboard.html`, watch the full animation in one take.
4. **Benchmark + hardening**: expand the attack corpus to ≥20 distinct escape techniques in `examples/attacks/`, run all of them through the sandbox, and emit `benchmark.md`/`benchmark.json` with block-rate (N/20), false-positive check (the 5 legitimate `.sky` examples still all pass), and timing overhead of the AST-sandboxed path vs. a naive `eval()`-based baseline over 100 runs.

## Success criteria
- [ ] `python3 run.py examples/report.sky` exits 0 and produces `report.json` whose contents exactly match `examples/report.expected.json`.
- [ ] `python3 run.py examples/malicious.sky` exits non-zero (or exits 0 with a `blocked` status) and blocks 100% of the techniques encoded in that single file, verified by `python3 -m unittest discover tests/`.
- [ ] `python3 benchmark.py` reports ≥18/20 (≥90%) of the full attack corpus in `examples/attacks/` blocked, 0 false positives on the 5 legitimate examples, and prints a numeric overhead % (sandboxed vs raw eval).
- [ ] `dashboard.html`, opened via `python3 -m http.server` in a browser at ≥1280×800, plays the clean-run animation then the attack-run animation with visible red "BLOCKED" banners and a final scoreboard line, with zero console errors — verified by a human loading the page.
- [ ] Entire repo runs with zero third-party pip installs (`pip list` diff before/after is empty) and makes no network calls other than the local `http.server`.

## Test plan
From a clean shell, in the repo directory:
1. `python3 -m unittest discover tests/` — unit tests for parser, DAG ordering, sandbox AST-whitelist (both accept/reject cases), and timeout enforcement.
2. `python3 run.py examples/report.sky` then `diff report.json examples/report.expected.json` — must be empty.
3. `python3 run.py examples/malicious.sky` — inspect stdout/exit code for block report; confirm no side effects occurred (`ls` shows no new/modified files outside `report.json`, no stray process, `/etc/passwd` untouched — trivially true since sandbox runs as the same user with no elevated access, verified by checking the tool never actually reached the filesystem call).
4. `python3 benchmark.py` — read `benchmark.json`, confirm block-rate ≥90% and false-positive count is 0.
5. `python3 -m http.server 8000` in repo dir, open `http://localhost:8000/dashboard.html`, watch full animation, confirm scoreboard numbers match `benchmark.json`.

## Run instructions
```
cd <repo>
python3 -m unittest discover tests/
python3 run.py examples/report.sky
python3 run.py examples/malicious.sky
python3 benchmark.py
python3 -m http.server 8000   # then open http://localhost:8000/dashboard.html
```

## Out of scope
- Real network-facing tools or any external/paid API calls — all "tools" operate on local JSON fixtures.
- Full language features (loops, conditionals, user-defined functions) in the DSL — steps + linear/DAG deps + simple filter expressions only.
- True OS-level sandboxing (containers, seccomp, gVisor) — this is a language-level AST whitelist, and the PRD is explicit that this is a *mitigation*, not a formal security boundary.
- Multi-user/session dashboard, persistence, or any server beyond `python3 -m http.server` for local viewing.
- Packaging/publishing as a pip package.

## Kill criteria
- If after 2 iterations the AST-whitelist approach lets ≥3 of the first 10 basic attack techniques (e.g. `os.system`, `eval`, `__import__`) through without a design fix in sight — pure-Python sandboxing is well-known to be leaky (metaclass/gadget escapes), so if we can't hit ≥90% block rate on the corpus, stop and publish "broke": pure-stdlib AST sandboxing cannot be made trustworthy, here's the escape that broke it and the block-rate ceiling we hit.
- If slice 1 (basic DAG executor) isn't runnably demoable in 1 iteration — stop, this shouldn't happen, but if it does the write-up is "the core idea didn't even clear hello-world."
- If the dashboard animation can't be made to look premium/on-brand within slice 3's budget (still looks like a debug page) — ship the benchmark numbers and trace log as the LinkedIn asset instead of the animation, and note the visual miss honestly.

## Depth extensions
1. **Fuzzed corpus**: auto-generate 50+ attack variants (recombining known gadget primitives) and re-run the benchmark to see if the block-rate holds at scale, not just on hand-written examples.
2. **Parallel fan-out visualization**: extend the DSL/executor to run independent branches concurrently (via `concurrent.futures`) and show the dashboard animating true parallel node execution, not just sequential — a stronger "scale" wow variant.
3. **Reusable usage guide**: write a short `README.md`/`USAGE.md` showing how someone drops in their own tool functions and `.sky` files tomorrow — the standalone-value artifact.
4. **Terminal-recording fallback**: produce a text-based asciinema-style replay (stdlib only, e.g. re-printing the trace with `time.sleep` pacing) as a LinkedIn-postable alternative for viewers who can't open the HTML file.