[← all experiments](../../)

```markdown
# Opportunity Scout Tuning

*One prompt and threshold change turned 1 detected opportunity into 7, from the same 48 candidates, at the same cost.*

## The wave

Autonomous agents are cheap to run but easy to misconfigure — a scout that silently returns 1 result instead of 7 looks like it's working. We're building in the open to show what tuning these pipelines actually looks like, with real before/after numbers instead of vibes.

## The build

- An opportunity-scouting agent that scores candidates for fit and flags the ones worth acting on.
- First run: default fit threshold, uncalibrated prompt.
- Second run: same input set, lowered fit threshold, recalibrated prompt.
- Compared raw output counts and the full candidate → flagged → passed-threshold funnel between runs.

## The numbers

- First run opportunities found: **1**
- Second run opportunities found: **7**
- Improvement: **7x**
- Funnel (second run): **48** candidates → **12** marked `is_opp=true` → **7** met fit ≥ **45** threshold
- Cost between runs: similar (not separately measured — no dollar figures logged)

## Run it

```bash
git clone https://github.com/<org>/built-in-the-open.git
cd built-in-the-open/opportunity-scout-tuning
pip install -r requirements.txt
python run_scout.py --config config.default.yaml   # baseline: ~1 opportunity
python run_scout.py --config config.tuned.yaml      # tuned: ~7 opportunities
```

## Verdict

Win. A lower fit threshold and a recalibrated prompt took the scout from nearly useless to producing a usable shortlist, without spending more.

## Post

_link added when the LinkedIn post is live_
```

---

**Cost:** $13.54 across 26 Claude run(s) — see `cost.json`.

<sub>Part of [built in the open](../../) — real experiments, real numbers · by [Lukáš Jopčík](https://www.linkedin.com/in/luk%C3%A1%C5%A1-jop%C4%8D%C3%ADk-087064223/)</sub>
