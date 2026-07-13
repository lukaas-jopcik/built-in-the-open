# MiniCrawl Dashboard

## Goal
Build a tiny, self-contained, zero-dependency (Python stdlib only) alternative to a
"Firecrawl"-style scrape API: fetch a small list of public sites, extract simple
metrics (title, word count, link count, image count), snapshot each run to disk,
diff consecutive runs, and render a static HTML dashboard that visualizes what
changed since last time.

## Wow shot
Run `python3 crawl.py` twice (a day apart, or twice in a row for a demo), then open
`dashboard.html` in a browser: big aggregate numbers ("5 sites tracked", "12,340
words scraped", "7 changes since last run") animate counting up from 0, and below
them a per-site table shows green "+" rows for new links and red "-" rows for
removed links, plus word-count deltas per site. It should feel like a live
"what changed on the internet since I last looked" report, built from nothing but
`urllib` and `html.parser`.

## Out of scope
- No real Firecrawl API usage, no API keys, no paid services.
- No JS-rendered/SPA scraping (no headless browser) — plain HTML fetch + parse only.
- No database — flat JSON snapshot files on disk.
- No auth, no crawling behind logins, no pagination/crawling beyond the seed URL list.
- No third-party pip packages (requests, bs4, etc.) — stdlib only (`urllib.request`,
  `html.parser`, `json`, `http.server` for tests).

## Slices (build in order, each independently testable)

### Slice 1 — Fetch + parse + snapshot
`lib/fetcher.py`: `fetch(url)` does an HTTP GET via `urllib.request` and parses the
HTML with `html.parser.HTMLParser` (no deps) to return: title, word_count,
link_count, image_count, sorted unique links, byte size, HTTP status.
`lib/store.py`: `save_snapshot(results)` writes a timestamped JSON file under
`data/runs/`; `list_snapshots()` / `load_snapshot()` read them back.
`crawl.py`: CLI that loads `sites.json` (list of seed URLs), fetches each with the
above, saves a snapshot, and prints a one-line summary per site.

**Binary success criteria:** running `python3 crawl.py` against the 5 URLs in
`sites.json` produces a new file in `data/runs/` containing a JSON object with a
`sites` array of length 5, where every entry has non-error `word_count > 0` for at
least 4 of 5 sites (allowing one flaky public site).

**Test plan:** `tests/test_fetcher.py` spins up a local stdlib `http.server` with
known fixture HTML and asserts `fetch()` extracts the exact expected title, link
count, and image count (deterministic, no real network needed for this test).
Run: `python3 -m unittest discover -s tests -v`.

### Slice 2 — Diff engine
`lib/diff.py`: `diff_snapshots(old, new)` compares two snapshot dicts by URL and
returns, per site: `added_links`, `removed_links`, `word_count_delta`,
`title_changed` (bool), plus an aggregate `total_changes` count across all sites.

**Binary success criteria:** diffing two identical snapshots yields
`total_changes == 0`; diffing a snapshot against a synthetic mutated copy (extra
link added, word count changed) yields `total_changes > 0` with the specific
added link present in `added_links` for that site.

**Test plan:** `tests/test_diff.py`, pure unit tests on in-memory dicts (no
network/filesystem). Run: `python3 -m unittest tests.test_diff -v`.

### Slice 3 — Dashboard generator
`lib/dashboard.py`: `render(snapshot, diff, out_path)` writes a single
self-contained `dashboard.html` (inline CSS/JS, no external assets) that:
- shows aggregate stat cards (sites tracked, total words, total links, total
  changes) with a vanilla-JS count-up animation from 0 to the final value,
- shows a per-site table with green/red diff rows for added/removed links and a
  ± word-count delta,
- degrades gracefully (renders "no prior run to diff" state) on the very first
  run when there is no previous snapshot.

**Binary success criteria:** the generated `dashboard.html` file (a) is valid
enough to parse without error via stdlib `html.parser`, (b) contains a
`<script>` block with the count-up logic, and (c) contains the exact aggregate
numbers computed from the snapshot/diff data passed in (checked via a marker
`data-*` attribute, not by parsing rendered pixels).

**Test plan:** `tests/test_dashboard.py` renders with a small fixed
snapshot+diff fixture and asserts the expected numbers appear in specific
`data-value="N"` attributes in the output HTML. Run:
`python3 -m unittest tests.test_dashboard -v`.

### Slice 4 — End-to-end CLI + resilience polish
Wire `crawl.py` to run fetch → snapshot → diff-against-previous → render
dashboard in one command. Add: per-site timeout + one retry, graceful
skip-and-continue on fetch failure (never crash the whole run), and a
`--sites`/`--out` CLI flags with sane defaults.

**Binary success criteria:** `python3 crawl.py` run twice in a row (no
network changes expected) exits 0 both times, produces two snapshot files,
and produces a `dashboard.html` whose "changes since last run" number is a
small number (ideally 0) rather than crashing or reporting all-sites-as-new.

**Test plan:** `tests/test_e2e.py` runs `crawl.py` as a subprocess twice
against a local fixture server (not real internet, for determinism) and
asserts exit code 0 both times and that `dashboard.html` exists and
references two distinct snapshot timestamps. Run:
`python3 -m unittest tests.test_e2e -v`.

## Run instructions
```
python3 crawl.py                 # fetch sites.json, snapshot, diff, render dashboard.html
open dashboard.html               # (or: python3 -m http.server, then visit in browser)
python3 -m unittest discover -s tests -v   # run all tests
```

## Kill criteria
- If the sandbox has no outbound network access at all (public GET fails to
  every reachable host, verified with `example.com`) — kill, since the whole
  premise requires fetching real pages. (Verified NOT the case as of 2026-07-13:
  `urllib.request.urlopen("https://example.com")` returns HTTP 200.)
- If stdlib `html.parser` cannot be coaxed into surviving malformed real-world
  HTML without try/except around `feed()` (i.e. it crashes unrecoverably even
  with error handling) — kill, since there's no dep-free fallback.

## Depth extensions (once all 4 slices pass and iterations remain)
1. **Historical trend**: once 3+ snapshots exist, add a tiny inline sparkline
   (SVG, no libs) per site showing word-count over time, not just last-vs-prev.
2. **Resilience hardening**: exponential backoff retry, per-site configurable
   timeout, redirect-loop guard, non-HTML content-type skip (don't try to parse
   a PDF/image response as HTML).
3. **Bigger wow shot**: add a "health score" per site (e.g. 100 minus penalties
   for fetch errors/timeouts across recent runs) shown as a badge, and a
   "biggest mover" callout card (site with largest word-count swing).
4. **Benchmark**: a `bench.py` that times fetch+parse+diff+render for the
   full site list and asserts it stays under a wall-clock budget (e.g. 30s for
   5 sites), logged in build-log.md with the actual number each iteration it
   changes.
