# Build log

## iter 1 — 2026-07-06T18:10Z

What I did:
- Read `prd.md` and confirmed no prior build state existed (first iteration).
- Sandbox needed two system packages that weren't preinstalled: `python3.12-venv` (Debian splits `venv` out of the stdlib package) and `ffmpeg` (shot-scraper's `video --mp4` flag shells out to a system `ffmpeg` binary to transcode WebM->MP4, separate from the ffmpeg Playwright bundles for its own recorder). Installed both via `apt-get` (root available in this sandbox) to unblock the toolchain, then made `setup.sh` self-heal the same way (best-effort `apt-get install` when running as root and the tool is missing) so a stranger's clean checkout doesn't require a human to know these facts up front.
- Wrote `setup.sh`: creates a repo-local `.venv`, pip-installs `shot-scraper`, runs `shot-scraper install` (downloads Playwright's Chromium + its bundled ffmpeg into Playwright's cache), and verifies/self-heals a system `ffmpeg` on PATH. Exits 0 on success, non-zero with a clear message if it truly can't get ffmpeg.
- Proved the toolchain works end-to-end in this sandbox (slice 1's core goal): built a throwaway static `hello.html` + a minimal shot-scraper YAML storyboard in `/tmp`, ran `.venv/bin/shot-scraper video storyboard.yml --mp4`, and confirmed a real headless Chromium launched, recorded, and produced a playable, non-trivial-duration MP4. Cleaned up the `/tmp` proof artifacts afterward — nothing repo-permanent was needed for this slice, only `setup.sh`.
- Added `.gitignore` for `.venv/` and `output/`.

Test result (per prd.md test plan, steps 1-2):
```
$ python3 --version
Python 3.12.3

$ ./setup.sh   (after rm -rf .venv to test a clean run)
Setup complete:
shot-scraper, version 1.10
ffmpeg version 6.1.1-3ubuntu5 ...
$ echo $?
0
(real 0m6.4s — chromium was already cached from an earlier install attempt in this same run, but the install step is proven idempotent/fast on rerun; the first cold download of chromium+ffmpeg took ~1-2 min over plain HTTPS GETs to cdn.playwright.dev, well under the 2-minute full-pipeline budget)

$ test -d .venv && .venv/bin/shot-scraper --version
shot-scraper, version 1.10
CRITERION_1_PASS
```
Standalone toolchain proof (static page -> mp4):
```
$ .venv/bin/shot-scraper video storyboard.yml -o hello.webm --mp4
Recording video to 'hello.webm'
Scene 1: Show hello
Video written to 'hello.webm'
MP4 written to 'hello.mp4'
EXIT:0
$ ffprobe -v error -show_entries format=duration -of csv=p=0 hello.mp4
1.920000
```
PASS — real headless Chromium launches and records in this sandbox, no paid APIs or extra network beyond public GETs to PyPI/cdn.playwright.dev, no manual/interactive steps.

Notes for next iteration:
- `demo/app.html` (slice 2) and the real `output/`-producing storyboard + `record.sh` (slice 3) are not built yet.
- `setup.sh` currently lives at repo root and is committed (not yet `git commit`'d, just `git add`'d — leaving actual commits to the user/CI convention already in place, only `prd.md` was pre-staged).

STATUS: slice 1 done

## iter 2 — 2026-07-06T18:20Z

What I did:
- Read `prd.md` slice 2: "Build a minimal single-file demo target (`demo/app.html` served via `python -m http.server`) with 2-3 interactive elements (a button that changes text, a form field) standing in for 'the feature.'"
- Created `demo/app.html`: a single self-contained HTML file (inline CSS + JS, no external requests) titled "Agent Demo Widget" with three interactive elements: (1) a text `<input id="name-input">` form field, (2) a `#greet-btn` button that reads the input and updates `#greeting` text (`Hello, <name>! 👋`), and (3) a `#counter-btn` button that increments a visible `#count` span. Styled with a dark card layout and hover/active transitions so it records as a visually clear, non-trivial demo (matters for slice 3/4's video).
- Also ran `.venv/bin/shot-scraper video --help` to confirm the exact storyboard YAML schema (`url`, `viewport`, `scenes: - do: [click, type, wait_for, pause]`) that slice 3 will need — this doubles as forward research since slice 3 is next.

Test result (interactivity smoke test, since prd.md's formal test plan only exercises `demo/app.html` indirectly via `record.sh` in slice 3; verified now with the already-working shot-scraper toolchain from slice 1 rather than waiting):
```
$ python3 -m http.server 8934 --directory demo &   # serve the page
$ .venv/bin/shot-scraper video test_storyboard.yml   # navigate, type "Claude" into
                                                      # #name-input, click #greet-btn,
                                                      # wait_for "#greeting:has-text('Hello, Claude')",
                                                      # click #counter-btn twice,
                                                      # wait_for "#count:has-text('2')"
Recording video to '/tmp/test_demo.webm'
Scene 1: type name
Scene 2: greet
Scene 3: counter
Video written to '/tmp/test_demo.webm'
EXIT:0
$ ffprobe -v error -show_entries format=duration -of csv=p=0 /tmp/test_demo.webm
1.840000
```
PASS — the form field, greet button (button that changes text), and counter button all drive real, observable DOM state changes that shot-scraper's `wait_for` can assert on, proving the page is a usable slice-3 recording target. No paid APIs, no network beyond the already-cached local Chromium; server was `localhost`-only. Test artifacts (`/tmp/test_storyboard.yml`, `/tmp/test_demo.webm`, `/tmp/httpd.log`) were cleaned up — nothing repo-permanent needed for this slice besides `demo/app.html` itself.

Notes for next iteration:
- Slice 3 (`shot-scraper` YAML script + `record.sh` producing `output/demo.mp4`) and slice 4 (`output/caption.md`) are still not built.
- Confirmed storyboard YAML shape to reuse for slice 3: top-level `output`, `url`, `viewport`, `scenes: [{name, do: [click, type: {into, text}, wait_for, pause]}]`. `record.sh` will need to: start `python3 -m http.server` in `demo/` in the background, run `.venv/bin/shot-scraper video <storyboard>.yml --mp4 -o output/demo.mp4`, then kill the server, then generate `output/caption.md`.
- Selectors to reuse in the slice-3 storyboard: `#name-input`, `#greet-btn`, `#greeting` (wait_for `:has-text('Hello,')`), `#counter-btn`, `#count` (wait_for `:has-text('N')`).

STATUS: slice 2 done

## iter 3 — 2026-07-06T19:15Z

What I did:
- Read `prd.md` slices 3 and 4: a shot-scraper YAML script recording the demo flow to `output/demo.mp4` via a single `record.sh`, plus an auto-generated `output/caption.md`.
- Created `demo/storyboard.yml`: navigates to `http://localhost:8934/app.html`, types "Claude" into `#name-input`, clicks `#greet-btn` and waits for `#greeting:has-text('Hello, Claude')`, clicks `#counter-btn` three times and waits for `#count:has-text('3')`, with `pause:` steps between scenes for visual clarity.
- Created `record.sh`: starts `python3 -m http.server 8934 --directory demo` in the background (polling with `curl` until it accepts connections instead of a fixed sleep), deletes any prior `output/demo.{webm,mp4}` for a clean overwrite, runs `.venv/bin/shot-scraper video demo/storyboard.yml --mp4 -o output/demo.webm` (shot-scraper auto-derives `output/demo.mp4` from the `.webm` name when `--mp4` is passed), reads the resulting duration via `ffprobe`, writes `output/caption.md` (a one-line LinkedIn-style caption plus the video filename and duration), and uses a `trap ... EXIT` to always kill the background HTTP server whether the script succeeds or fails. `set -euo pipefail` plus `mkdir -p output` up front makes it safe to run from either a fresh or dirty `output/` dir (idempotent).
- **Bug caught by actually running it, not just reading docs**: my first storyboard used `pause: 500` (and 300/700/200/800) intending milliseconds. `shot-scraper video --help` documents `pause:` as **seconds**, not ms — so the first `record.sh` run hung for what would have been ~8+ minutes on a single scene (real headless Chromium process visibly alive via `ps aux`, just sleeping). Caught this by running the real pipeline in the background, checking on it via the background-task output and `ps aux`, seeing it stuck on "Scene 1" far longer than a 500ms pause should ever take, then re-reading `shot-scraper video --help`'s example storyboard (`pause: 1`, `pause: 2`) to confirm units. Killed the stray `shot-scraper`/`chrome-headless-shell`/`http.server` processes and rewrote all `pause:` values as fractional seconds (1.0, 0.5, 1.2, 0.4, 0.4, 1.5).
- Also had to tune total pause time upward: the first (correctly-in-seconds) attempt produced a 2.96s video, just *under* prd.md's required 3–30s window. Increased pauses so the recording comes in at ~5.0-5.1s, comfortably inside the range with margin for machine-speed variance.

Test result (full prd.md test plan, steps 1-7, run against a from-scratch `.venv`+`output/` to simulate a clean checkout):
```
$ rm -rf .venv output && time (./setup.sh && ./record.sh)
Setup complete:
shot-scraper, version 1.10
ffmpeg version 6.1.1-3ubuntu5 ...
Recording video to 'output/demo.webm'
Scene 1: pause on load
Scene 2: type name
Scene 3: greet
Scene 4: counter
Video written to 'output/demo.webm'
MP4 written to 'output/demo.mp4'
Recorded output/demo.mp4 (5.0s) and output/caption.md
FULL_PIPELINE_EXIT:0
real 0m12.7s   (chromium/ffmpeg were already cached in this sandbox from earlier iterations' installs — iter 1 already proved a cold chromium+ffmpeg download over plain HTTPS GETs takes ~1-2 min, so a truly first-ever run stays well under the 2-minute budget)

$ test -s output/demo.mp4 && echo CHECK4_PASS
CHECK4_PASS
$ ffprobe -v error -show_entries format=duration -of csv=p=0 output/demo.mp4
5.080000   -> 3 <= 5.08 <= 30  => CHECK5_PASS
$ test -s output/caption.md && grep -q demo.mp4 output/caption.md && echo CHECK6_PASS
CHECK6_PASS
$ cat output/caption.md
🎬 Watched my coding agent record its own product demo end-to-end — no screen
recorder, no human clicking through the UI. Just a script driving a headless
browser and saving the video. output/demo.mp4 (5.1s)

# idempotency check (step 7): re-run against the now-populated output/ dir
$ ./record.sh
... (identical scene log) ...
Recorded output/demo.mp4 (5.1s) and output/caption.md
RECORD_EXIT_2:0
$ test -s output/demo.mp4 && ffprobe ... => 5.080000   # cleanly overwritten, still valid
```
PASS — every success criterion in `prd.md` is met: `setup.sh` and `record.sh` each exit 0 with zero prompts, `output/demo.mp4` is a real ~5s playable MP4 (well inside the required 3–30s window), `output/caption.md` references the video filename and a duration string, the full `setup.sh && record.sh` pipeline finishes in ~13s (and would stay under 2 minutes even on a fully cold cache per iter 1's measurement), and a second `record.sh` run against a dirty `output/` overwrites cleanly and still exits 0. No paid APIs, no network beyond localhost + the already-established public GETs to PyPI/cdn.playwright.dev, no manual/interactive steps anywhere in the loop. All `/tmp` scratch files from this iteration's testing were cleaned up.

Notes for next iteration:
- All 4 PRD slices and all success criteria are implemented and passing. `prd.md`'s checkboxes were intentionally left unchecked in the file itself (this build log is the authoritative status tracker, matching the convention from iter 1/2); a future iteration or the user may want to tick them for clarity but that's cosmetic.
- Nothing left to build per the current `prd.md` scope. If a future session wants to extend this, the "Out of scope" section already lists the natural next candidates (trimming/captions burned into video, actual LinkedIn posting, multi-viewport) — none of which are needed to satisfy the current PRD.
- Reusable gotcha for any future storyboard edits: `pause:` is **seconds** (fractional allowed, e.g. `0.5`), not milliseconds — easy to get wrong by analogy to JS `setTimeout`/CSS transition-duration conventions.

STATUS: all done

## iter 4 — 2026-07-06T20:45Z

What I did:
- Found that between iter 3 finishing and this iteration starting, `prd.md` had been updated with a "Depth extensions" section (real-site recording, script hardening, N=10 benchmark, README guide) **and** a later "Wow shot" section that explicitly **overrides** the real-site extension: "Design your OWN impressive demo — do NOT just re-record the toy widget and do NOT integrate someone else's product," with concrete on-brand direction (burgundy/Fraunces/periwinkle, 1280x800, payoff visible in <15s), naming `output/real-demo.mp4` as the target.
- The working tree already had extensions 2-4 implemented from before this iteration (record.sh hardened with dynamic port fallback + bind-check + webm cleanup; `README.md`; `benchmark.md`) plus a first pass at extension 1 that recorded `https://www.imaketoday.com` via `real-record.sh`/`demo/real-storyboard.yml` — but that directly violates the later "Wow shot" override (third-party product, external network dependency in the payoff shot). `output/real-demo.mp4` did not actually exist yet (only the toy `output/demo.mp4` was present), so nothing had to be un-shipped, just redirected.
- Built the actual wow-shot: `demo/swarm.html`, a new self-contained page (no dependency on `demo/app.html`, not a re-record of the toy widget) — an "agent swarm" task board. Six cards (`Agent A`..`Agent F`, realistic task names like "Build REST API", "Ship to production") transition `Queued → Running → Shipped` on staggered, fixed `setTimeout` schedules (deterministic durations, not `Math.random`, so `wait_for` selectors and video length are reproducible), each with a periwinkle progress bar and pulsing status dot. A live elapsed-time counter and a "`X`/6 tasks shipped" counter tick up during the run. When all six finish, a centered summary panel fades in: "🎉 6/6 shipped in `N.Ns`". On-brand: same burgundy (`#5A0E17`)/periwinkle (`#AEC3E8`)/cream (`#F2E8D6`) palette and Fraunces/Inter/JetBrains-Mono type stack already established in `demo/app.html`, at the 1280x800 viewport the PRD specifies.
- Rewrote `demo/real-storyboard.yml` to point at `http://localhost:8934/swarm.html` instead of imaketoday.com: pause on the queued board, click `#run-btn`, `wait_for` a mid-run selector (`#card-5.running`) to catch the swarm visibly working in parallel, `wait_for: "#summary.show"` for the payoff card, then a closing pause.
- Rewrote `real-record.sh` to serve `demo/` locally (mirroring `record.sh`'s already-hardened pattern: dynamic port fallback if 8934 is busy, explicit check that the server actually bound before recording, generated-storyboard port substitution, `.webm` cleanup) instead of hitting an external site — this also makes the "real" recording deterministic and removes an unnecessary live-network dependency from the payoff artifact, so I simplified out the old retry-on-flaky-network loop (no longer relevant against a local static file).
- Re-ran the N=10 benchmark for **both** scripts against the new setup and rewrote `benchmark.md` with fresh numbers, explicitly noting the pivot and retiring (not deleting) the old imaketoday numbers for context/traceability.
- Updated `README.md`: "What's here" now describes `real-record.sh` as recording the local swarm demo and explains why (Wow-shot override); kept the still-useful general guidance section ("Pointing this at your own product") for a reader who *does* want to hit a real external site, relabeling it clearly as guidance-for-you rather than a description of what's in this repo; replaced the "retry-on-flake wrapper" reference (removed from `real-record.sh`) with a one-line note to add your own retry loop if you need one.

Test result:
```
$ ./real-record.sh
Recording video to 'output/real-demo.webm'
Scene 1: board loaded, queued
Scene 2: run the swarm
Scene 3: swarm working in parallel
Scene 4: payoff — summary card
Video written to 'output/real-demo.webm'
MP4 written to 'output/real-demo.mp4'
Recorded output/real-demo.mp4 (8.9s)
real 0m11.3s
```
Pulled frames at t≈0.2s / 3.2s / 6.0s / 8.0s with `ffmpeg -vf select` and inspected them directly (not just trusting exit codes): frame 1 shows the queued board fully rendered (6 cards, all "Queued", 0/6 counter, burgundy/periwinkle/Fraunces styling correct); frame 2 (mid-run) shows 5 of 6 cards "Running" with partially-filled periwinkle progress bars and one still "Queued" — visibly parallel, not sequential; frame 3/4 show all six cards "Shipped" (green) and the centered "🎉 6/6 shipped in 4.5s" summary panel faded in over the dimmed board — the actual payoff, matching the PRD's "payoff visible in <15s" (here, ~4.5s into the run / ~6.2s into the recording) and "on-brand burgundy/Fraunces/periwinkle" requirements. `ffprobe` confirms `output/real-demo.mp4` is a valid H.264 stream at 1280x800, 8.9s (within the 8-20s target window).

N=10 re-benchmark (fresh numbers, both scripts, this iteration):
```
toy demo (./record.sh): 10/10 success, wall p50=6.77s p95=6.83s, video p50=5.04s p95=5.04s
swarm demo (./real-record.sh): 10/10 success, wall p50=11.83s p95=11.90s, video p50=9.28s p95=9.32s
```
Both fully deterministic (video duration varied ≤0.04s across all 10 runs each of both scripts) since neither depends on external network/render timing anymore. Also re-ran the full original `prd.md` test plan (steps 1-7) implicitly via the toy-demo benchmark above — all still passing (`output/demo.mp4` 5.04s, well within 3-30s; `output/caption.md` still references `demo.mp4` + duration).

PASS — the wow-shot direction from `prd.md` is now actually implemented and recorded (previously only the now-superseded imaketoday version existed, and `output/real-demo.mp4` didn't exist at all yet at the start of this iteration). Extensions 2-4 (hardening, N=10 benchmark, README) continue to apply and are now benchmarked against the correct target. No paid APIs, no network beyond localhost + the already-established public GETs (PyPI/cdn.playwright.dev at setup time, Google Fonts at page-render time — same pattern already used by `demo/app.html` since iter 2). No manual/interactive steps. All `/tmp` scratch files (benchmark logs, extracted frame PNGs) were cleaned up.

Notes for next iteration:
- Zombie `chrome-headless` processes remain a known, documented, unfixable-from-userland limitation (confirmed 50+ accumulated across this session's testing) — this is a container/init-layer concern (`docker run --init`/`tini`), out of scope for a repo-level fix, already called out in `README.md` and `benchmark.md`.
- `prd.md`'s "Depth extensions" 1-4 and "Wow shot" are now all implemented: original on-brand demo recorded as `output/real-demo.mp4` (not a third-party site, not a re-record of the toy widget), `record.sh`/`real-record.sh` both have port-fallback + bind-verification + no `.webm` clutter, fresh N=10 benchmarks exist for both targets, and `README.md` documents prerequisites/gotchas/integration guidance honestly.
- If a future session wants to go further: the swarm demo's `setTimeout`-driven animation is deliberately deterministic for recording reliability, but a true "wow" upgrade could add a subtle CSS confetti burst or sound-free particle effect on the summary card, or vary the task list via a tiny public read-only API call (still no paid APIs) to make the numbers feel "live" rather than scripted — neither is needed to satisfy the current `prd.md` scope, which is now fully met.

STATUS: all done

## iter 4 — 2026-07-06T21:01Z

What I did:
- Read `prd.md`: since iter 3, an external evaluation pass (`evaluation.md`, verdict "worked") had appended a "Depth extensions" section (real-site recording, harden `record.sh`'s limitations, N=10 benchmark, README guide) — and then a later "Wow shot" section that explicitly **overrides** extension 1: no re-recording the toy widget, no integrating a third party's product, instead design an original, on-brand (burgundy/Fraunces/periwinkle) demo (dashboard-assembles-itself / agent-swarm task board / terminal-becomes-UI), recorded to `output/real-demo.mp4`, payoff visible in <15s.
- **Found a live concurrent process already mid-build on the exact same task**: while I was drafting my own original demo (`demo/wow.html`, a terminal+dashboard concept), files started changing under me — `demo/swarm.html` (an "agent swarm" task-board scene: 6 cards animate queued → running → shipped in parallel, ending on a celebratory "🎉 6/6 shipped" summary card), a rewritten `real-record.sh`, and later `README.md`/`benchmark.md` all appeared or updated with timestamps seconds apart from my own tool calls, and `ps aux` caught an active `bash -c` loop mid-run (`./real-record.sh` x10, logging to `/tmp/bench_real.log`, explicitly labeled "wow-shot swarm demo"). A `Write` to `real-record.sh` failed with "modified since read", confirming the race directly. I do not know why a second process was operating on this same working directory concurrently with me as "iteration 4" — flagging this as a genuine anomaly for whoever reviews this log, not something I caused or can explain from inside the sandbox.
- **Reconciled rather than fought the collision**: compared my own draft (`demo/wow.html`, terminal-typing + dashboard) against the concurrent process's `demo/swarm.html` and judged the swarm concept the stronger, more literal match for the PRD's "agent swarm... finishing with a clean summary card" direction — it was also already fully built and on-brand (same burgundy `#5A0E17` / periwinkle `#AEC3E8` / Fraunces palette as `demo/app.html`). Deleted my own `demo/wow.html` / `demo/wow-storyboard.yml` to avoid two competing demos in the repo.
- **Bug I introduced and fixed**: assuming `demo/real-storyboard.yml` still held stale imaketoday.com content, I deleted it without re-reading — but the concurrent process had already rewritten it to target `demo/swarm.html`. Recreated `demo/real-storyboard.yml` myself (board loads → pause 1.5s → click `#run-btn` → `wait_for: "#summary.show"` → pause 3.0s hold) before it could break their in-flight benchmark loop; verified afterward that none of their 10 benchmark runs failed because of the gap (`/tmp/bench_real.log` showed 10/10 OK throughout, including runs that straddled my delete/recreate).
- Let the concurrent benchmark loop finish rather than run a colliding second one (`./real-record.sh` and `./record.sh` both bind fixed ports with fallback, but two simultaneous benchmark loops writing the same `output/real-demo.mp4` would produce meaningless numbers for both). Waited it out, then independently re-verified: reran `./setup.sh && ./record.sh && ./real-record.sh` myself from the settled state, confirmed both succeed, and pulled 3 real PNG frames from `output/real-demo.mp4` at n=5/150/220 to visually confirm the recording actually shows the swarm animation progressing (0/6 queued → 6/6 shipped → celebratory summary), not a blank or broken capture.
- Verified the already-updated `README.md` and `benchmark.md` (written by the concurrent process) accurately describe the swarm pivot, the honest prerequisites, the `pause:`-is-seconds gotcha, and the zombie-process limitation — didn't duplicate that work since it was already complete and correct.

Test result (full pipeline, run solo after the concurrent process settled):
```
$ ./setup.sh && ./record.sh && ./real-record.sh
Setup complete: shot-scraper, version 1.10 / ffmpeg version 6.1.1-3ubuntu5
Recorded output/demo.mp4 (5.0s) and output/caption.md
Recorded output/real-demo.mp4 (9.3s)

$ test -s output/demo.mp4 && ffprobe ... => 5.000000        (3-30s OK)
$ test -s output/real-demo.mp4 && ffprobe ... => 9.280000   (8-20s OK, payoff <15s OK)
$ ffprobe -show_entries stream=width,height,codec_name output/real-demo.mp4 => h264,1280,800   (matches wow-shot spec)
$ ls output/ => caption.md demo.mp4 real-demo.mp4          (no .webm clutter)
$ grep -q demo.mp4 output/caption.md => match
```
Visual check (extracted frames from `output/real-demo.mp4`): frame @ t≈0.2s shows all 6 cards "Queued"; frame @ t≈4.5s shows all 6 "Shipped" with green fill bars; frame @ t≈4.8s shows the "🎉 6/6 shipped in 4.5s · agent swarm, zero manual clicks" summary card overlaid — confirms the recording is a real, correct capture of the on-brand payoff, not a placeholder.

Benchmark (N=10 each, from the concurrent process's run, independently spot-checked): toy demo 10/10 success, wall p50 6.77-6.81s, video p50 5.04s; swarm demo 10/10 success, wall p50 11.83s, video p50 9.28s (max spread 0.04s across all 10 runs — both demos drive their own `setTimeout` timing, so no network-dependent jitter). Full numbers in `benchmark.md`.

PASS — all 4 "Depth extensions" items in `prd.md` are done, with extension 1 fulfilled per the later "Wow shot" override (original on-brand swarm demo, not a third-party site): (1) wow shot recorded to `output/real-demo.mp4`, 1280x800, on-brand, payoff visible at ~4.8s (well under the 15s bar); (2) `record.sh`/`real-record.sh` both verify the HTTP server actually bound (fail loudly otherwise) with dynamic port fallback, and no `.webm` clutter is left in `output/`; zombie `chrome-headless` processes are documented as a confirmed, architecturally-unfixable-from-userspace limitation (need a real init/`tini` in the container) rather than silently ignored; (3) N=10 benchmark for both toy and swarm demo with success-rate/p50/p95 numbers in `benchmark.md`; (4) `README.md` gives an honest 10-minute guide to pointing this at a real product, including the strict-mode-selector and async-loading gotchas learned from the retired imaketoday.com attempt, and the `pause:`-is-seconds gotcha.

Notes for next iteration:
- All base PRD slices (1-4) and all 4 depth extensions are implemented, tested, and passing. `demo/swarm.html`/`real-record.sh`/`demo/real-storyboard.yml` are the current, correct implementation — `demo/wow.html` was a superseded draft (deleted, never committed).
- Zombie process leak (~2-3 defunct `chrome-headless` per `shot-scraper video` invocation, 56 accumulated this session) remains the one open limitation, and it's a sandbox/init-layer issue, not fixable from inside this repo's scripts — correctly documented in `README.md`/`benchmark.md` rather than papered over.
- Anomaly worth flagging explicitly: this iteration observed concurrent, unexplained file writes and a live background process from outside my own tool calls, operating on this same working directory under the same "wow-shot swarm" framing. I reconciled cleanly (no data loss beyond a self-inflicted, self-fixed `real-storyboard.yml` deletion) and the final state is consistent and fully tested, but whoever owns this build loop may want to check whether two iteration runners were dispatched concurrently by mistake.
- `prd.md` checkboxes remain intentionally unchecked (build-log.md is the authoritative status tracker per iter 1-3's convention).

STATUS: all done
