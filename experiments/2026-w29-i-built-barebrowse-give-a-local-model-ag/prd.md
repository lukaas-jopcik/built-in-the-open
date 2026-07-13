# barebrowse

## Goal
A stdlib-only Python tool that converts any web page into a pruned, ARIA-role-style text snapshot (no Playwright, no browser), then drives a local-model (or rule-based fallback) agent through a real multi-step task using only that snapshot — proving to founders that browsing agents can skip the heavyweight browser-automation stack and burn a fraction of the tokens.

## Wow shot
A single `report.html` (brand-styled, opens standalone in any browser) plays back an autonomous agent completing a real task — e.g. "search Wikipedia for X, follow the right link, extract fact Y" — as a step-by-step transcript: each step shows the pruned snapshot the agent actually saw, the action it chose, and a running token-count counter ticking up in the periwinkle accent color while a shadow counter for "raw HTML equivalent" rockets far higher beside it. The payoff frame is a final bar-chart panel: **raw HTML tokens vs. barebrowse snapshot tokens across 15 real pages**, with the reduction percentage rendered large in Fraunces. That gap — a live task completed end-to-end while the token bar stays flat — is the stop-scrolling moment.

## Slices (max 4)
1. **Snapshot engine** — `barebrowse/snapshot.py` parses static HTML with stdlib `html.parser`, maps tags to implicit ARIA roles (button, link, heading, nav, form, textbox, etc.), strips non-semantic wrappers/scripts/styles, and assigns stable `ref` ids to interactive elements. CLI: `python3 -m barebrowse snapshot <url>` prints the pruned tree. Demo-able alone: run against any real page and see structured output plus a token-count line.
2. **Browser session** — `barebrowse/browser.py` wraps `urllib` + the snapshot engine into a `Browser` object with `goto(url)`, `click(ref)`, `type(ref, text)`, `submit(ref)`. No JS execution. Demo-able alone: a script that navigates from page A to page B purely by clicking a `ref` pulled out of the snapshot text.
3. **Autonomous agent + wow report** — `barebrowse/agent.py` loops: feed snapshot → local model (Ollama HTTP API via stdlib `urllib`, if present) or deterministic rule-based policy (fallback) → parse chosen action → execute via `Browser` → repeat until task-complete or step cap. Every run logs steps to JSON; `barebrowse/render_report.py` turns that log into the brand-styled standalone `report.html` described in the Wow shot.
4. **Benchmark + hardening** — `barebrowse/bench.py` runs the snapshot engine over a fixed list of ≥15 real public pages, records raw-HTML token count vs. pruned-snapshot token count, and runs the slice-3 task N=10 times to compute a success rate. Both numbers feed into `report.html`'s final panel.

## Success criteria
- [ ] `python3 -m barebrowse snapshot <url>` produces non-empty structured output (no traceback) for 5 distinct real public pages.
- [ ] `bench.py` reports, across ≥15 real pages, a mean token reduction of pruned-snapshot vs. raw-HTML ≥ 70%, written to `bench_results.json`.
- [ ] `Browser.goto/click/type` completes a scripted 3+ step navigation purely from snapshot-derived refs, asserted by an automated test (`tests/test_browser.py` exits 0, no manual watching).
- [ ] The autonomous agent (local-model or rule-based fallback) completes the defined task end-to-end in ≥ 8/10 runs, logged in `run_log.jsonl`.
- [ ] `report.html` opens directly in a browser (file:// URL, no server) and renders the transcript, token-comparison bars, and success-rate number, styled per the brand spec (no default/bootstrap look).
- [ ] Core snapshot/browser/bench path runs with stdlib only — confirmed by running it in a fresh venv with zero installed packages.

## Test plan
From a clean shell in the repo directory:
```
python3 -m venv /tmp/bb-clean && source /tmp/bb-clean/bin/activate
python3 -m barebrowse snapshot https://en.wikipedia.org/wiki/Special:Random   # repeat x5, check non-empty output
python3 -m pytest tests/test_browser.py -q                                   # asserts multi-step nav via refs
python3 barebrowse/bench.py --pages pages.txt --out bench_results.json       # check reduction % in output
python3 barebrowse/agent.py --task task.json --runs 10 --out run_log.jsonl   # check success rate line printed
python3 barebrowse/render_report.py run_log.jsonl bench_results.json -o report.html
open report.html   # (or xdg-open) — visually confirm brand styling, transcript, chart, no console errors
deactivate
```
Each command's exit code and printed number is the pass/fail signal — no subjective judgment needed except the final visual open.

## Run instructions
```
git clone <this repo dir> && cd barebrowse
python3 -m barebrowse snapshot https://example.com
python3 barebrowse/bench.py --pages pages.txt --out bench_results.json
python3 barebrowse/agent.py --task task.json --runs 10 --out run_log.jsonl
python3 barebrowse/render_report.py run_log.jsonl bench_results.json -o report.html
```
(Optional, only if the wow-with-LLM variant is desired: `ollama pull llama3.2` and `ollama serve` before running `agent.py` — otherwise `agent.py` auto-falls back to the rule-based policy.)

## Out of scope
- No JavaScript execution / SPA rendering (static HTML only — this is the explicit trade-off vs. Playwright).
- No paid model APIs, no cloud deploy, no persistent server — everything is a one-shot local script producing local files.
- No auth-gated or logged-in browsing flows.
- No general-purpose "any website, any task" claim — the demo targets one chosen public site/task, not a universal agent.

## Kill criteria
- If the HTML→ARIA-role heuristic produces unusable/garbage snapshots on more than half of a 10-page sample after 2 tuning iterations, stop slice 1 and write up as broken (core idea doesn't hold on real-world markup).
- If no local model runtime (Ollama or equivalent) is available/installable in the build sandbox **and** the rule-based fallback also can't complete the slice-3 task, ship slices 1-2 only and report the wow shot as "broke" — snapshot engine + benchmark still stand alone.
- If the chosen target site blocks scripted fetches (403/anti-bot) and no permissive alternative public site is found within 1 iteration, swap sites; if still blocked after 2 iterations, kill the live wow shot and fall back to a bundled static HTML sample set for the benchmark.
- Hard stop regardless of progress: 10 iterations / 3 evenings.

## Depth extensions
1. **Edge-case sweep**: feed the snapshot engine pages with iframes, deeply nested divs, ARIA landmarks (`nav`/`main`/`aside`), and tables; tune pruning thresholds until snapshots stay both compact and lossless for task-relevant elements.
2. **Robustness pass**: handle redirects, timeouts, non-UTF8 encodings, and malformed HTML gracefully (no crash, log-and-skip), re-run the benchmark to confirm reduction numbers hold.
3. **Second wow variation**: run the identical task through the same local model fed *raw* HTML instead of the pruned snapshot, and show it stalls/hallucinates/exceeds context — a stark before/after panel added to `report.html`.
4. **Usage guide**: `README.md` documenting the `Browser` API, the snapshot text format, and how to point `agent.py` at a new task/site in under 10 lines of config.