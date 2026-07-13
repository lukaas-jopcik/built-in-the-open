# Evaluation — MiniCrawl Dashboard

## Verdict: worked

## Depth: adequate — it was exercised against real live sites (not just fixtures) and caught one genuine real-world bug (gzip), but the "sites" are all simple, cooperative, non-JS documentation/demo pages, and no quantified comparison to real Firecrawl exists.

## Criteria
- [x] `python3 crawl.py` produces a snapshot file with a `sites` array of length 5, ≥4/5 non-error `word_count > 0` — evidence: fresh run produced `data/runs/20260713T161538453289.json`, output showed `5/5 sites fetched successfully` (all 5 succeeded this run; PRD only requires 4/5).
- [x] Diff engine: identical snapshots → `total_changes == 0`; mutated snapshot → `total_changes > 0` with the specific link in `added_links` — evidence: `tests/test_diff.py`, 6/6 passing (`test_identical_snapshots_have_zero_changes`, `test_mutated_snapshot_flags_added_link_and_word_delta`).
- [x] `dashboard.html` parses via `html.parser`, contains a `<script>` with count-up logic, contains exact aggregate numbers via `data-value` — evidence: ran `HTMLParser().feed()` against the real generated file with no exception; found `requestAnimationFrame: True`; found `data-metric="sites_tracked" data-value="5"`, `total_words 2162`, `total_links 274`, `total_changes 0` matching computed data.
- [x] `crawl.py` run twice in a row exits 0 both times, two snapshot files, small "changes since last run" — evidence: two fresh consecutive runs, both `EXIT: 0`, second run printed `Changes since last run: 0`; `data/runs/` now holds 6 files with distinct microsecond timestamps.
- [x] Full test suite passes — evidence: `python3 -m unittest discover -s tests -v` → `Ran 24 tests in 1.226s / OK` (fetcher, diff, dashboard, health, e2e all green), run fresh in this session.
- [x] No outbound-network kill criterion avoided — evidence: `urllib.request.urlopen("https://example.com")` → 200 in this sandbox.
- [x] Graceful degradation on fetch failure — evidence: fetching a 404 and a connection-reset URL both raise cleanly and are caught by `fetch_with_retry`; a prior e2e test also confirms an unreachable site doesn't crash the run (`1/2 sites fetched successfully`, dashboard still written).

## What broke / limitations
- Nothing broke in this session — every documented success criterion held on a fresh run, not just against the log's historical claims.
- **Not a real Firecrawl substitute, and the PRD says so up front**: no JS rendering (pure `urllib` + `html.parser`), no crawling beyond the seed list (single page per site, no link-following/pagination), no markdown/structured extraction, no proxy/anti-bot handling, no LLM-based extraction.
- **No `robots.txt` respect or rate limiting** — `fetch_with_retry` retries immediately with no backoff; hitting real third-party sites repeatedly (e.g. on a cron schedule) with no politeness delay is the kind of thing that gets an IP blocked at any real scale.
- **No brotli decompression** — `lib/fetcher.py` only handles `gzip`/`deflate` `Content-Encoding`. I could not trigger a brotli response in this sandbox (Cloudflare-fronted `react.dev`/`cloudflare.com`/`vercel.com` all returned unencoded HTML), so this is an untested but real gap: any CDN that force-serves brotli regardless of `Accept-Encoding` (the same behavior the code already had to work around for python.org's gzip) would hand the parser raw compressed bytes decoded as `errors="replace"` UTF-8 garbage, silently producing near-0 word/link counts rather than an error.
- **No concurrency** — sites fetch strictly sequentially; 5 sites took 0.667s wall-clock end-to-end here, but with a default `timeout=10` and `retries=1`, a list of even 20-30 real-world sites with a couple of slow/dead ones could take minutes per run, not seconds. This is fine for a 5-site demo, not for a "many sites" product.
- **Unbounded local storage** — every run adds a new full JSON snapshot to `data/runs/`, no retention/pruning; fine for a demo, would need cleanup for continuous use.
- **Depth extensions from the PRD's own roadmap are incomplete**: the historical sparkline (#1) and the `bench.py` wall-clock benchmark (#4) were never built (confirmed: no `bench.py` file exists, no sparkline code in `lib/dashboard.py`), despite the build log flagging both as "next" after iteration 5. Iteration stopped at 5 of a stated 4+ roadmap.
- Word count is a crude `str.split()` token count (after stripping `<script>`/`<style>` text), not a linguistically meaningful metric — fine for "did this page change" drift-detection, misleading if presented as a real content metric.
- Repo has zero git commits (everything still staged) — not a code defect, but worth noting if "done" means shippable/reviewable state.

## Founder translation
This is a solid, free, no-API-key script that checks up to a handful of your own or competitors' web pages, remembers what they looked like last time, and shows you a nice dashboard of what changed (word count, links, title) — genuinely useful for "did my competitor update their pricing page" style monitoring, and it runs in under a second for 5 sites with zero ongoing cost. But it is not a scraping product: it can't handle JavaScript-heavy sites (most modern app dashboards, single-page apps), doesn't crawl beyond one page per site, has no politeness/rate-limiting so hammering many external sites on a schedule risks getting blocked, and hasn't been proven at any scale beyond 5 friendly demo/documentation pages. Treat it as a personal "did this specific page change" alert tool, not a Firecrawl replacement — using it to actually replace a paid scraping API would take real additional engineering (JS rendering, scale, politeness, storage cleanup).

## Numbers
- 24/24 tests passing in 1.226s (`python3 -m unittest discover -s tests -v`).
- 5/5 real public sites fetched successfully in 0.667s wall-clock (fresh run, this session).
- 2,162 total words / 274 total links aggregated across the 5 tracked sites, `total_changes = 0` on a same-day re-run (correctly detecting no drift).
