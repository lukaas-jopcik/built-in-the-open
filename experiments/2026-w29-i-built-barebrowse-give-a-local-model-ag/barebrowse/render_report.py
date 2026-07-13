"""Turn run_log.jsonl (+ optional bench_results.json) into a standalone,
brand-styled report.html — no server, no build step, opens via file://.

Layout follows the PRD's wow-shot spec: a step-by-step transcript of one
agent run (each step shows the pruned snapshot the agent actually saw and
the action it chose), a periwinkle "snapshot tokens seen" counter racing a
much larger "raw HTML equivalent" shadow counter, and a payoff panel with
the cross-page benchmark bar chart + reduction percentage in Fraunces.
"""
import argparse
import html
import json
import os
import sys

if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CSS = """
:root {
  --bg: #0f1117;
  --panel: #171a24;
  --panel-2: #1d2130;
  --border: #2a2f42;
  --text: #e8e9f3;
  --muted: #9098b5;
  --periwinkle: #8c9eff;
  --periwinkle-dim: #5b67a8;
  --shadow-red: #ff7a7a;
  --good: #6fe3b4;
  --bad: #ff8b8b;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  line-height: 1.5;
}
.wrap { max-width: 980px; margin: 0 auto; padding: 48px 24px 96px; }
.big { font-family: 'Fraunces', Georgia, serif; }
header.hero { margin-bottom: 40px; }
header.hero .brand {
  font-family: 'Fraunces', Georgia, serif;
  font-size: 15px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--periwinkle);
  margin: 0 0 12px;
}
header.hero h1 {
  font-family: 'Fraunces', Georgia, serif;
  font-size: 40px;
  margin: 0 0 12px;
  font-weight: 600;
}
header.hero p.desc { color: var(--muted); font-size: 16px; max-width: 640px; margin: 0; }

.counters {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin: 36px 0 44px;
}
.counter-card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 20px 24px;
}
.counter-card .label {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted);
  margin-bottom: 6px;
}
.counter-card .num {
  font-size: 40px;
  font-weight: 600;
}
.counter-card.snapshot .num { color: var(--periwinkle); }
.counter-card.raw .num { color: var(--shadow-red); }

h2.section {
  font-family: 'Fraunces', Georgia, serif;
  font-size: 22px;
  margin: 48px 0 18px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}

.step {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 14px;
  margin-bottom: 18px;
  overflow: hidden;
}
.step .step-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  padding: 14px 20px;
  background: var(--panel-2);
  border-bottom: 1px solid var(--border);
  flex-wrap: wrap;
}
.step .step-idx {
  font-family: 'Fraunces', Georgia, serif;
  color: var(--periwinkle);
  font-weight: 600;
  font-size: 15px;
}
.step .step-title { color: var(--muted); font-size: 13px; word-break: break-all; }
.step .step-body {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 0;
}
@media (max-width: 700px) { .step .step-body { grid-template-columns: 1fr; } }
.step pre.snapshot {
  margin: 0;
  padding: 16px 20px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 12px;
  color: #c7cbe0;
  max-height: 220px;
  overflow: auto;
  white-space: pre-wrap;
  border-right: 1px solid var(--border);
}
.step .step-meta { padding: 16px 20px; }
.action-pill {
  display: inline-block;
  padding: 5px 12px;
  border-radius: 999px;
  background: rgba(140, 158, 255, 0.15);
  color: var(--periwinkle);
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 10px;
}
.action-pill.error { background: rgba(255, 139, 139, 0.15); color: var(--bad); }
.token-line { font-size: 12px; color: var(--muted); margin-top: 8px; }
.token-line b.snap { color: var(--periwinkle); }
.token-line b.raw { color: var(--shadow-red); }

.payoff {
  margin-top: 56px;
  padding: 32px;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 16px;
}
.payoff .row { display: flex; align-items: baseline; gap: 40px; flex-wrap: wrap; }
.payoff .stat .label { color: var(--muted); font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em; }
.payoff .stat .value {
  font-family: 'Fraunces', Georgia, serif;
  font-size: 56px;
  font-weight: 600;
  color: var(--good);
}
.payoff .stat .value.warn { color: var(--bad); }

.bench-placeholder {
  color: var(--muted);
  font-size: 14px;
  border: 1px dashed var(--border);
  border-radius: 10px;
  padding: 16px 20px;
  margin-top: 16px;
}

.bars { margin-top: 24px; }
.bar-row { margin-bottom: 14px; }
.bar-row .bar-label {
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
  display: flex;
  justify-content: space-between;
}
.bar-track { position: relative; height: 20px; background: var(--panel-2); border-radius: 6px; overflow: hidden; }
.bar-fill { position: absolute; top: 0; left: 0; height: 100%; border-radius: 6px; }
.bar-fill.raw { background: var(--shadow-red); opacity: 0.55; }
.bar-fill.snapshot { background: var(--periwinkle); }

footer { margin-top: 56px; color: var(--muted); font-size: 12px; text-align: center; }
"""

HEAD_LINKS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link href="https://fonts.googleapis.com/css2?family=Fraunces:wght@500;600&'
    'family=Inter:wght@400;500;600&display=swap" rel="stylesheet">'
)

COUNTUP_JS = """
function countUp(el, target, ms) {
  var start = null;
  function step(ts) {
    if (start === null) start = ts;
    var p = Math.min(1, (ts - start) / ms);
    el.textContent = Math.round(p * target).toLocaleString();
    if (p < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('[data-countup]').forEach(function (el) {
    countUp(el, parseInt(el.getAttribute('data-countup'), 10), 1400);
  });
});
"""


def _esc(s):
    return html.escape(s if s is not None else "")


def _action_label(action):
    t = action.get("type")
    if t == "type":
        return f'type "{action.get("text", "")}" into {action.get("ref", "?")}'
    if t == "click":
        return f'click {action.get("ref", "?")}'
    if t == "done":
        if action.get("success"):
            return f'done — extracted {action.get("extracted")!r}'
        return f'done — failed ({action.get("reason", "no reason given")})'
    if t == "error":
        return f'error — {action.get("reason", "?")}'
    return t or "?"


def _render_steps(steps):
    parts = []
    cum_snap, cum_raw = 0, 0
    for s in steps:
        cum_snap += s.get("snapshot_tokens", 0)
        cum_raw += s.get("raw_html_tokens", 0)
        action = s.get("action", {})
        is_error = action.get("type") == "error" or (action.get("type") == "done" and not action.get("success"))
        pill_class = "action-pill error" if is_error else "action-pill"
        parts.append(f"""
<div class="step">
  <div class="step-head">
    <span class="step-idx">step {s['step']}</span>
    <span class="step-title">{_esc(s.get('title') or '')} — {_esc(s.get('url') or '')}</span>
  </div>
  <div class="step-body">
    <pre class="snapshot">{_esc(s.get('snapshot_text', ''))}</pre>
    <div class="step-meta">
      <span class="{pill_class}">{_esc(_action_label(action))}</span>
      <div class="token-line">this page: <b class="snap">{s.get('snapshot_tokens', 0):,}</b> snapshot tokens
        vs <b class="raw">{s.get('raw_html_tokens', 0):,}</b> raw HTML tokens</div>
      <div class="token-line">running total: <b class="snap">{cum_snap:,}</b> seen by agent
        vs <b class="raw">{cum_raw:,}</b> raw HTML equivalent</div>
    </div>
  </div>
</div>""")
    return "".join(parts), cum_snap, cum_raw


def _render_bench(bench):
    if not bench:
        return """
<div class="bench-placeholder">
  Cross-page benchmark (raw HTML vs. snapshot tokens across ≥15 real pages) lands in the
  next iteration — this panel will fill in with the bar chart and reduction percentage.
</div>"""
    pages = bench.get("pages", [])
    mean_reduction = bench.get("mean_reduction_pct", 0.0)
    max_raw = max((p.get("raw_tokens", 0) for p in pages), default=1) or 1
    rows = []
    for p in pages:
        raw = p.get("raw_tokens", 0)
        snap = p.get("snapshot_tokens", 0)
        raw_pct = 100.0 * raw / max_raw
        snap_pct = 100.0 * snap / max_raw
        label = p.get("url", "")
        rows.append(f"""
<div class="bar-row">
  <div class="bar-label"><span>{_esc(label)}</span><span>{raw:,} → {snap:,} tokens ({p.get('reduction_pct', 0):.0f}% cut)</span></div>
  <div class="bar-track">
    <div class="bar-fill raw" style="width:{raw_pct:.1f}%"></div>
    <div class="bar-fill snapshot" style="width:{snap_pct:.1f}%"></div>
  </div>
</div>""")
    return f"""
<div class="row">
  <div class="stat">
    <div class="label">mean token reduction, {len(pages)} pages</div>
    <div class="value big">{mean_reduction:.0f}%</div>
  </div>
</div>
<div class="bars">{''.join(rows)}</div>"""


def render(run_log, bench, task_description=""):
    if not run_log:
        raise ValueError("run_log is empty; nothing to render")

    primary = next((r for r in run_log if r.get("success")), run_log[0])
    steps_html, cum_snap, cum_raw = _render_steps(primary.get("steps", []))

    total = len(run_log)
    successes = sum(1 for r in run_log if r.get("success"))
    success_pct = 100.0 * successes / total if total else 0.0
    success_class = "" if successes >= max(1, int(0.8 * total)) else "warn"

    bench_html = _render_bench(bench)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>barebrowse — agent run report</title>
{HEAD_LINKS}
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <header class="hero">
    <p class="brand">barebrowse</p>
    <h1>An agent that never saw the HTML.</h1>
    <p class="desc">{_esc(task_description) or 'Autonomous agent run, driven entirely off pruned ARIA-role snapshots — no browser automation stack, no raw markup ever reaches the policy.'}</p>
  </header>

  <div class="counters">
    <div class="counter-card snapshot">
      <div class="label">tokens the agent actually saw</div>
      <div class="num" data-countup="{cum_snap}">0</div>
    </div>
    <div class="counter-card raw">
      <div class="label">raw HTML equivalent (shadow counter)</div>
      <div class="num" data-countup="{cum_raw}">0</div>
    </div>
  </div>

  <h2 class="section">Step-by-step transcript</h2>
  {steps_html}

  <div class="payoff">
    <div class="row">
      <div class="stat">
        <div class="label">task success rate</div>
        <div class="value big {success_class}">{successes}/{total}</div>
      </div>
      <div class="stat">
        <div class="label">success %</div>
        <div class="value big {success_class}">{success_pct:.0f}%</div>
      </div>
    </div>
    {bench_html}
  </div>

  <footer>barebrowse — stdlib-only HTML→ARIA snapshot engine + ref-driven browser + autonomous agent loop</footer>
</div>
<script>{COUNTUP_JS}</script>
</body>
</html>
"""


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render run_log.jsonl (+ optional bench_results.json) to report.html")
    parser.add_argument("run_log", help="path to run_log.jsonl")
    parser.add_argument("bench", nargs="?", default=None, help="path to bench_results.json (optional)")
    parser.add_argument("-o", "--out", default="report.html")
    args = parser.parse_args(argv)

    run_log = []
    with open(args.run_log) as f:
        for line in f:
            line = line.strip()
            if line:
                run_log.append(json.loads(line))

    bench = None
    if args.bench and os.path.exists(args.bench):
        with open(args.bench) as f:
            bench = json.load(f)

    task_description = ""
    task_path = "task.json"
    if os.path.exists(task_path):
        with open(task_path) as f:
            task_description = json.load(f).get("description", "")

    html_out = render(run_log, bench, task_description=task_description)
    with open(args.out, "w") as f:
        f.write(html_out)
    print(f"wrote {args.out} ({len(run_log)} runs, bench={'yes' if bench else 'pending'})")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
