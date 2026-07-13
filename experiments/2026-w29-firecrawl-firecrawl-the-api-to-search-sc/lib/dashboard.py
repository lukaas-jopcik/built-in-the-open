"""Render a single self-contained dashboard.html from a snapshot + diff.

Pure string templating, stdlib only (no Jinja/etc). All remote-sourced text
(titles, URLs) is HTML-escaped before being embedded, since it originates
from third-party pages we don't control.
"""
import html as _html


def _ok_sites(snapshot):
    return [s for s in snapshot.get("sites", []) if "error" not in s and "skipped" not in s]


def _aggregate(snapshot, diff):
    ok = _ok_sites(snapshot)
    return {
        "sites_tracked": len(snapshot.get("sites", [])),
        "total_words": sum(s.get("word_count", 0) for s in ok),
        "total_links": sum(s.get("link_count", 0) for s in ok),
        "total_changes": diff["total_changes"] if diff else 0,
    }


def _stat_card(label, key, value):
    return (
        f'<div class="stat-card" data-metric="{key}" data-value="{value}">'
        f'<div class="stat-number" data-target="{value}">0</div>'
        f'<div class="stat-label">{_html.escape(label)}</div>'
        f"</div>"
    )


def _link_rows(items, css_class, sign):
    rows = []
    for link in items:
        rows.append(
            f'<div class="link-row {css_class}">{sign} {_html.escape(link)}</div>'
        )
    return "\n".join(rows)


def _health_badge(health_scores, url):
    if not health_scores or url not in health_scores:
        return ""
    score = health_scores[url]["score"]
    tier = "good" if score >= 90 else "warn" if score >= 50 else "bad"
    return f'<span class="badge health {tier}">{score}% healthy</span>'


def _site_row(site, per_site_diff, health_scores=None):
    url = site.get("url", "")
    if "error" in site:
        return (
            f'<tr class="site-row error"><td>{_html.escape(url)}'
            f'{_health_badge(health_scores, url)}</td>'
            f'<td colspan="3">error: {_html.escape(str(site["error"]))}</td></tr>'
        )
    if "skipped" in site:
        return (
            f'<tr class="site-row skipped"><td>{_html.escape(url)}'
            f'{_health_badge(health_scores, url)}</td>'
            f'<td colspan="3">skipped: {_html.escape(str(site["skipped"]))}</td></tr>'
        )

    title = _html.escape(site.get("title") or "(untitled)")
    words = site.get("word_count", 0)

    d = per_site_diff or {}
    delta = d.get("word_count_delta")
    if d.get("is_new"):
        delta_html = '<span class="badge new">new</span>'
    elif delta is None:
        delta_html = '<span class="delta zero">&plusmn;0</span>'
    elif delta > 0:
        delta_html = f'<span class="delta pos">+{delta}</span>'
    elif delta < 0:
        delta_html = f'<span class="delta neg">{delta}</span>'
    else:
        delta_html = '<span class="delta zero">&plusmn;0</span>'

    added = _link_rows(d.get("added_links", []), "added", "+")
    removed = _link_rows(d.get("removed_links", []), "removed", "-")
    link_diff_html = added + removed if (added or removed) else '<span class="muted">no link changes</span>'

    title_flag = ' <span class="badge title-changed">title changed</span>' if d.get("title_changed") else ""

    return (
        '<tr class="site-row">'
        f'<td><a href="{_html.escape(url)}">{_html.escape(url)}</a>'
        f'{_health_badge(health_scores, url)}<br>'
        f'<span class="site-title">{title}</span>{title_flag}</td>'
        f"<td>{words}</td>"
        f"<td>{delta_html}</td>"
        f'<td class="link-diffs">{link_diff_html}</td>'
        "</tr>"
    )


_CSS = """
body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; background: #0b0d12; color: #e6e8ec; margin: 0; padding: 2rem; }
h1 { font-weight: 600; }
.subtitle { color: #8890a0; margin-top: -0.5rem; }
.stats { display: flex; gap: 1rem; flex-wrap: wrap; margin: 2rem 0; }
.stat-card { background: #161923; border-radius: 12px; padding: 1.25rem 1.75rem; min-width: 160px; box-shadow: 0 1px 0 rgba(255,255,255,0.04) inset; }
.stat-number { font-size: 2.25rem; font-weight: 700; color: #6ee7b7; }
.stat-label { color: #8890a0; font-size: 0.85rem; margin-top: 0.25rem; }
table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
th { text-align: left; color: #8890a0; font-size: 0.8rem; padding: 0.5rem; border-bottom: 1px solid #262a36; }
td { padding: 0.75rem 0.5rem; border-bottom: 1px solid #1c1f2a; vertical-align: top; }
a { color: #93c5fd; text-decoration: none; }
.site-title { color: #c7cbd6; font-size: 0.85rem; }
.delta.pos { color: #6ee7b7; }
.delta.neg { color: #f87171; }
.delta.zero { color: #8890a0; }
.badge { display: inline-block; font-size: 0.7rem; padding: 0.1rem 0.45rem; border-radius: 999px; margin-left: 0.35rem; }
.badge.new { background: #1e3a2f; color: #6ee7b7; }
.badge.title-changed { background: #3a2f1e; color: #fbbf24; }
.badge.health.good { background: #1e3a2f; color: #6ee7b7; }
.badge.health.warn { background: #3a2f1e; color: #fbbf24; }
.badge.health.bad { background: #3a1e22; color: #f87171; }
.link-row.added { color: #6ee7b7; }
.link-row.removed { color: #f87171; }
.muted { color: #8890a0; }
.site-row.error td, .site-row.skipped td { color: #f87171; }
.no-prior { color: #8890a0; font-style: italic; margin: 1rem 0; }
.mover-card { background: #161923; border-radius: 12px; padding: 1.25rem 1.75rem; min-width: 220px; box-shadow: 0 1px 0 rgba(255,255,255,0.04) inset; border: 1px solid #262a36; }
.mover-card .mover-label { color: #8890a0; font-size: 0.85rem; }
.mover-card .mover-url { color: #93c5fd; font-weight: 600; word-break: break-all; }
.mover-card .mover-delta { font-size: 1.5rem; font-weight: 700; margin-top: 0.25rem; }
.mover-card .mover-delta.pos { color: #6ee7b7; }
.mover-card .mover-delta.neg { color: #f87171; }
"""

_JS = """
document.addEventListener('DOMContentLoaded', function () {
  var els = document.querySelectorAll('.stat-number');
  els.forEach(function (el) {
    var target = parseInt(el.getAttribute('data-target'), 10) || 0;
    var start = 0;
    var duration = 900;
    var startTime = null;
    function step(ts) {
      if (!startTime) startTime = ts;
      var progress = Math.min((ts - startTime) / duration, 1);
      el.textContent = Math.floor(start + (target - start) * progress);
      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        el.textContent = target;
      }
    }
    requestAnimationFrame(step);
  });
});
"""


def _mover_card(biggest_mover):
    if not biggest_mover:
        return ""
    delta = biggest_mover["word_count_delta"]
    tier = "pos" if delta > 0 else "neg" if delta < 0 else ""
    sign = "+" if delta > 0 else ""
    return (
        '<div class="mover-card">'
        '<div class="mover-label">Biggest mover</div>'
        f'<div class="mover-url">{_html.escape(biggest_mover["url"])}</div>'
        f'<div class="mover-delta {tier}">{sign}{delta} words</div>'
        "</div>"
    )


def render(snapshot, diff, out_path, health_scores=None, biggest_mover=None):
    """Render a self-contained dashboard.html from a snapshot dict and diff dict.

    `diff` may be None (first-ever run, nothing to compare against).
    `health_scores` (optional): {url: {"score": int, ...}} from
    lib.health.compute_health_scores(), rendered as a per-site badge.
    `biggest_mover` (optional): {"url", "word_count_delta"} from
    lib.diff.find_biggest_mover(), rendered as a callout card.
    """
    agg = _aggregate(snapshot, diff)
    per_site = diff["per_site"] if diff else {}

    stat_cards = "\n".join(
        [
            _stat_card("Sites tracked", "sites_tracked", agg["sites_tracked"]),
            _stat_card("Words scraped", "total_words", agg["total_words"]),
            _stat_card("Links found", "total_links", agg["total_links"]),
            _stat_card("Changes since last run", "total_changes", agg["total_changes"]),
        ]
    )
    mover_html = _mover_card(biggest_mover)

    no_prior_html = (
        '<p class="no-prior">No prior run to diff against &mdash; this is the first snapshot. '
        "Run again later to see what changed.</p>"
        if diff is None
        else ""
    )

    rows = "\n".join(
        _site_row(site, per_site.get(site.get("url", "")), health_scores)
        for site in snapshot.get("sites", [])
    )

    timestamp = _html.escape(str(snapshot.get("timestamp", "")))

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>MiniCrawl Dashboard</title>
<style>{_CSS}</style>
</head>
<body>
<h1>MiniCrawl Dashboard</h1>
<p class="subtitle">Snapshot: {timestamp}</p>
{no_prior_html}
<div class="stats">
{stat_cards}
{mover_html}
</div>
<table>
<thead>
<tr><th>Site</th><th>Words</th><th>Word &Delta;</th><th>Link changes</th></tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
<script>{_JS}</script>
</body>
</html>
"""

    with open(out_path, "w") as f:
        f.write(doc)
    return out_path
