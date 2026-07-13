# Agent-recorded video demos (shot-scraper)

An agent can drive a real (headless) browser through your product and
export a real MP4 + a LinkedIn-ready caption, with zero manual screen
recording. This repo is the proof-of-concept; this file is how to point it
at *your* product in under 10 minutes.

## What's here

- `setup.sh` — one-time: creates `.venv`, installs `shot-scraper`, downloads
  Playwright's Chromium, checks for `ffmpeg`.
- `record.sh` / `demo/storyboard.yml` — records the toy local demo
  (`demo/app.html`) to `output/demo.mp4`.
- `real-record.sh` / `demo/real-storyboard.yml` / `demo/swarm.html` — the
  wow-shot demo: an on-brand "agent swarm" task board where six cards ship
  in parallel, ending on a summary card, recorded to `output/real-demo.mp4`.
  This used to record a real external site (imaketoday.com's landing →
  pricing flow); the PRD's "Wow shot" direction later overrode that — no
  third-party product and no external network dependency in the payoff
  shot, an original demo instead. See "Pointing this at your own product"
  below for how to swap in a *real* external site if that's what you need.
- `benchmark.md` — N=10 success-rate/timing numbers for both.

## Honest prerequisites

The PRD's "just Python 3" framing undersold this — here's what's actually
required:

- **Python 3** with the stdlib `venv` module available. On Debian/Ubuntu
  this is sometimes a separate `python3-venv` package; `setup.sh` will try
  to `apt-get install` it automatically **only if you're root on a
  Debian/Ubuntu-family box**. On macOS, Windows, non-Debian Linux, or as a
  non-root user, and `venv` is missing, you'll need to install it yourself
  first — `setup.sh` will fail with a clear message rather than hanging.
- **A system `ffmpeg` binary on `PATH`.** `shot-scraper video --mp4` shells
  out to it for WebM→MP4 transcoding (this is separate from the ffmpeg
  Playwright bundles for its own use). Same auto-install caveat as above:
  automatic only for root on Debian/Ubuntu; otherwise `brew install ffmpeg`
  / your distro's package manager / manual download.
- **Network egress** to PyPI (`pip install shot-scraper`) and to
  `cdn.playwright.dev` (~150MB+ Chromium download, one-time). If your
  network blocks either, `setup.sh` will fail during that step.
- **A container/init that reaps zombie processes**, if you're running this
  in a loop (CI, one recording per PR, etc.) — see "Known limitation" below.

None of this needs a paid API key or account signup; everything above is a
one-time local/system setup cost, not a per-recording cost.

## Pointing this at your own product

This repo's own `real-record.sh` now targets a local, self-contained page
(`demo/swarm.html`) rather than a live external site, on purpose — see
"What's here" above. The steps below are for when *you* want to point this
technique at your actual product, which is very likely a real external
site.

1. **Write your own storyboard**, copying `demo/real-storyboard.yml` as a
   template. Key fields:
   ```yaml
   url: https://your-product.example.com/
   viewport: {width: 1280, height: 800}
   cursor: true          # draws a simulated mouse cursor — much more
                          # watchable than actions happening with no cursor
   wait_for: "selector"   # wait for a real signal the page has rendered
                          # before recording starts (not a fixed sleep)
   scenes:
     - name: some scene
       do:
         - click: "selector"
         - type: {into: "selector", text: "..."}
         - wait_for: "selector:has-text('...')"
         - pause: 1.5     # SECONDS, not ms — see gotcha below
   ```
2. **Run it once manually first** to find your real selectors — don't guess
   from memory of the DOM, `curl` the page (or run
   `.venv/bin/shot-scraper video yourboard.yml` once and read the error) and
   check for ambiguous matches before committing to a selector.
3. **Iterate on failures out loud.** The two real failure modes we hit
   building the original `real-demo.mp4` extension against a live site
   (imaketoday.com, before the wow-shot pivot to a local demo) — still the
   two things most likely to bite you against any real external product:
   - **Strict-mode selector violations.** Playwright's `click`/`wait_for`
     refuse to act when a selector matches more than one element (e.g.
     `text=YourLogo` matching the header logo *and* a footer logo *and* a
     copyright line) — it fails loudly rather than silently clicking the
     wrong thing. Fix: scope to a parent landmark, e.g.
     `header a[href='/pricing']` instead of a bare `a[href='/pricing']`.
   - **Async/loading states.** Real product pages fetch data after initial
     load (spinners, skeleton screens). Never use a fixed `pause:` to wait
     for content to appear — use `wait_for: "selector"` with a selector that
     only exists once the real content has rendered (e.g. wait for the
     actual heading text, not just "the page responded").
4. **Run it:** `.venv/bin/shot-scraper video yourboard.yml --mp4 -o output/yours.webm`.
   If you're hitting a live network dependency you don't control, wrap the
   call in a retry loop (a few attempts with a short sleep between) so one
   transient network hiccup doesn't fail the whole recording.

## The one gotcha that will bite you

`pause:` in a shot-scraper storyboard is in **seconds**, not milliseconds —
easy to get wrong by analogy to JS `setTimeout`/CSS `transition-duration`
conventions. Using `pause: 500` meaning "500ms" actually pauses for over 8
minutes. Use fractional seconds (`pause: 0.5`) for anything sub-second.

## Known limitation: zombie processes

Every `shot-scraper video` run leaves ~2 defunct `[chrome-headless]`
processes behind, reparented to PID 1 once their real parent exits. In a
container/sandbox whose PID 1 isn't a real init (no `tini`/`dumb-init`),
these are never reaped — confirmed at 58 zombies after 26 runs in this
sandbox's session (see `benchmark.md`). This can't be fixed from inside
`record.sh`: a process can only `wait()` on its own children, and these are
already reparented away by the time they're visible. If you're running this
in a loop (e.g. CI, one recording per PR), run the container with a real
init — `docker run --init ...` or a `tini`/`dumb-init` entrypoint — so PID 1
actually reaps them.
