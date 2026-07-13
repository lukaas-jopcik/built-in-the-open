#!/usr/bin/env python3
"""MiniCrawl: fetch a list of public sites, snapshot, diff against the previous
run, and render a self-contained dashboard.html. Stdlib only. See prd.md.
"""
import argparse
import json
import sys

from lib import dashboard, diff as diff_lib, fetcher, health, store


def load_sites(path):
    with open(path) as f:
        return json.load(f)


def fetch_with_retry(url, timeout, retries):
    """Fetch url, retrying up to `retries` extra times on any exception.
    Never raises - returns an {"error": ...} dict on final failure so a single
    flaky/unreachable site can never take down the whole run.
    """
    last_err = None
    for attempt in range(retries + 1):
        try:
            return fetcher.fetch(url, timeout=timeout)
        except Exception as e:
            last_err = e
    return {"url": url, "error": f"{type(last_err).__name__}: {last_err}"}


def run_crawl(sites, timeout=10, retries=1):
    return [fetch_with_retry(url, timeout, retries) for url in sites]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sites", default="sites.json", help="JSON file with a list of seed URLs")
    ap.add_argument("--out", default="dashboard.html", help="path to write the rendered dashboard HTML")
    ap.add_argument("--data-dir", default=store.RUNS_DIR, help="directory to read/write snapshot JSON files")
    ap.add_argument("--timeout", type=float, default=10, help="per-site fetch timeout in seconds")
    ap.add_argument("--retries", type=int, default=1, help="extra fetch attempts per site on failure")
    args = ap.parse_args(argv)

    sites = load_sites(args.sites)

    # Snapshot the *previous* run (if any) before this run's file lands in the
    # same directory, so "previous" and "current" can never both resolve to
    # the file we're about to write.
    prev_paths = store.list_snapshots(args.data_dir)
    old_snapshot = store.load_snapshot(prev_paths[-1]) if prev_paths else None

    results = run_crawl(sites, timeout=args.timeout, retries=args.retries)
    path = store.save_snapshot(results, runs_dir=args.data_dir)
    new_snapshot = store.load_snapshot(path)

    d = diff_lib.diff_snapshots(old_snapshot, new_snapshot) if old_snapshot else None

    # Health scores need the *full* history including this run, so recompute
    # the snapshot list after save_snapshot() has written the new file.
    history = [store.load_snapshot(p) for p in store.list_snapshots(args.data_dir)]
    health_scores = health.compute_health_scores(history)
    biggest_mover = diff_lib.find_biggest_mover(d) if d else None

    dashboard.render(new_snapshot, d, args.out, health_scores=health_scores, biggest_mover=biggest_mover)

    print(f"Saved snapshot: {path}")
    ok_count = 0
    for r in results:
        if "error" in r:
            print(f"  FAIL {r['url']}: {r['error']}")
        elif "skipped" in r:
            print(f"  SKIP {r['url']}: {r['skipped']}")
        else:
            ok_count += 1
            print(
                f"  OK   {r['url']}: title={r['title']!r} "
                f"words={r['word_count']} links={r['link_count']} images={r['image_count']}"
            )
    print(f"{ok_count}/{len(sites)} sites fetched successfully")
    print(f"Changes since last run: {d['total_changes'] if d else '(no prior run)'}")
    print(f"Dashboard: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
