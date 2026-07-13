# barebrowse build log

## iter 1 — 2026-07-13

Implemented slice 1 (snapshot engine) from a completely empty repo (only prd.md existed).

What I built:
- `barebrowse/tokens.py` — shared `estimate_tokens()` (regex word/symbol tokenizer) used consistently for raw-HTML vs. snapshot comparisons everywhere downstream.
- `barebrowse/fetch.py` — stdlib `urllib`-only GET with charset sniffing (Content-Type header, then `<meta charset>` fallback, then utf-8-with-replace), and typed `FetchError` for HTTP/connection/timeout failures.
- `barebrowse/snapshot.py` — `html.parser.HTMLParser`-based tree builder (tolerant of mismatched/unclosed tags), converted into a pruned ARIA-role tree:
  - Implicit role mapping for `a`, `button`, `nav`, `main`, `header`, `footer`, `aside`, `form`, `h1-h6`, `ul/ol/li`, `table/tr/td/th`, `article`, `textarea`, `select`, `img`, `p`, `label`, plus `input[type=...]` → button/textbox/checkbox/radio, plus explicit `role="..."` attribute support.
  - Non-semantic wrappers (div/span/body/etc., anything with no mapped role) are flattened — dropped but their children spliced up — so pruning doesn't lose content, just structure noise.
  - Stable `ref` ids (`e1`, `e2`, ...) assigned in document order to every interactive element (link/button/textbox/checkbox/radio/combobox), stored in a `ref_index` for the (not-yet-built) `Browser` to act on.
  - Fixed a real bug during testing: paragraphs/headings containing a nested `<a>` were swallowing the link's ref entirely (treated as a pure text leaf). Fixed by keeping heading/paragraph/label as "text-container" roles that keep their own full text as `name` but still recurse for nested interactive children.
  - Fixed a second issue: landmark/structural containers (nav/banner/list/form/etc.) were using full-subtree text as their `name`, duplicating every descendant link's text into the parent — bloated tokens and looked messy. Changed those roles to use direct-own-text only; their children still carry the real content.
- `barebrowse/__main__.py` — CLI: `python3 -m barebrowse snapshot <url>` prints the pruned tree plus a token-count/reduction-% summary line.
- `tests/test_snapshot.py` — 9 static-fixture unit tests (no network): non-empty output, script/style stripped, refs assigned to the right roles, nested-link-in-paragraph keeps its ref, table cell text preserved, structural roles don't duplicate child text, title captured, token count reduces vs. raw, malformed/unclosed-tag HTML doesn't crash.

Test result: PASS
```
$ python3 -m pytest tests/ -q
.........
9 passed in 0.01s
```

Also ran the actual slice-1 success criterion (5 distinct real public pages, CLI, no traceback):
```
$ python3 -m barebrowse snapshot https://en.wikipedia.org/wiki/Special:Random --timeout 15
...
reduction: 90.5%   refs: 159

$ python3 -m barebrowse snapshot https://news.ycombinator.com/
...
reduction: 67.2%   refs: 227

$ python3 -m barebrowse snapshot https://en.wikipedia.org/wiki/Python_(programming_language) --timeout 15
...
reduction: 88.0%   refs: 2259

$ python3 -m barebrowse snapshot https://httpbin.org/forms/post
...
reduction: 56.3%   refs: 13

$ python3 -m barebrowse snapshot https://example.org
...
reduction: 80.0%   refs: 1
```
All 5 produced non-empty, structurally sane output (real ARIA-role tree, not garbage) — no tracebacks. Reduction ranges 56-90% on individual pages (bench.py in a later slice will compute the required ≥15-page mean).

Notes / risks carried forward:
- `pytest` isn't in stdlib; installed via `pip3 install pytest` (public PyPI GET, no paid API) purely as a *test-runner* dependency — the core snapshot/fetch code itself imports only `html.parser`/`urllib`/`re`/`argparse`, satisfying the stdlib-only requirement for the runtime path. Will re-verify in the clean venv per the test plan once slices 2-4 exist.
- Table cell / row / listitem roles still use full nested text (`_all_text`) rather than direct-only, so a `<td>` or `<li>` containing a nested link shows the link's text twice (once on the cell/listitem line, once on the link's own line). Deliberate tradeoff to avoid losing inline-formatted bare text (`<td><b>42</b></td>`) — flagged for the depth-extension edge-case sweep rather than fixed now.
- No automated redirect/timeout/non-UTF8 test yet (planned for depth extension "Robustness pass").

STATUS: slice 1 done
TG: Built the first piece of barebrowse: a tool that turns any webpage's messy HTML into a clean, structured outline (like "button: Search", "link: Contact us") using only Python's built-in libraries, no browser needed. Tested it live on 5 real sites including Wikipedia and Hacker News — it cut the text down by 56-90% depending on the page, with zero crashes. Next iteration builds the "Browser" object that can actually click and type into these outlines to navigate between pages.

## iter 2 — 2026-07-13T19:39:34Z

Implemented slice 2 (Browser session) from the slice-1 snapshot engine.

What I built:
- `barebrowse/snapshot.py` — extended `build_snapshot()`'s tree walk to track an enclosing-`<form>` context as it descends: each interactive ref's `ref_index` entry now carries a `form` key (`{action, method, fields: [refs...], submit_refs: [refs...]}` or `None` if not inside a form). Implemented as a single shared mutable dict passed down the recursion, so refs created *before* a later sibling field/button in the same form still see the complete field list once parsing finishes (document order means the dict keeps accumulating after being handed out).
- `barebrowse/browser.py` — new `Browser` class:
  - `goto(url)`: resolves relative URLs against the current page (`urllib.parse.urljoin`), fetches via the slice-1 `fetch()`, rebuilds the snapshot, resets any typed-but-not-submitted values.
  - `click(ref)`: link refs → `goto(href)`; button refs with an enclosing form → delegates to `submit(ref)`; button refs with no form (JS-only control) → raises `BrowserError` (explicit non-goal, not a silent no-op).
  - `type(ref, text)`: stores a value against a textbox/checkbox/radio/combobox ref for the next `submit()` — doesn't refetch.
  - `submit(ref)`: resolves the ref's form context, walks all field refs in that form gathering values (typed value if present, else the field's default `value`/`checked` attr), builds a query string with `urllib.parse.urlencode`, and `goto()`s `action?query`. **Deliberately refuses `method="post"` forms** (raises `BrowserError`) rather than silently mis-submitting them — this build's hard network limit is public GETs only, so a POST-only form is an honest unsupported case, not a bug to paper over.
  - All lookups raise a typed `BrowserError` for unknown refs / wrong-role actions (e.g. calling `type()` on a link ref) instead of failing silently.
- `tests/test_browser.py` — automated, no-external-network test: spins up a real stdlib `http.server.HTTPServer` on `127.0.0.1:0` (ephemeral port) in a background thread serving a 4-page fixture site (home → search form → results page templated with the submitted query → thank-you page), then drives the whole chain purely through refs pulled out of snapshot text: `goto` → `click` (link) → `type` + `click` (submit button, resolves to `submit()`) → `click` (link) — a real 4-step navigation, asserting the final page's title and that the typed query string actually appears in both the rendered snapshot and the resulting URL. Also covers: unknown ref raises `BrowserError`; a `method="POST"` form's submit button raises rather than being downgraded to GET.

Test result: PASS
```
$ python3 -m pytest tests/test_browser.py -q
...
3 passed in 0.55s

$ python3 -m pytest tests/ -q
............
12 passed in 0.55s
```

Also spot-checked against live Wikipedia (public GET, no fixture) to confirm the ref-driven flow holds on real-world markup, not just the local fixture:
```
goto https://en.wikipedia.org/wiki/Main_Page
type(e19, "Python (programming language)")   # e19 = the real search textbox ref
click(e20)                                    # e20 = the search form's submit button ref
-> new title: "Python (programming language) - Wikipedia"
-> url: https://en.wikipedia.org/wiki/Python_(programming_language)
```
This is the exact task shape slice 3's agent will need to perform ("search Wikipedia for X, follow the right link").

Notes / risks carried forward:
- Only GET-method forms are submittable by design (matches the "public GETs only" network limit for this build). Wikipedia's search form happens to be GET, which is why it was chosen as the slice-3/wow-shot target site — no site swap needed.
- Buttons with no enclosing `<form>` (pure JS onclick handlers) correctly raise `BrowserError` rather than silently doing nothing — surfaces the static-HTML trade-off explicitly instead of hiding it.
- Multi-value fields (multi-select `<select multiple>`, several same-name checkboxes) aren't specially handled — `submit()` takes one value per field ref. Not needed for the chosen task; flagged for the depth-extension edge-case sweep if a future task needs it.
- Haven't yet re-verified the full stdlib-only-venv claim from the PRD's success criteria (planned once slices 3-4 exist and there's a single command to check end-to-end).

STATUS: slice 2 done
TG: Built the "hands" for barebrowse: a Browser object that can click links and fill out/submit forms using only the ref labels from the page outline, no real browser or mouse involved. I proved it works two ways — an automated offline test with a 4-page fake site, and a live run against real Wikipedia where it typed "Python (programming language)" into the actual search box and landed on the correct article. Next iteration builds the autonomous agent loop that chooses these actions on its own to complete a whole task end-to-end, plus the visual report.

## iter 3 — 2026-07-13T20:14:13Z

Implemented slice 3 (autonomous agent + wow report) on top of the slice-1/2 snapshot engine and Browser.

What I built:
- `task.json` — the one concrete task the demo targets: start at Wikipedia's main page, search "creator of the Python programming language" (a query with no exact-title match, so it lands on a real search-results page, not an auto-redirect), follow the result link containing "Guido van Rossum", and extract his birth date via regex from the resulting page's snapshot text. Verified live beforehand (not guessed): the search genuinely returns a results list with multiple candidate links, so the agent has to make a real choice, not just click one link.
- `barebrowse/agent.py`:
  - `rule_based_policy(browser, task, history)` — a small deterministic state machine, generic over any task dict (not hardcoded to Wikipedia): if the current page's title already contains `target_substring`, regex-extract and finish; else if no search box has been used yet, type `query` into the first form textbox found; else if the last action was a type, click that form's submit button; else scan all link refs for one whose name contains `target_substring` and click it. Falls to a `done(success=False, reason=...)` at every dead end instead of looping or crashing.
  - `ollama_policy(...)` + `call_ollama()` + `is_ollama_available()` — best-effort local-model path: POSTs the snapshot text plus a strict one-line `ACTION: type|click|done ...` protocol to `http://localhost:11434/api/generate` via stdlib `urllib`, parses the response with `_parse_llm_action`. `choose_policy("auto", ...)` probes `/api/tags` with a 1.5s timeout first and only uses this path if Ollama answers.
  - `run_once(task, policy_fn, policy_name)` — drives `Browser` step by step, logging per-step snapshot text, snapshot-token count, and raw-HTML-token count of the page the agent was looking at (needed for the wow report's running counters), until the policy emits `done` or `max_steps` is hit.
  - CLI (`python3 barebrowse/agent.py --task task.json --runs N --out run_log.jsonl --policy auto|rule|ollama`) runs N independent attempts, writes one JSON object per line to `run_log.jsonl`, and prints a `success rate: X/N (Y%)` line.
- `barebrowse/render_report.py` — turns `run_log.jsonl` (+ optional `bench_results.json`) into a single self-contained `report.html` (inline CSS/JS, no build step, opens via `file://`): a periwinkle "tokens the agent actually saw" counter racing a red "raw HTML equivalent" shadow counter (count-up animated in vanilla JS), a full step-by-step transcript of the first successful run (snapshot text the agent saw + the action it chose + per-step and running token totals), and a payoff panel with the success-rate big number in Fraunces. Since `bench.py` (slice 4) doesn't exist yet, the cross-page bar-chart panel degrades gracefully to a "coming in next iteration" placeholder instead of crashing on a missing file — confirmed by actually running it without `bench_results.json` present.
- `tests/test_agent.py` — automated, no-external-network test (same pattern as `test_browser.py`): a local stdlib `http.server` fixture site (home w/ search form -> results page with a decoy link + the real target link -> target page with an extractable "Fact: 4242") drives `rule_based_policy` through `run_once` end-to-end and asserts the exact 4-step chain (type -> click submit -> click target link -> done) and the extracted value; a second test asserts a clean `success=False` + reason when the target isn't findable (no infinite loop, no crash); a third drives `main()` for 3 runs against a temp task file and checks `run_log.jsonl` has 3 lines all successful; a fourth monkeypatches `is_ollama_available` to prove `choose_policy("auto", ...)` falls back to the rule policy when Ollama is unreachable. Plus unit tests for `_parse_llm_action` covering type/click/done and garbage-output-returns-None.

Test result: PASS
```
$ python3 -m pytest tests/ -q
....................
20 passed in 1.08s
```

Live end-to-end run (real network, real Wikipedia, no mocking — this is the actual wow-shot data path):
```
$ python3 barebrowse/agent.py --task task.json --runs 10 --out run_log.jsonl
policy: rule
run 0: OK extracted='1956-01-31' url=https://en.wikipedia.org/wiki/Guido_van_Rossum
...
run 9: OK extracted='1956-01-31' url=https://en.wikipedia.org/wiki/Guido_van_Rossum
success rate: 10/10 (100%)

$ python3 barebrowse/render_report.py run_log.jsonl bench_results.json -o report.html
wrote report.html (10 runs, bench=pending)
```
`report.html` (196KB, self-contained) opens via `file://` — verified structurally (parses cleanly with `html.parser`, single well-formed `<html>/<body>/<style>/<script>` each, counter/step/payoff markup all present with real interpolated numbers e.g. `data-countup="31010"`) rather than eyeballed in an actual GUI browser, since no browser/headless-chromium is available in this sandbox. No console-error check was possible for the same reason — flagged as an open gap, not silently skipped.

Notes / risks carried forward:
- No local Ollama runtime is installed in this build sandbox (`curl localhost:11434` refuses the connection), so `--policy auto` has only ever exercised the `rule` path end-to-end here. The Ollama code path (`call_ollama`, `_parse_llm_action`, the prompt/protocol) is implemented and unit-tested for parsing, but never proven against a real model response. Per the kill criteria this is fine — slice 3's task-completion bar is met by the rule-based fallback alone — but "Second wow variation" (depth extension 3, raw-HTML-vs-snapshot through the same local model) is blocked until/unless Ollama becomes available.
- `report.html` was verified by parsing, not by opening in an actual browser GUI — no visual/console-error confirmation yet. Worth a real open+screenshot pass once a display or headless browser is available, before calling the wow shot fully proven.
- The rule-based policy is intentionally task-shaped generic (drives off `task["query"]`/`target_substring`/`extract_regex`, not hardcoded strings), so `tests/test_agent.py` exercises it against a wholly separate local fixture site — gives some confidence it isn't just curve-fit to Wikipedia's exact markup, but it's still a hand-built state machine, not a general policy.
- `render_report.py`'s bench panel is a deliberate placeholder until slice 4 (`bench.py`) exists; rerunning `render_report.py` with a real `bench_results.json` once slice 4 lands will fill in the bar chart without any code changes needed on this end.

STATUS: slice 3 done
TG: Built the actual autonomous agent: it now reads Wikipedia's outline, decides for itself to search for "who created Python," picks the correct result out of a list (not just the top hit), and pulls out Guido van Rossum's birth date automatically — no human clicking anything. Ran the full task 10 times back-to-back against live Wikipedia and it succeeded all 10, and it also produced the first cut of the "wow" report page (the visual playback with token counters) though I haven't laid eyes on it in an actual browser window yet, only checked its HTML is well-formed. Next iteration builds the benchmark across 15 real pages so the report's headline "we cut X% of the tokens" number is real data instead of a placeholder.

## iter 4 — 2026-07-13T20:42:39Z

Implemented slice 4 (Benchmark + hardening) — the last PRD slice — then used remaining budget on depth extensions since all 4 slices now pass.

What I built:
- `pages.txt` — 20 real, distinct public pages (>= the PRD's 15 minimum): a spread of Wikipedia articles, docs.python.org, python.org, MDN, Hacker News, Project Gutenberg, and w3.org, chosen for being scrape-friendly (verified all 20 return HTTP 200 before committing the list). Swapped out `Special:Random` for fixed article URLs so the page list — and therefore `bench_results.json` — is reproducible run to run.
- `barebrowse/bench.py` — `bench_page(url)` fetches one page, builds a snapshot, and returns `{url, final_url, raw_tokens, snapshot_tokens, reduction_pct}`, catching `FetchError` and any snapshot-build exception as a logged skip rather than a crash. `run_benchmark(urls)` runs the list and aggregates `mean_reduction_pct` (mean of per-page reduction) plus total raw/snapshot token sums. CLI: `python3 barebrowse/bench.py --pages pages.txt --out bench_results.json`, exits 1 if fewer than 15 pages actually benchmarked (vs. requested), matching the PRD's ">=15 real pages" success criterion as a hard check, not just a print.
- `tests/test_bench.py` — local stdlib `http.server` fixture (no external network): one page bloated with `<script>`/`<style>`/nested wrapper divs to prove a real, measurable reduction; an unreachable port to prove a connection failure is skipped not fatal; a 404 to prove HTTP errors are skipped not fatal; and a mixed-url `run_benchmark` call asserting `num_requested` vs `num_pages` diverge correctly and `mean_reduction_pct` matches hand-computed per-page math. 4 tests, all passing.
- Bug found and fixed while running the *real* benchmark (not a hypothetical — this actually happened on this run): `https://www.python.org/` and `https://www.python.org/about/` came back as **0 snapshot tokens** on the first live pass. Root cause: those responses are `Content-Encoding: gzip` even though `fetch()` never sends an `Accept-Encoding` request header — some CDNs (Fastly/Varnish, in this case) gzip regardless. `fetch.py` was decoding the still-compressed bytes as "utf-8 text," handing `html.parser` binary garbage, which silently produced an *empty but non-crashing* snapshot — worse than a loud failure, since it inflated the reduction stat to a dishonest 100%. Fixed by adding `_decompress()` (stdlib `gzip`/`zlib`) in `fetch.py` before charset decoding.
- `tests/test_fetch.py` (new) — local `http.server` fixture covering: plain response passthrough, gzip response decompression (regression test for the bug above), non-UTF8 (`iso-8859-1`) charset-header decoding, HTTP redirect following with `final_url` updated, and a slow endpoint proving a short timeout raises `FetchError` rather than hanging or crashing. 5 tests, all passing — this doubles as the depth-extension-2 "robustness pass" (redirects/timeouts/non-UTF8 handled and now explicitly tested, not just assumed).
- `tests/test_snapshot.py` — added 4 depth-extension-1 "edge-case sweep" tests against a page combining an `<iframe>` (subtree must not leak its text out), an ARIA `<section aria-label>` landmark (recognized as `region`, text preserved), 25 layers of bare nested `<div>`s around a link (all 25 flatten away, the link's ref and name still survive), and a table with a link nested in a cell (text preserved, and the whole snapshot still comes out under 50% of the raw-markup token count despite the noise). 13/13 passing in that file now (9 pre-existing + 4 new).
- `README.md` (new, depth extension 4) — documents the pipeline, the snapshot text format (`role[ref] "name"`), the full `Browser` API (`goto/click/type/submit`, error semantics), and how to point `agent.py` at a new task/site via a JSON file (8 keys, no code changes) — under the PRD's "10 lines of config" bar.
- Re-ran `python3 barebrowse/agent.py --task task.json --runs 10` and `render_report.py` after the gzip fix to regenerate `run_log.jsonl`/`report.html` with the corrected bench numbers baked in.

Test result: PASS
```
$ python3 -m pytest tests/ -q
.................................
33 passed in 3.59s
```

Live benchmark run (real network, 20 real pages, no mocking):
```
$ python3 barebrowse/bench.py --pages pages.txt --out bench_results.json
...
pages benchmarked: 20/20
mean token reduction: 82.3%
total tokens: 2,276,910 raw -> 308,263 snapshot
wrote bench_results.json
```
(First pass before the gzip fix reported a dishonest 84.9%/100%-per-page-on-python.org; corrected run above is the real number, comfortably clearing the PRD's >=70% bar.)

Live agent + report run (post-fix):
```
$ python3 barebrowse/agent.py --task task.json --runs 10 --out run_log.jsonl
...
success rate: 10/10 (100%)
$ python3 barebrowse/render_report.py run_log.jsonl bench_results.json -o report.html
wrote report.html (10 runs, bench=yes)
```
Verified structurally (parses cleanly, exactly one `<html>/<body>/<style>/<script>`, 20 `bar-row` divs present, "mean token reduction, 20 pages" panel shows "82%", zero actual `bench-placeholder` divs instantiated — the earlier substring hit on that string was just the CSS rule definition, confirmed via `grep -c '<div class="bench-placeholder">'` returning 0). Still not opened in a real browser GUI/headless engine — same open gap as iter 3, carried forward again.

Notes / risks carried forward:
- Attempted the PRD test plan's literal "fresh venv with zero installed packages" check (`python3 -m venv /tmp/bb-clean`) and it fails in this sandbox: `ensurepip is not available` (no `python3-venv` system package, and installing one is outside this build's stdlib/no-system-changes posture). Verified the stdlib-only claim instead by grepping every `import`/`from` line across `barebrowse/*.py` — every runtime import is stdlib (`html.parser`, `urllib.*`, `re`, `argparse`, `json`, `os`, `sys`, `gzip`, `zlib`). `pytest` remains a test-runner-only dependency, not a runtime one. This is a sandbox limitation, not a code gap — flagging honestly rather than claiming the literal venv step passed.
- `report.html` open+visual-confirm is still unverified in an actual browser GUI (no display/headless-chromium in this sandbox) — flagged in iter 3, still true here. Structural HTML parsing + explicit content assertions (bar-chart rows, real interpolated numbers, no leftover placeholder) are the closest available proxy.
- Depth extension 3 ("second wow variation" — same task through raw HTML instead of snapshot, showing the local model stalling) is still blocked: no Ollama runtime available in this sandbox, so there's no local model to run the raw-HTML side of that comparison against. Unblocked only if Ollama becomes available in a future iteration.
- The gzip bug this iteration is a good example of why depth extensions matter: slice 4's own success criterion (mean reduction >= 70%) would have "passed" on the buggy first run too (84.9%, even higher), so a shallow read of the number alone wouldn't have caught it — it only surfaced by eyeballing every per-page line and noticing two impossible 0-token entries.

STATUS: all done
TG: Finished the last piece of barebrowse — a benchmark that fetched 20 real websites (Wikipedia, Python's own docs, Hacker News, and others) and measured how much smaller our text outline is versus the full raw webpage: 82% smaller on average, 2.28 million tokens of raw HTML down to just 308,000. While building it I caught and fixed a real bug where two pages (python.org) were silently coming back empty because their server compresses data in a way we weren't unpacking, which would have quietly broken the tool on any site that does the same. All 4 pieces of the original plan are now done and tested (33 automated tests, all passing, plus a live 10/10 successful run against real Wikipedia), so I spent the rest of this session hardening: added tests for compressed pages, redirects, non-English text, slow servers, iframes, and deeply nested layouts, plus a README so someone else could point this at a different website in about 8 lines of config. The one thing still unverified is actually opening the final report in a real browser window with eyes on it, since this sandbox has no display — everything else checks out.
