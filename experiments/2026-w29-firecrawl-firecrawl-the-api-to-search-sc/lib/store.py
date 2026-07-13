"""Flat-file JSON snapshot storage (stdlib only, no database)."""
import datetime
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS_DIR = os.path.join(BASE_DIR, "data", "runs")


def ensure_dir(runs_dir=RUNS_DIR):
    os.makedirs(runs_dir, exist_ok=True)


def save_snapshot(results, runs_dir=RUNS_DIR, timestamp=None):
    ensure_dir(runs_dir)
    # Microsecond precision (not just seconds) so two runs fired back-to-back
    # in the same second - e.g. the end-to-end test, or a demo double-run -
    # still get distinct filenames/timestamps instead of one overwriting the other.
    ts = timestamp or datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    path = os.path.join(runs_dir, f"{ts}.json")
    with open(path, "w") as f:
        json.dump({"timestamp": ts, "sites": results}, f, indent=2)
    return path


def list_snapshots(runs_dir=RUNS_DIR):
    ensure_dir(runs_dir)
    files = sorted(f for f in os.listdir(runs_dir) if f.endswith(".json"))
    return [os.path.join(runs_dir, f) for f in files]


def load_snapshot(path):
    with open(path) as f:
        return json.load(f)


def latest_two(runs_dir=RUNS_DIR):
    """Return (previous, current) loaded snapshots, or (None, current)/(None, None)."""
    paths = list_snapshots(runs_dir)
    if not paths:
        return None, None
    if len(paths) == 1:
        return None, load_snapshot(paths[-1])
    return load_snapshot(paths[-2]), load_snapshot(paths[-1])
