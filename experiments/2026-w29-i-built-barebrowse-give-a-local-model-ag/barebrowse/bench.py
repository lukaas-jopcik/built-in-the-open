"""Benchmark: raw-HTML tokens vs. pruned-snapshot tokens across a fixed list
of real public pages. Feeds the report.html payoff panel's headline number.

Fetch failures (timeout, 403, DNS, etc.) are logged and skipped rather than
crashing the whole run -- one flaky page shouldn't sink the benchmark.
"""
import argparse
import json
import os
import sys

if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from barebrowse.fetch import FetchError, fetch
from barebrowse.snapshot import build_snapshot
from barebrowse.tokens import estimate_tokens


def bench_page(url, timeout=10):
    """Fetch url, return a result dict, or None (with a printed reason) on failure."""
    try:
        final_url, html_text = fetch(url, timeout=timeout)
    except FetchError as e:
        print(f"  SKIP {url}: {e}")
        return None

    try:
        snapshot = build_snapshot(html_text, base_url=final_url)
    except Exception as e:  # malformed markup must not crash the whole benchmark
        print(f"  SKIP {url}: snapshot build failed: {e}")
        return None

    raw_tokens = estimate_tokens(html_text)
    snapshot_tokens = snapshot.token_count()
    reduction_pct = 100.0 * (raw_tokens - snapshot_tokens) / raw_tokens if raw_tokens else 0.0

    return {
        "url": url,
        "final_url": final_url,
        "raw_tokens": raw_tokens,
        "snapshot_tokens": snapshot_tokens,
        "reduction_pct": reduction_pct,
    }


def run_benchmark(urls, timeout=10):
    pages = []
    for url in urls:
        print(f"benchmarking {url} ...")
        result = bench_page(url, timeout=timeout)
        if result is not None:
            pages.append(result)
            print(f"  {result['raw_tokens']:,} -> {result['snapshot_tokens']:,} tokens "
                  f"({result['reduction_pct']:.1f}% cut)")

    mean_reduction_pct = (
        sum(p["reduction_pct"] for p in pages) / len(pages) if pages else 0.0
    )
    total_raw = sum(p["raw_tokens"] for p in pages)
    total_snapshot = sum(p["snapshot_tokens"] for p in pages)

    return {
        "pages": pages,
        "num_pages": len(pages),
        "num_requested": len(urls),
        "mean_reduction_pct": mean_reduction_pct,
        "total_raw_tokens": total_raw,
        "total_snapshot_tokens": total_snapshot,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Benchmark raw-HTML vs. snapshot token counts across real pages")
    parser.add_argument("--pages", default="pages.txt", help="path to a file of one URL per line")
    parser.add_argument("--out", default="bench_results.json")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(argv)

    with open(args.pages) as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    if len(urls) < 15:
        print(f"warning: only {len(urls)} pages listed, PRD asks for >=15", file=sys.stderr)

    results = run_benchmark(urls, timeout=args.timeout)

    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)

    print()
    print(f"pages benchmarked: {results['num_pages']}/{results['num_requested']}")
    print(f"mean token reduction: {results['mean_reduction_pct']:.1f}%")
    print(f"total tokens: {results['total_raw_tokens']:,} raw -> {results['total_snapshot_tokens']:,} snapshot")
    print(f"wrote {args.out}")

    return 0 if results["num_pages"] >= 15 else 1


if __name__ == "__main__":
    sys.exit(main())
