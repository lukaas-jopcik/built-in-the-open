# Agent-Recorded Video Demos with shot-scraper

## Goal
A one-command pipeline that spins up a tiny local demo page, drives it with `shot-scraper video`, and outputs a playable video file proving an agent can generate its own demo footage unattended.

## Slices (max 4)
1. Install `shot-scraper` + Playwright's Chromium in a repo-local venv and record a video of a static built-in page (e.g. a local `hello.html`) to prove the toolchain works in this sandbox at all.
2. Build a minimal single-file demo target (`demo/app.html` served via `python -m http.server`) with 2-3 interactive elements (a button that changes text, a form field) standing in for "the feature."
3. Write a `shot-scraper` YAML script that navigates to the demo page, clicks/types through the interactive elements, and records the whole flow to `output/demo.mp4` — triggered by a single script, no manual steps.
4. Emit `output/caption.md`: a one-line LinkedIn-ready caption plus the video path and duration, auto-generated after recording.

## Success criteria
- [ ] `./setup.sh` installs `shot-scraper` and Playwright's Chromium into a repo-local venv with zero manual intervention, exit code 0
- [ ] `./record.sh` starts the local HTTP server, runs the shot-scraper script, stops the server, and exits 0 with no prompts
- [ ] `output/demo.mp4` exists, has non-zero size, and `ffprobe`-reported duration is between 3 and 30 seconds
- [ ] `output/caption.md` exists and contains the video filename and a duration string
- [ ] Full pipeline (`./setup.sh && ./record.sh`) completes in under 2 minutes on a clean checkout
- [ ] A stranger with only Python 3 + this repo can run the two commands above and get a playable video, no other setup

## Test plan
From a clean shell in the repo directory:
1. `python3 --version` — confirm Python 3 present (no other pre-req assumed).
2. `./setup.sh` — must exit 0; then `test -d .venv && .venv/bin/shot-scraper --version` should print a version.
3. `./record.sh` — must exit 0.
4. `test -s output/demo.mp4` — file exists and is non-empty.
5. `ffprobe -v error -show_entries format=duration -of csv=p=0 output/demo.mp4` — parse duration, assert `3 <= duration <= 30`.
6. `test -s output/caption.md && grep -q demo.mp4 output/caption.md` — caption references the video.
7. Re-run `./record.sh` a second time from a dirty state (output/ already populated) — must still exit 0 and overwrite cleanly (idempotency check).

## Run instructions
```bash
cd <repo>
./setup.sh          # creates .venv, pip installs shot-scraper, playwright install chromium
./record.sh         # serves demo/app.html on localhost, runs shot-scraper video, writes output/demo.mp4 + output/caption.md
open output/demo.mp4 # or: ffplay output/demo.mp4
cat output/caption.md
```

## Out of scope
- Any real product/feature — the demo target is a throwaway static HTML toy.
- Video editing, trimming, captions/subtitles burned into the video, audio narration.
- Actually posting to LinkedIn (the output is the LinkedIn-ready artifact, not the post itself).
- Multi-browser or multi-page recording, mobile viewport variants.
- CI integration or scheduled recording.

## Kill criteria
- Playwright's `chromium` fails to install or launch headless in this sandbox (missing shared libs, no network egress for the browser download) and isn't fixable within 2 iterations → stop, write up as "broke: sandbox can't run a real headless browser."
- 2 iterations pass with slice 1 (bare `shot-scraper video` on a static page) still not producing a valid video file → stop and write up.
- `shot-scraper` requires a paid API key or external network service to function (it shouldn't, per docs, but verify early) → stop immediately.
## Depth extensions (added 2026-07-06 — spend the remaining iteration budget here)
1. **Real target:** record a real flow on a real production website —
   https://www.imaketoday.com (public pages: landing → pricing, scrolls,
   hovers, at least one interactive element). Real-world messiness expected:
   async loading, network latency, cookie banners — handle them with robust
   wait_for strategies. Output: output/real-demo.mp4 (1280x800, 8–20s).
2. **Fix the limitations the evaluation caught:** (a) record.sh must verify
   the HTTP server actually bound the port and fail loudly; pick a free port
   dynamically with fallback; (b) eliminate zombie chrome processes (proper
   wait/reap or shot-scraper flags); (c) stop leaving demo.webm clutter
   unless kept intentionally.
3. **Benchmark with numbers:** run the toy AND the real-site recording N=10
   times each; table of success rate + p50/p95 duration; note every failure
   mode observed. This is the founder-facing number.
4. **Reusable mini-guide:** README.md — how to point this at YOUR product in
   <10 minutes (prereqs honestly stated: Debian/root or manual ffmpeg,
   network egress), incl. the pause-is-seconds gotcha and wait_for patterns
   for async UIs.

## Wow shot (updated 2026-07-06 — this overrides extension 1 below)
The Friday video must make a founder STOP scrolling. Design your OWN
impressive demo — do NOT just re-record the toy widget and do NOT integrate
someone else\x27s product. Direction (pick one or invent better, on-brand
burgundy/Fraunces/periwinkle, 1280x800, payoff visible in <15s):
- a live dashboard that assembles itself — panels, animated charts and
  numbers counting up from real public data, recorded as it builds
- a task board where an "agent swarm" visibly completes a queue of cards in
  parallel, finishing with a clean summary card
- terminal on the left, polished UI growing on the right — one continuous
  take of "code becomes product"
The recording of THIS is output/real-demo.mp4. Extensions 2-4 (hardening,
N=10 benchmark, README guide) still apply unchanged.
