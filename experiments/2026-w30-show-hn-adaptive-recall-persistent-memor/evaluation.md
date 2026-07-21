# Evaluation — Adaptive Recall Bench

## Verdict: worked

## Depth: adequate — real, reusable MCP server + reproducible numbers, but the "stateless baseline" is a random-guess strawman, not a real forgetting agent, so the 92%-vs-8% headline is less rigorous than it looks.

## Criteria
- [x] `python3 memory_core.py remember "fact"` then a fresh process `recall "query"` returns the fact — evidence: `remember "the launch date is March 3"` → `Remembered (id=1): ...`; separate process `recall "launch date"` → `1. [score=0.8333] the launch date is March 3`.
- [x] `mcp_server.py` accepts a raw JSON-RPC `tools/call` over stdin/stdout and returns a spec-shaped response — evidence: piping the prd's exact `recall` request and `sample_request.json` both returned `{"jsonrpc": "2.0", "id": 1, "result": {"content": [...], "isError": false}}`, exit code 0.
- [x] `benchmark.py --sessions 50 --seed 42` completes in <60s, stdlib-only, writes `results.json` — evidence: `time python3 benchmark.py --sessions 50 --seed 42` → `real 0m0.057s`; wrote `results.json` (36KB).
- [x] Adaptive accuracy ≥3x baseline — evidence: `results.json` → `baseline_accuracy=0.08`, `adaptive_accuracy=0.9267` (139/150 vs 12/150), ratio = 11.58x.
- [x] `dashboard.html` opens standalone (file://) and renders the branded split-screen animation — evidence: rendered with Playwright/Chromium at 1280×800, zero console/page errors, screenshots confirm staged 0%→93%/8% count-up, burgundy `#7E1621`/cream `#F2E8D6`/periwinkle `#AEC3E8` all present, Fraunces/Inter/JetBrains Mono all referenced.
- [x] Malformed JSON returns a JSON-RPC error, not a crash — evidence: `printf 'not json\n' | python3 mcp_server.py` → `{"jsonrpc": "2.0", "id": null, "error": {"code": -32700, "message": "Parse error: ..."}}`, exit code 0.
- [x] Same `--seed` reproduces byte-identical `results.json` — evidence: ran `benchmark.py --sessions 50 --seed 42` twice, `diff` produced no output; also confirmed the freshly-regenerated `results.json`/`dashboard.html` are byte-identical to the versions already committed to git (`git status --short` clean after regenerating).

Bonus (depth-extension slices, all run and confirmed working, not required by the letter of the success criteria):
- `test_hardening.py`: 9/9 tests pass in 0.83s (concurrency under WAL, duplicate facts, contradiction-recency ranking, memory-cap eviction, empty-store, malformed-request edge cases).
- `sweep.py`: runs, writes `sweep_results.json` + `sweep_dashboard.html`, confirms default params (half-life=10, keyword-weight=0.6) are in fact the best combo found (93%) vs. worst (51%) in the 4×4 grid.
- `memory_graph.py`: runs off `results.json`, writes a force-directed SVG graph (200 nodes/150 edges), renders without errors.

## What broke / limitations
- Nothing crashed or failed to run. The weakest point isn't a bug, it's the benchmark's honesty: the "stateless baseline" isn't a simulated memory-less agent, it's `rng.randrange(len(candidate_values))` — a uniform random draw from a fixed list of 8-12 plausible answers per fact type. That mathematically produces ~1/12 ≈ 8.3% accuracy regardless of anything else. The "92.67% vs 8%, 11.6x" headline is therefore comparing a real keyword-lookup engine against a coin-flip-shaped strawman, not against how a real LLM without memory actually behaves (which might guess more cleverly from context, or refuse to answer). The comparison correctly demonstrates "memory beats no memory" in principle, but the specific magnitude is inflated/tautological, not evidence about real agent behavior.
- Query cost is O(n) full table scan on every `recall`/`adaptive_recall` call (loads every row, tokenizes, scores in Python). Fine at the demo's scale (50-5000 facts, prd's own eviction cap) but would degrade linearly with memory size in real usage — no index, no FTS, no vector search (explicitly out of scope, but worth naming as a production blocker).
- `dashboard.html`, `sweep_dashboard.html`, and `memory_graph.html` all load fonts from `fonts.googleapis.com`. They technically still render fine offline (fallback to system fonts, verified no console errors), but the "standalone, no server, no network" framing is only true for functionality, not for the exact branded look — first open on an air-gapped machine won't match the intended typography.
- The concurrency hardening test exercises 20 writer + 20 reader threads inside one Python process (sharing the GIL), not genuinely separate OS processes contending for the SQLite file. That's a real test of WAL-mode thread-safety but a weaker proof than the prd's "concurrent recall/remember calls" implies for a real multi-process MCP deployment (e.g. two Claude Desktop instances).
- The distractor set reuses at least one subject name across two different fact templates ("Ingrid" appears twice in the 50-name pool with different templates/queries), which creates genuine keyword-overlap ambiguity — plausibly part of why adaptive recall isn't 100% (139/150, not 150/150). This is realistic noise, but it's incidental rather than a designed edge case, and isn't called out anywhere in the repo.
- No real MCP client (Claude Desktop/Code) handshake was tested, per the prd's own out-of-scope — the README gives a plausible-looking config stanza but it has not been proven against an actual client.

## Founder translation
This is a working, free, local "memory" add-on for an AI assistant — imagine your AI stops forgetting things you told it weeks ago (a launch date, a teammate's new schedule) instead of guessing or making something up. In this test it built its own scorecard: with memory it got the right answer about 93% of the time versus about 8% of the time without it. That's a real, reproducible result, but it was measured on made-up practice conversations the tool generated for itself, not on your actual chats or a live AI, and the "no memory" comparison point is closer to a coin flip than to how an assistant actually behaves — so treat the 93% as "this general idea clearly works," not as "your support bot will be 11x better." Cost to build something like this: a few hours of a developer's time and no ongoing API/hosting fees, since it deliberately avoids all paid AI calls in its own testing.

## Numbers
- Adaptive recall accuracy: 92.67% (139/150 correct)
- Stateless baseline accuracy: 8.00% (12/150 correct)
- Benchmark runtime: 0.057s for 50 conversations / 150 queries (well under the 60s budget)
- Hardening suite: 9/9 tests passed in 0.83s
- Parameter sweep: best combo 93% (half-life=10, keyword-weight=0.6) vs. worst combo 51% (half-life=10, keyword-weight=0.2)
