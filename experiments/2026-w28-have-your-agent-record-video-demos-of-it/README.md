[← all experiments](../../)

# Agent-Recorded Demos with shot-scraper

*An agent recorded its own on-brand demo clip in 12 seconds of wall time, $0 API spend, 100% success across 20 back-to-back runs.*

## The wave

Agents ship features faster than anyone can screen-record them. Proving "it works" still means a human opening a screen recorder, clicking through a flow, and trimming the clip. `shot-scraper video` lets the agent that built the feature also record the proof, unattended, as part of the same pipeline.

## The build

- `setup.sh` installs `shot-scraper` and Playwright's Chromium into a repo-local venv, zero prompts.
- `record.sh` serves a static demo page, drives it through `shot-scraper`, and writes `output/demo.mp4` plus a LinkedIn-ready `output/caption.md`.
- `real-record.sh` records a second, on-brand "wow shot": an agent-swarm task board where six cards animate queued → running → shipped in parallel, ending on a summary card.
- Both scripts verify the HTTP server actually bound the port, fall back to a free port if not, and clean up so no `.webm` clutter is left behind.
- Tested with `ffprobe` (duration, resolution, codec), extracted frames to visually confirm real rendered content, and benchmarked N=10 back-to-back runs of each demo.

## The numbers

- Toy demo video duration: **5.0s**, resolution **1280x800**, size **~68KB**
- Toy demo success rate: **10/10** (benchmark), **6/6** (review session)
- Toy demo wall time: p50 **6.77s**, p95 **6.83s**
- Swarm demo video duration: **9.3–9.4s**, resolution **1280x800**, size **~456KB**
- Swarm demo success rate: **10/10** (benchmark), **4/4** (review session)
- Swarm demo wall time: p50 **11.83s**, p95 **11.90s**
- Cost per clip: **$0** in API spend
- Caveat — zombie processes: **58 → 85** (+27) defunct `chrome-headless` processes accumulated over one review session's ~12 recordings; not reaped by this sandbox's PID 1, and not fixable from inside the repo's own scripts.
- Caveat — cold-cache install time (<2 minutes) was **never independently measured**: the sandbox blocks deleting the shared Playwright cache needed to test it.
- Caveat — both demo pages load fonts live from `fonts.googleapis.com`, a real external network dependency the docs elsewhere describe as eliminated.

## Run it

```bash
./setup.sh          # installs shot-scraper + Chromium into a repo-local venv
./record.sh          # records the toy demo to output/demo.mp4 + output/caption.md
./real-record.sh      # records the on-brand swarm demo to output/real-demo.mp4
ffprobe -v error -show_entries format=duration -of csv=p=0 output/demo.mp4
cat output/caption.md
```

## Verdict

Worked. An agent can unattended produce a real, playable MP4 and a ready-to-post caption in seconds, for free. It has only ever been proven against pages the builder fully controls, not a real product with logins, spinners, or a JS framework — pointing it at an actual SaaS dashboard is real selector-debugging work, not a URL swap. The zombie-process leak is real and unbounded without a container-level init fix.

## Post

_link added when the LinkedIn post is live_

---

**Cost:** $8.18 across 15 Claude run(s) — see `cost.json`.

<sub>Part of [built in the open](../../) — real experiments, real numbers · by [Lukáš Jopčík](https://www.linkedin.com/in/luk%C3%A1%C5%A1-jop%C4%8D%C3%ADk-087064223/)</sub>
