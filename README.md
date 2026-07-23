<div align="center">

<img src=".github/banner.png" alt="built in the open" width="100%">

# built in the open

**Real experiments. Real numbers. Built in the open.**

</div>

Every week an autonomous engine picks one wave worth riding, builds it, measures it, and ships the result here — the plan, the build log, the skeptical evaluation, and the real dollar cost. Wins and honest negatives get the same treatment: when the numbers say it didn't work, that ships too. Nothing here is estimated, extrapolated, or staged after the fact.

## Experiments

| Week | Experiment | Verdict | Key number | Cost | |
|:--|:--|:--|:--|--:|:--|
| 2026-W30 | **[Show HN: Adaptive Recall, persistent memory for AI assistants over MCP](experiments/2026-w30-show-hn-adaptive-recall-persistent-memor/)** | 🟢 worked | Adaptive recall accuracy: 92.67% (139/150 correct) | $17.91 | [code →](experiments/2026-w30-show-hn-adaptive-recall-persistent-memor/) |
| 2026-W30 | **[Show HN: Skillscript – A declarative, sandboxed language for tool orch](experiments/2026-w30-show-hn-skillscript-a-declarative-sandbo/)** | 🟡 partial | 58/58 unit tests pass in 1.876s; 20/20 (100%) hand-written attack corpus bloc… | $17.91 | [code →](experiments/2026-w30-show-hn-skillscript-a-declarative-sandbo/) |
| 2026-W29 | **[Show HN: BoundFlow – an open-source control plane for AI agents](experiments/2026-w29-show-hn-boundflow-an-open-source-control/)** | 🟡 partial | Naive mode: 31/50 tasks succeeded (62.00%) with no retries, on seed 42, 30% s… | $31.46 | [code →](experiments/2026-w29-show-hn-boundflow-an-open-source-control/) |
| 2026-W29 | **[firecrawl/firecrawl — The API to search, scrape, and interact with the](experiments/2026-w29-firecrawl-firecrawl-the-api-to-search-sc/)** | 🟢 worked | 24/24 tests passing in 1.226s (`python3 -m unittest discover -s tests -v`) | $31.54 | [code →](experiments/2026-w29-firecrawl-firecrawl-the-api-to-search-sc/) |
| 2026-W29 | **[linkedin-engine — Claude Code headless system-prompt overhead benchmar](experiments/2026-w29-linkedin-engine-claude-code-headless-sys/)** | 🟢 win | MCP servers and settings add 3.4x token overhead to headless calls | $31.54 | [code →](experiments/2026-w29-linkedin-engine-claude-code-headless-sys/) |
| 2026-W29 | **[I built barebrowse: give a local-model agent a browser without Playwri](experiments/2026-w29-i-built-barebrowse-give-a-local-model-ag/)** | 🟡 partial | — | $31.68 | [code →](experiments/2026-w29-i-built-barebrowse-give-a-local-model-ag/) |
| 2026-W29 | **[linkedin-engine — Tuning improved opportunity detection from 1 to 7 mo](experiments/2026-w29-linkedin-engine-tuning-improved-opportun/)** | 🟢 win | Lowered fit threshold and calibrated prompt increased output 7x while maintai… | $31.72 | [code →](experiments/2026-w29-linkedin-engine-tuning-improved-opportun/) |
| 2026-W28 | **[Have your agent record video demos of its work with shot-scraper video](experiments/2026-w28-have-your-agent-record-video-demos-of-it/)** | 🟢 worked | Toy demo: 5.0s video, 1280×800 H.264, ~68KB, 6/6 runs succeeded this session… | $39.95 | [code →](experiments/2026-w28-have-your-agent-record-video-demos-of-it/) |

## How to read an experiment

Each subdir is self-contained: the plan (`prd.md`), every build iteration (`build-log.md`), the skeptical evaluation with measured numbers (`evaluation.md`), what it actually cost (`cost.json`) — and a README that tells you how to run it yourself.

---

<div align="center">
<sub>Built by <a href="https://www.linkedin.com/in/luk%C3%A1%C5%A1-jop%C4%8D%C3%ADk-087064223/">Lukáš Jopčík</a> · followed live on <a href="https://www.linkedin.com/in/luk%C3%A1%C5%A1-jop%C4%8D%C3%ADk-087064223/">LinkedIn</a><br>MIT licensed · experimental code, run at your own risk</sub>
</div>
