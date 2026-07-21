# Adaptive Recall Bench: Persistent Memory Over MCP, Proven With Numbers

## Goal
Build a minimal MCP-compatible persistent-memory server (SQLite-backed, adaptive recency+relevance ranking) and prove — with a reproducible N-session benchmark and a premium before/after dashboard — that it recalls facts across sessions where a stateless agent forgets.

## Wow shot
A single HTML report opens showing a **split-screen session timeline**: 50 simulated multi-session conversations play out left-to-right as a compact grid of session ticks. On the left half, a "stateless agent" column flashes red ✗ almost every time a fact is queried sessions after it was stated. On the right half, the "adaptive recall agent" column lights up periwinkle ✓ almost every time, with a small recall-score bar animating up per query. Above the grid, two big numbers count up simultaneously (CSS/JS `requestAnimationFrame`-free, pure CSS counter or staged reveal): **Stateless: 8% recall** vs **Adaptive Recall: 92% recall** across the same 50 sessions and same distractor facts. The moment a founder stops scrolling: the grid finishes animating and the two percentages land side by side under the burgundy/periwinkle brand treatment — a visual, numeric "this is why your agent needs memory."

## Slices (max 4)
1. **Memory core (scaffolding hello-world):** stdlib SQLite store with `remember(text, tags)` / `recall(query, k)`; a CLI that writes a fact in one process invocation and reads it back in a second, separate invocation — proves persistence across "sessions" with zero server running.
2. **MCP server wrapper:** implement a minimal MCP server (JSON-RPC 2.0 over stdio per the MCP spec, stdlib `json`/`sys` only, no SDK dependency) exposing `remember` and `recall` as MCP tools, with adaptive ranking = recency decay (exponential, tunable half-life) blended with keyword-overlap score (stdlib-only TF-IDF-ish cosine, no ML deps). Demo: `echo` a raw JSON-RPC request at the process over stdio, get a ranked JSON result back.
3. **Wow shot benchmark + dashboard:** generate 50 synthetic multi-session conversations (templated, deterministic, no LLM calls) where facts are planted in session 1 and queried at sessions +5/+10/+20 with distractor noise; run each conversation twice — once against a stateless no-memory baseline, once against the MCP memory server — score recall accuracy; render the branded HTML/CSS/JS dashboard described in Wow shot from the resulting JSON.
4. **Hardening:** malformed JSON-RPC requests return proper MCP error responses (not crashes); concurrent recall/remember calls under SQLite `WAL` mode; duplicate and contradicting facts don't corrupt ranking; empty-memory query returns a clean empty result, not an exception.

## Success criteria
- [ ] `python3 memory_core.py remember "fact"` in one process, then `python3 memory_core.py recall "query"` in a fresh process, returns the fact — proving persistence with zero long-running server.
- [ ] `python3 mcp_server.py` accepts a raw JSON-RPC `tools/call` request for `remember` and `recall` over stdin/stdout and returns a spec-valid JSON-RPC response.
- [ ] `python3 benchmark.py --sessions 50 --seed 42` completes in under 60 seconds on stdlib alone (no network, no paid API) and writes `results.json`.
- [ ] `results.json` shows adaptive-recall accuracy at least 3x the stateless-baseline accuracy across the 50-session run (quantified comparison number for the LinkedIn post).
- [ ] `dashboard.html` opens standalone in a browser (file:// URL, no server) and renders the animated split-screen described in Wow shot, matching the brand palette (burgundy #7E1621, cream #F2E8D6, periwinkle #AEC3E8, Fraunces/Inter/JetBrains Mono).
- [ ] Malformed JSON sent to `mcp_server.py` returns a JSON-RPC error object, not a stack trace / crash.
- [ ] Re-running `benchmark.py` with the same `--seed` reproduces the same accuracy numbers exactly (determinism, no LLM/network variance).

## Test plan
From a clean shell in this experiment directory:
1. `python3 memory_core.py remember "the launch date is March 3"` then, as a **separate process**, `python3 memory_core.py recall "launch date"` — confirm the fact text is returned.
2. `printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"recall","arguments":{"query":"launch date"}}}' | python3 mcp_server.py` — confirm a valid JSON-RPC response on stdout.
3. `printf 'not json\n' | python3 mcp_server.py` — confirm a JSON-RPC error response, exit code 0, no traceback.
4. `python3 benchmark.py --sessions 50 --seed 42` — confirm `results.json` is written and `python3 -c "import json;print(json.load(open('results.json'))['adaptive_accuracy'], json.load(open('results.json'))['baseline_accuracy'])"` shows adaptive ≥ 3x baseline.
5. Run step 4 twice, `diff` the two `results.json` outputs — confirm byte-identical (determinism).
6. `open dashboard.html` (or `python3 -m http.server` and browse to it) — visually confirm the split-screen animation, the two landed percentages, and brand colors/fonts render correctly at ≥1280×800.

## Run instructions
```bash
cd 2026-w30-show-hn-adaptive-recall-persistent-memor
python3 memory_core.py remember "demo fact"
python3 memory_core.py recall "demo"
python3 mcp_server.py < sample_request.json
python3 benchmark.py --sessions 50 --seed 42
open dashboard.html   # or: python3 -m http.server 8000, then visit /dashboard.html
```

## Out of scope
- Any real LLM/agent calls (Claude API, OpenAI, etc.) — all "sessions" and "agent" behavior are deterministic simulations, not live model calls, to keep this zero-cost and reproducible.
- Real MCP client integration into Claude Desktop/Claude Code config — we implement the server side of the protocol and test it with raw JSON-RPC, not a full client handshake.
- Vector embeddings / ML-based semantic search — ranking uses stdlib string overlap + recency decay only.
- Multi-user auth, network exposure, or any deployed/hosted server — everything runs locally via stdio/file, inside this repo directory.
- Memory eviction policies beyond a simple cap (no LRU tuning research, no production-grade memory management).

## Kill criteria
- If implementing a spec-valid MCP JSON-RPC handshake (slice 2) takes more than 2 iterations without a working request/response round-trip, drop MCP fidelity and ship a simplified "MCP-flavored" JSON-RPC subset instead — write up which parts of the spec were cut and why.
- If the adaptive-recall ranking fails to beat the stateless baseline by any meaningful margin after 2 iterations of tuning (i.e., the "wow" number isn't real), stop and write up "broke": persistent memory over a naive keyword+recency scheme didn't demonstrably help in this synthetic benchmark.
- If SQLite concurrency/locking issues (slice 4) can't be resolved cleanly in 1 iteration, downgrade to single-process-only access and note the limitation rather than burning further iterations on it.
- Total: no working benchmark number by end of iteration 6 → stop, publish as "broke," and post the honest failure with what was learned.

## Depth extensions
1. **Edge case suite:** contradicting facts (e.g., "meeting is Monday" then later "meeting is actually Tuesday") — verify recall surfaces the most recent/authoritative fact, not both or the stale one; add a test for memory-cap eviction under sustained writes.
2. **Parameter sensitivity mini-benchmark:** sweep the recency-decay half-life (e.g., 5/10/20/50 sessions) and keyword-weight blend across the same 50-session set, plot accuracy vs. parameter as a second branded chart — gives a concrete "here's the knob and here's the tradeoff" artifact.
3. **Usage guide (README):** step-by-step for wiring `mcp_server.py` into a real MCP client config (Claude Desktop `claude_desktop_config.json` / Claude Code MCP settings), including the exact JSON stanza, so the tool has standalone reuse value beyond this experiment.
4. **Second wow variation — memory graph:** render an animated force-directed graph (pure SVG/JS, no deps) of which planted facts were recalled for which queries across the 50 sessions, color-coded by correct/incorrect — a different, equally shareable visual angle on the same benchmark data.