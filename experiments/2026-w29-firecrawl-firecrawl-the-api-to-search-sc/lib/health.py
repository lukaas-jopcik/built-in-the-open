"""Per-site health score: 0-100, based on fetch success rate across recent runs.

Pure function over already-loaded snapshot dicts - no I/O here, so it's
trivially unit-testable and callers (crawl.py) decide how many snapshots to
load and from where.
"""


def compute_health_scores(history, lookback=10):
    """history: list of loaded snapshot dicts, oldest first (as returned by
    lib.store.list_snapshots()/load_snapshot() in file order). Only the most
    recent `lookback` snapshots count towards the score, so a site that used
    to be flaky but has recovered isn't punished forever.

    Returns {url: {"score": int 0-100, "runs": int, "ok_runs": int}}.
    A site with zero observed runs never appears in the result.
    """
    recent = history[-lookback:] if lookback else history

    tally = {}
    for snap in recent:
        for site in snap.get("sites", []):
            url = site.get("url")
            if url is None:
                continue
            runs, ok_runs = tally.get(url, (0, 0))
            ok = "error" not in site and "skipped" not in site
            tally[url] = (runs + 1, ok_runs + (1 if ok else 0))

    return {
        url: {
            "score": round(100 * ok_runs / runs),
            "runs": runs,
            "ok_runs": ok_runs,
        }
        for url, (runs, ok_runs) in tally.items()
    }
