# Build Log — Adaptive Recall Bench

## iter 1 — 2026-07-20
Implemented Slice 1 (Memory core scaffolding). Built `memory_core.py`: stdlib-only
`sqlite3` store (WAL mode) with `remember(text, tags)` / `recall(query, k)` and a
CLI (`remember` / `recall` subcommands, `--json` output option). Recall ranks
facts by keyword-overlap score (Jaccard + query-coverage blend) since the
adaptive recency-decay ranking is scoped to Slice 2. Added `.gitignore` for
`memory.db*` and `__pycache__`.

Test (test plan step 1): ran `remember` in one process, then `recall` in a
**separate** process invocation against the same `memory.db` on disk.

```
$ python3 memory_core.py remember "the launch date is March 3" --tags launch,date
Remembered (id=1): the launch date is March 3
$ python3 memory_core.py recall "launch date"
1. [score=0.8333] the launch date is March 3 (tags: launch, date)
```

Also spot-checked ranking sanity with 3 stored facts + a query and a
no-match query (returns clean "(no matching facts)", no exception):
```
$ python3 memory_core.py recall "when is the meeting"
1. [score=0.875] the meeting is on Tuesday (tags: meeting)
2. [score=0.5] the launch date is March 3 (tags: launch, date)
3. [score=0.2361] the office moved to 5th avenue (tags: office)
$ python3 memory_core.py recall "unrelated gibberish query xyz"
(no matching facts)
```

Result: PASS — fact written in process A was read back correctly in
process B with zero server running, confirming persistence.

STATUS: slice 1 done

TG: Built the persistent memory core — a fact stored by one program run is
correctly recalled by a completely separate run later, using a local SQLite
file instead of a live server. Test passed: wrote "the launch date is March 3"
in one process, read it back in a fresh process with a relevance score of
0.83. Next iteration will wrap this in a minimal MCP JSON-RPC server so an
agent can call `remember`/`recall` as tools over stdio.

## iter 2 — 2026-07-20
Implemented Slice 2 (MCP server wrapper). Added `mcp_server.py`: a minimal
MCP-flavored JSON-RPC 2.0 server over stdio (stdlib `json`/`sys` only, no MCP
SDK) supporting `initialize`, `tools/list`, and `tools/call` for the
`remember`/`recall` tools, plus batch (array) requests. Added
`memory_core.adaptive_recall()`: blends keyword-overlap score with
exponential recency decay (tunable `half_life_sessions`), using session-number
elapsed distance when facts/queries carry a session (as the Slice 3 benchmark
will), falling back to elapsed wall-clock minutes otherwise. A fact must have
nonzero keyword overlap to surface — recency alone never resurfaces an
irrelevant fact. Added `sample_request.json` matching the PRD's run
instructions.

Test (test plan steps 2-3): fresh `remember` in one process, then a raw
JSON-RPC `tools/call` request for `recall` piped into a **separate**
`mcp_server.py` process invocation over stdio; then a malformed-input check.

```
$ python3 memory_core.py remember "the launch date is March 3" --tags launch,date
Remembered (id=1): the launch date is March 3
$ printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"recall","arguments":{"query":"launch date"}}}' | python3 mcp_server.py
{"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "[{\"id\": 1, \"text\": \"the launch date is March 3\", ... \"score\": 0.9}]"}], "isError": false}}
$ printf 'not json\n' | python3 mcp_server.py; echo "exit=$?"
{"jsonrpc": "2.0", "id": null, "error": {"code": -32700, "message": "Parse error: Expecting value: line 1 column 1 (char 0)"}}
exit=0
```

Also spot-checked: `tools/list` returns both tool schemas; a `tools/call` with
a missing required argument returns a `-32602` error (not a traceback); a
JSON-array batch request returns a JSON-array of responses. All via
`python3 -m py_compile` clean.

Result: PASS — spec-shaped JSON-RPC round trip over stdio works, malformed
input returns a proper JSON-RPC error object with exit code 0 (no crash).

STATUS: slice 2 done

TG: Wrapped the memory store in a minimal MCP-style server that speaks
JSON-RPC over stdin/stdout — no Anthropic/OpenAI SDK involved, just Python's
standard library. Tested it two ways: a valid "recall" request correctly
returned the fact planted moments earlier by a separate process (relevance
score 0.9), and a garbage/malformed input returned a clean JSON error instead
of crashing. Next iteration builds the 50-session benchmark that compares
this against a memory-less baseline and should produce the "adaptive recall
beats stateless by 3x+" headline number.

## iter 3 — 2026-07-20
Implemented Slice 3 (wow-shot benchmark + dashboard). Built `benchmark.py`:
50 deterministic synthetic conversations (10 fact templates x 5 subjects
each, seeded `random.Random`), each plants one fact into a **shared**
in-memory SQLite store (all 50 facts coexist as mutual distractor noise,
not synthetic filler) and is queried 3x later at +5/+10/+20 sessions
(150 queries total). Two strategies answer every query against the same
seeded RNG stream: a stateless baseline that has zero persistent memory and
can only guess a plausible slot value at random (e.g. one of 12 candidate
dates/names/amounts per template), vs `memory_core.adaptive_recall` reading
the shared store. Writes `results.json` (per-conversation, per-query
correct/incorrect + adaptive score, plus aggregate accuracies) and renders
`dashboard.html` by embedding that JSON directly into `dashboard_template.html`
(no `fetch()`, so it opens standalone over `file://` with zero CORS issues).

Test (test plan steps 4-6):
```
$ time python3 benchmark.py --sessions 50 --seed 42
Wrote results.json: baseline_accuracy=0.08 adaptive_accuracy=0.9267 (139/150 vs 12/150)
Wrote dashboard.html
real  0m0.056s
$ python3 benchmark.py --sessions 50 --seed 42 --no-dashboard   # second run
$ diff results_run1.json results.json && echo "DETERMINISTIC: byte-identical"
DETERMINISTIC: byte-identical
$ python3 -c "...adaptive_accuracy >= 3*baseline_accuracy..."
0.9267 0.08 True
```
Then rendered `dashboard.html` in a headless Chromium (Playwright) via a
`file://` URL (no HTTP server) to actually verify the wow shot, not just the
JSON: 0 JS console/page errors, both grids populated with exactly 150 cells,
counters landed on **8%** (stateless) and **93%** (adaptive) matching
`results.json`, brand colors/fonts (burgundy heading, cream background,
periwinkle ✓ cells, red ✗ cells, Fraunces/Inter/JetBrains Mono) rendered as
specified. Screenshot confirmed the split-screen grid + landed percentages
side by side as described in the Wow shot section.

Result: PASS on all of test plan steps 4-6 — benchmark runs in 0.056s (well
under the 60s budget), is byte-identical across repeated runs with the same
seed, adaptive recall beats the stateless baseline by ~11.6x (92.67% vs 8%,
comfortably over the 3x bar), and the dashboard renders correctly standalone
in a real browser with the exact brand treatment.

STATUS: slice 3 done

TG: Built and visually verified the "wow shot" — a 50-conversation benchmark
where a memory-less agent guesses facts from scratch (8% correct) while the
adaptive-recall agent looks them up in persistent memory (93% correct), an
~11.6x gap, reproducible byte-for-byte on reruns and generated in under a
tenth of a second. Opened the resulting dashboard.html in a real headless
browser to confirm the animated split-screen grid and the two landed
percentages render correctly with zero errors, not just that the JSON looks
right. Next iteration tackles Slice 4 (hardening: malformed input, SQLite
concurrency, duplicate/contradicting facts, empty-memory edge cases).

## iter 4 — 2026-07-20
Implemented Slice 4 (hardening) — the final PRD slice. Changes:
- `memory_core.py`: `connect()` now opens SQLite with `timeout=10.0` and sets
  `PRAGMA busy_timeout=10000` in addition to the existing `WAL` mode, so
  concurrent writers retry instead of raising `sqlite3.OperationalError:
  database is locked`.
- New `test_hardening.py` (stdlib `unittest`, isolated temp-file DBs per test
  so nothing touches the shared `memory.db`): concurrent writes/reads (20
  threads x 10 writes + 20 concurrent readers hammering the same WAL-mode
  db), exact-duplicate facts (both surface, no crash), contradicting facts
  (a later "meeting is actually Tuesday" outranks the earlier "meeting is
  Monday" once enough sessions have passed), empty-memory recall (both the
  raw function and the MCP JSON payload path), and three extra malformed
  JSON-RPC shapes beyond iteration 2's parse-error case: a bare top-level
  JSON scalar (`42`), a request with no `method` field, and a `tools/call`
  whose `arguments` is a JSON array instead of an object.

Test (test plan step + success-criteria bullets on malformed input / SQLite
concurrency / duplicate-contradicting facts / empty-memory):
```
$ python3 -m py_compile memory_core.py mcp_server.py test_hardening.py && python3 test_hardening.py
test_concurrent_remember_and_recall_under_wal ... ok
test_contradicting_fact_ranks_above_stale_one ... ok
test_exact_duplicate_facts_both_surface_without_crashing ... ok
test_mcp_recall_on_empty_store_returns_clean_empty_result ... ok
test_recall_on_empty_store_returns_empty_list ... ok
test_missing_method_field_is_method_not_found_not_crash ... ok
test_non_dict_top_level_json_is_invalid_request_not_crash ... ok
test_tools_call_with_non_object_arguments_does_not_crash ... ok
Ran 8 tests in 0.867s
OK
```
Also re-ran the original malformed-input smoke test plus a bare-scalar
variant through the real `mcp_server.py` subprocess (not just in-process):
both returned clean JSON-RPC error objects with exit code 0. Then stress-
tested the actual CLI (not just threads-in-process): spawned 10 concurrent
`python3 memory_core.py remember ...` OS processes against the shared
`memory.db` in a bash `&`/`wait` loop — all 10 succeeded, no lock errors,
and the DB ended up with exactly 10 rows (verified by count, then cleaned up
so the shared demo DB stays pristine for future runs).

Result: PASS — all 4 slices from the PRD are now implemented and tested.

STATUS: slice 4 done

TG: Hardened the memory server against the messy real-world cases: many
processes writing and reading at the same time (tested with 10 concurrent
OS processes plus 40 concurrent threads — zero lock errors), facts that
contradict each other (a later correction now correctly outranks the stale
fact it replaced), duplicate facts, and empty-memory or garbage-input
queries, all verified with 8 passing automated tests plus manual subprocess
checks. All 4 planned slices are now done — next iteration moves into the
PRD's "depth extensions": a parameter-sensitivity sweep (how the recall
half-life knob trades off against accuracy) and a second, differently-shaped
wow visual (a recall graph) to make the benchmark story land even harder.

## iter 5 — 2026-07-20
All 4 PRD slices were already done entering this iteration, so per the DEPTH
RULE this iteration moved into "## Depth extensions": #2 (parameter-
sensitivity mini-benchmark) as the main piece, plus closing out the one gap
noted in #1 (memory-cap eviction under sustained writes wasn't tested yet).

Changes:
- `memory_core.py`: `remember()` now accepts `max_facts` (default
  `MAX_FACTS = 5000`) and evicts the oldest rows (by `created_at`, ties by
  `id`) whenever the store exceeds the cap after an insert — a sustained
  writer can no longer grow `memory.db` without bound. Default cap is far
  above the 50-conversation/150-query benchmark's ~50 planted facts, so it
  doesn't touch existing behavior or numbers.
- `test_hardening.py`: new `test_memory_cap_evicts_oldest_under_sustained_writes`
  — writes 35 facts against a cap of 20, asserts exactly 20 rows survive and
  that it's the newest 20 (oldest 15 evicted, not an arbitrary/newest-evicted
  bug). 9/9 hardening tests now pass (was 8/9).
- New `sweep.py` — depth extension #2. Reuses `benchmark.build_conversations`
  with the same seed/session count as the main benchmark, then re-runs all
  150 queries through `memory_core.adaptive_recall` for every combination of
  `half_life_sessions` in {5, 10, 20, 50} and `keyword_weight` in
  {0.2, 0.4, 0.6, 0.8} (16 combos), recording accuracy per cell plus best/
  worst/default-point callouts. Stdlib only, deterministic, no network.
- New `sweep_dashboard_template.html` / generated `sweep_dashboard.html` — a
  second branded chart (line chart of accuracy vs. half-life, one line per
  keyword weight, drawn as raw SVG with no chart library, animated stroke-
  dashoffset draw-in) plus a color-graded heatmap of the same 16 cells, in
  the same burgundy/cream/periwinkle/Fraunces/Inter/JetBrains-Mono brand
  system as the main dashboard. Added reciprocal nav links between
  `dashboard.html` and `sweep_dashboard.html`.

Test (hardening suite + sweep-specific determinism/timing/visual checks):
```
$ python3 -m py_compile memory_core.py mcp_server.py test_hardening.py benchmark.py sweep.py
$ python3 test_hardening.py
Ran 9 tests in 0.279s
OK
$ python3 benchmark.py --sessions 50 --seed 42   # re-verify cap didn't move the wow numbers
Wrote results.json: baseline_accuracy=0.08 adaptive_accuracy=0.9267 (139/150 vs 12/150)
$ time python3 sweep.py --sessions 50 --seed 42
Wrote sweep_results.json: best=10.0hl/0.6kw=0.9267 worst=10.0hl/0.2kw=0.5133
Wrote sweep_dashboard.html
real 0m0.434s
$ python3 sweep.py --sessions 50 --seed 42 --no-dashboard   # second run
$ diff sweep_run1.json sweep_results.json && echo "DETERMINISTIC: byte-identical"
DETERMINISTIC: byte-identical
```
Sweep accuracy spread across the 16 cells ranges 51%–93% (a real tradeoff,
not a flat/degenerate curve) — half-life alone barely matters once
keyword_weight ≥ 0.6, but at keyword_weight=0.2 (recency-dominated ranking)
accuracy collapses to 51–60% for short/medium half-lives, which is the
concrete "here's the knob and here's the tradeoff" story the depth extension
asked for. The default point used on the main dashboard (10.0, 0.6) turned
out to already be the best cell in the sweep (93%).

Then rendered both `dashboard.html` and `sweep_dashboard.html` in headless
Chromium (Playwright) over `file://`: zero JS console/page errors on either,
main dashboard still lands on 8%/93% after adding the new nav link (no
regression), sweep dashboard's 16 heatmap cells / 4 SVG lines / 16 dots all
populated and callouts read "hl=10 kw=0.6 → 93%" (best) / "hl=10 kw=0.2 →
51%" (worst) / "hl=10 kw=0.6 → 93%" (default), screenshot confirmed on-brand
styling (burgundy headings, cream background, periwinkle-to-burgundy
heatmap gradient, Fraunces/Inter/JetBrains Mono).

Result: PASS — memory-cap eviction test added and passing (closes the last
gap in depth extension #1), parameter-sensitivity sweep built, benchmarked,
and visually verified (depth extension #2 complete).

STATUS: slice 4 done

TG: Added a safety net so the memory server can't grow without bound under
heavy sustained use (old facts get evicted past a 5,000-fact cap, verified
with a new automated test), and built a second branded report that answers
"what happens if you tune the memory's recall settings?" — sweeping 16
combinations of two tuning knobs, still in under half a second and fully
reproducible. The sweep shows accuracy ranging from 51% to 93% depending on
the settings, and confirms the settings already used in the main demo happen
to be the best of the 16 tested. Both new dashboard.html <-> sweep_dashboard
links and visuals were checked in a real browser with zero errors. Next
iteration will tackle the remaining depth extensions: a usage-guide README
for wiring this into a real MCP client, and a second "wow visual" — an
animated recall graph of which facts matched which queries.

## iter 6 — 2026-07-20 18:43 UTC
All 4 PRD slices plus depth extensions #1 and #2 were already done entering
this iteration, so per the DEPTH RULE this moved on to the two remaining
depth extensions: #3 (usage-guide README) and #4 (second wow visual — an
animated memory graph). Also found and fixed a real flaky bug surfaced while
re-verifying the existing hardening test suite.

Changes:
- New `README.md` — day-2 usage guide. Documents the repo file map, the
  quick-start commands, and the exact JSON stanza for wiring
  `mcp_server.py` into Claude Desktop's `claude_desktop_config.json` and
  Claude Code's `.mcp.json`/`claude mcp add`, plus an honest "what's
  simplified vs. the full MCP spec" section (no `resources/*`/`prompts/*`,
  stdio-only transport, static capability block) so the tool has standalone
  reuse value beyond this experiment, per depth extension #3.
- New `memory_graph.py` + `memory_graph_template.html` / generated
  `memory_graph.html` — depth extension #4, the second wow visual. Reads
  the existing `results.json` (no recompute, no new randomness) and
  reshapes it into a graph: one burgundy "fact" hub node per planted fact,
  one small "query" node per recall attempt at +5/+10/+20 sessions, edges
  colored periwinkle (correct) or red (missed) by whether adaptive recall
  got that query right. Layout is a from-scratch force simulation (pairwise
  repulsion + spring edges + centering + soft boundary push-back) drawn as
  raw SVG and animated via `requestAnimationFrame`, no charting library.
  Same burgundy/cream/periwinkle/Fraunces/Inter/JetBrains-Mono brand system,
  with callouts (93% adaptive accuracy, 139/150 edges, accuracy by recall
  distance) and a legend. Added reciprocal nav links across all three HTML
  reports (`dashboard.html` <-> `sweep_dashboard.html` <-> `memory_graph.html`).
  First physics tuning pass (repulsion 2600 / weak centering 0.006 / hard
  edge clamp) caused nodes to pile up in a visible line along the canvas
  walls — retuned to repulsion 1500 / centering 0.02 / soft boundary
  push-back instead of a hard clamp, which produces a natural, non-clamped
  cluster layout (verified visually, screenshot below).
- Fixed a flaky bug in `memory_core.connect()` found while re-running the
  existing hardening suite: the prior iteration 4/5 logs claimed the 40-way
  concurrency test passed cleanly, but re-running `test_hardening.py` 5x in
  this iteration failed with `sqlite3.OperationalError: database is locked`
  2 of 5 times. Root cause: the very first `PRAGMA journal_mode=WAL` and the
  `CREATE TABLE IF NOT EXISTS` schema-creation statement both need a brief
  exclusive lock, and when 40 threads race to `connect()` to the same
  brand-new file at once, SQLite's busy handler doesn't always engage for
  that specific lock even with `busy_timeout` set — a genuine startup-race
  gap the prior tests happened not to hit. Fixed by wrapping the WAL-switch
  + schema-creation step in a retry loop (up to 20 attempts, short backoff)
  that only retries on "locked"/"busy" `OperationalError`s and re-raises
  anything else. This is the kind of SQLite concurrency issue the PRD's
  kill criteria calls out ("if SQLite concurrency/locking issues can't be
  resolved cleanly in 1 iteration, downgrade to single-process-only
  access") — resolved cleanly within this iteration, so no downgrade needed.

Test (full suite re-verify + new artifacts + regression check):
```
$ python3 -m py_compile memory_core.py mcp_server.py test_hardening.py benchmark.py sweep.py memory_graph.py
$ for i in 1 2 3 4 5 6 7 8; do python3 -m unittest test_hardening.ConcurrencyTest; done   # was 2/5 failing before the fix
... 8/8 OK after the connect() retry fix (was flaky before)
$ python3 test_hardening.py   # x5 in a row after the fix
Ran 9 tests in ~0.2-0.9s
OK (all 5 runs)
$ python3 memory_core.py remember "the launch date is March 3"
$ python3 memory_core.py recall "launch date"
1. [score=0.8333] the launch date is March 3
$ printf '%s\n' '{"jsonrpc":"2.0",...,"method":"tools/call","params":{"name":"recall",...}}' | python3 mcp_server.py
{"jsonrpc": "2.0", "id": 1, "result": {...}}
$ printf 'not json\n' | python3 mcp_server.py; echo exit=$?
{"jsonrpc": "2.0", "id": null, "error": {"code": -32700, ...}}
exit=0
$ python3 benchmark.py --sessions 50 --seed 42   # re-verify connect() fix didn't move the wow numbers
Wrote results.json: baseline_accuracy=0.08 adaptive_accuracy=0.9267 (139/150 vs 12/150)
$ diff <(git show HEAD:results.json) results.json   # byte-identical, no working-tree diff at all
$ python3 sweep.py --sessions 50 --seed 42
Wrote sweep_results.json: best=10.0hl/0.6kw=0.9267 worst=10.0hl/0.2kw=0.5133
$ python3 memory_graph.py
Wrote memory_graph.html: 200 nodes / 150 edges (139/150 correct edges)
```

Then rendered all three HTML reports in headless Chromium (Playwright) over
`file://`:
- `dashboard.html`: zero console/page errors, counters land on 8% / 93%
  after ~6s (staged-reveal counter, not instant), both new nav links present,
  screenshot confirms brand styling unchanged from before this iteration's
  edits.
- `memory_graph.html`: zero console/page errors, 200 SVG circles / 150 SVG
  lines rendered, force layout settles (`#settle-badge` shows) within ~7-9s
  and then stops animating (bounded `MAX_FRAMES`, doesn't spin forever),
  callouts read "93%" / "139 / 150" / "+5: 94% +10: 94% +20: 90%" matching
  `results.json` exactly, footer shows "baseline for comparison: 8%".
  Screenshot confirmed after the physics retune: facts and queries form
  natural clusters, periwinkle edges dominate with a handful of visible red
  "missed" edges/clusters, no wall-clamped nodes.
- `sweep_dashboard.html`: unchanged from iteration 5, re-verified nav link
  to `memory_graph.html` resolves.
- Cross-checked all 3 pages link to each other (`grep href` on all three
  confirms the expected 2 outbound links each).

Result: PASS — depth extensions #3 (README) and #4 (memory graph) are both
built and verified; all 4 PRD depth extensions are now complete, and a real
(if intermittent) concurrency bug was caught and fixed rather than papered
over. `memory.db`/`-wal`/`-shm` created during manual CLI testing were
removed before finishing (gitignored, but kept the working tree clean
regardless).

STATUS: all done

TG: Finished the last two "make this actually useful" items: a README that
tells someone exactly how to plug this memory server into Claude Desktop or
Claude Code (the copy-pasteable config snippet), and a second shareable
visual — an animated graph showing all 50 planted facts and the 150 recall
attempts against them, color-coded green/red by whether memory got it
right. While re-testing everything end to end I also caught a real bug: the
concurrency safety net from a few iterations ago was flaky under heavy load
(failed roughly 2 times out of 5 in a stress test), not the "zero errors"
it was reported as — I fixed the root cause (a startup race when many
processes open a brand-new database at once) and it's now passed 13
consecutive stress-test runs. With that fixed, every slice in the plan and
every depth extension is built, tested, and visually verified, so this
project is done — the concrete numbers for the founder to share are still
the same: 93% recall with memory vs. 8% without, across 150 test queries.
