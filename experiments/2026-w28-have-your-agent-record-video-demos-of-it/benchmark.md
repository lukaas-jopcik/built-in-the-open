# Benchmark — toy widget vs. wow-shot swarm demo

N=10 back-to-back runs each, same sandbox, warm Chromium/ffmpeg cache
(cold-download timing was not re-measured this session — see
`evaluation.md`, which already flagged this as unverified in this sandbox).

**Note:** the "real" recording target changed mid-build. The PRD's original
depth extension asked to record a real external site (imaketoday.com); a
later PRD update ("Wow shot", 2026-07-06) explicitly overrode that — no
third-party product, no external network dependency for the payoff shot,
an original on-brand demo instead. `real-record.sh` now records
`demo/swarm.html`, a self-contained "agent swarm" task board (6 cards
animate queued → running → shipped in parallel, ending on a summary card),
not imaketoday.com. The numbers below are for that swarm demo; the retired
imaketoday numbers are kept at the bottom for context.

## Toy demo (`./record.sh` → `output/demo.mp4`, local static widget)

| Metric | Value |
|---|---|
| Success rate | 10/10 (100%) |
| Wall time p50 | 6.77s |
| Wall time p95 | 6.83s |
| Video duration p50 | 5.04s |
| Video duration p95 | 5.04s |

## Wow-shot swarm demo (`./real-record.sh` → `output/real-demo.mp4`, local `demo/swarm.html`)

| Metric | Value |
|---|---|
| Success rate | 10/10 (100%) |
| Wall time p50 | 11.83s |
| Wall time p95 | 11.90s |
| Video duration p50 | 9.28s |
| Video duration p95 | 9.32s |

Both targets were near-perfectly deterministic run-to-run (video duration
varied by at most 0.04s across 10 runs each) — expected, since both pages
drive their own animation timing with fixed `setTimeout` schedules and
neither depends on an external network fetch or a third party's render
time. This is a meaningful reliability improvement over the retired
imaketoday-based benchmark below, whose numbers depended on a live site's
response time and DOM structure outside this repo's control.

## Failure modes observed

- **None triggered a hard failure in this N=10 x 2 run.** Both storyboards
  completed successfully every time.
- **Confirmed process leak (not a per-run failure, but an accumulating
  resource leak):** every `shot-scraper video` invocation leaves ~2-3
  defunct `[chrome-headless]` zombie processes reparented to PID 1. After
  the 20 `shot-scraper` invocations in this N=10 x 2 benchmark (on top of
  prior manual testing this session), `ps aux` showed 50+ zombies
  accumulated — i.e. PID 1 in this sandbox is not reaping them. Not fixable
  from inside `record.sh`/`real-record.sh` (a process can only `wait()` on
  its own children, and by the time these are visible they've already been
  reparented away). See `README.md` for the standard mitigation (run under
  `tini`/`dumb-init` or `docker run --init`) — a container/init-layer fix,
  not a repo-layer one.

## Retired: imaketoday.com benchmark (superseded)

An earlier version of this file benchmarked `real-record.sh` against
`https://www.imaketoday.com`: 10/10 success, 14.66s p50 wall time, 11.68s
p50 video duration, every run identical because the site's pricing page was
edge-cached/prerendered (`x-nextjs-cache: HIT`). That target was replaced by
the on-brand swarm demo above per the PRD's "Wow shot" direction, which
explicitly rules out embedding someone else's product in the payoff
recording. The one lesson from that attempt worth keeping is preserved in
`README.md`'s integration guide — Playwright strict-mode selector
violations on pages that repeat nav/footer links (e.g. `a[href='/pricing']`
matching a nav link, a hero CTA, and a footer link all at once) — since
it's still the most common gotcha when pointing this technique at a real
external product.

## Founder-facing number

Once the toolchain is installed, generating the on-brand wow-shot demo clip
costs about **12 seconds of wall time and $0 in API spend**, with a 100%
success rate across 20 back-to-back attempts (10 toy + 10 swarm) in this
sandbox — and because the swarm demo owns its own timing instead of
depending on a real website's load time, that reliability number isn't at
the mercy of a network hiccup or a third party changing their page. The
remaining risk isn't reliability of any single recording, it's the slow
zombie-process leak on a host that never reaps children, which matters for
anyone running this in a tight loop (e.g. one recording per PR in CI)
rather than a handful of times a day.
