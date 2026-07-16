[← all experiments](../../)

I've drafted the README. Here it is in full since the write was blocked by permissions:

```markdown
# SwarmDeck

*A stdlib-only retry-and-routing layer turned 50 simulated agent tasks from 62% success to 98% success — same seed, same failures, just smarter handling.*

## The wave

Every team wiring up AI agents hits the same wall: raw SDK calls have no retries, no routing, no visibility into what failed and why. Open-source control planes for agents are showing up to fix exactly that. We wanted to know how much of that value comes from genuinely hard infrastructure versus a small amount of retry-and-routing logic anyone could write in an evening.

## The build

- Zero-dependency Python control plane: `Task`, `Router` (round-robin across simulated workers), `RetryPolicy` (exponential backoff), `Observer` (thread-safe JSONL logger of every state transition).
- Simulated workers with seeded, configurable failure rates and latency jitter — no real LLM calls, no API keys, no network.
- Two modes sharing the identical seeded failure sequence: `naive` (single worker, one attempt, no recovery) vs `control` (thread pool, dynamic routing, retries).
- Tested by running both modes on the same seed and diffing success rate, retry counts, worker distribution, and wall-clock time.
- Not built: the live terminal dashboard, the branded `report.html`, and the multi-run (`--runs 20`) confidence-interval benchmark — all three were planned and dropped mid-build.

## The numbers

- Naive mode success: **31/50** tasks (**62.00%**), zero retries, seed 42, 30% simulated failure rate.
- Control-plane success: **49/50** tasks (**98.00%**), same seed and failure rate.
- Delta: **+36** percentage points — from a **single seed only**, no confidence interval was computed.
- Retry events fired: **46** in control mode, **0** in naive mode.
- Worker ids touched: naive used **1** worker, control used **5** workers.
- Wall-clock: control finished in **0.51s** vs naive **1.82s** (**~3.6x** faster) — re-run **3x** informally, not statistically sampled.
- JSONL log: **363** lines, one per task-state transition, all valid JSON.
- Shipped **2 of 4** planned build slices; met **4 of 8** PRD success criteria.
- Caveats: no dashboard, no branded report, no multi-seed benchmark exist. The 98% number is one lucky-or-not seed, not a proven rate.

## Run it

\`\`\`bash
git clone <this-repo-subdir>
cd swarmdeck
python3 -m swarmdeck.cli --tasks 50 --failure-rate 0.3 --seed 42
\`\`\`

This prints a naive-vs-control summary table and writes `events.jsonl`. Verify the JSONL:

\`\`\`bash
python3 -c "import json; [json.loads(l) for l in open('events.jsonl')]"
\`\`\`

## Verdict

Partial. The core retry-and-routing engine works and the success-rate delta is real on this seed, but the shareable half of this experiment — the live dashboard, the branded report, the multi-run benchmark that would rule out a lucky seed — was never built. What exists is a command-line table, not a demo.

## Post

_link added when the LinkedIn post is live_
```

Want me to retry writing it to `/app/swarmdeck/README.md` once you grant permission, or write it to a different path?

---

**Cost:** $13.36 across 23 Claude run(s) — see `cost.json`.

<sub>Part of [built in the open](../../) — real experiments, real numbers · by [Lukáš Jopčík](https://www.linkedin.com/in/luk%C3%A1%C5%A1-jop%C4%8D%C3%ADk-087064223/)</sub>
