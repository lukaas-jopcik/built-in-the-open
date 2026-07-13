import argparse
import sys

from barebrowse.fetch import FetchError
from barebrowse.snapshot import snapshot_url
from barebrowse.tokens import estimate_tokens


def cmd_snapshot(args):
    try:
        snap, final_url, html_text = snapshot_url(args.url, timeout=args.timeout)
    except FetchError as e:
        print(f"fetch error: {e}", file=sys.stderr)
        return 1

    print(snap.render())
    raw_tokens = estimate_tokens(html_text)
    snap_tokens = snap.token_count()
    reduction = 0.0
    if raw_tokens:
        reduction = 100.0 * (1 - snap_tokens / raw_tokens)
    print()
    print(f"url: {final_url}")
    print(f"raw html tokens: {raw_tokens}")
    print(f"snapshot tokens: {snap_tokens}")
    print(f"reduction: {reduction:.1f}%")
    print(f"refs: {len(snap.ref_index)}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="barebrowse")
    sub = parser.add_subparsers(dest="command", required=True)

    p_snap = sub.add_parser("snapshot", help="fetch a URL and print its pruned role-tree")
    p_snap.add_argument("url")
    p_snap.add_argument("--timeout", type=float, default=10)
    p_snap.set_defaults(func=cmd_snapshot)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
