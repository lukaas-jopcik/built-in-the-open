"""Diff two snapshots (as produced by lib.store) by URL. Pure, in-memory, no I/O."""


def _site_map(snapshot):
    if not snapshot:
        return {}
    return {s["url"]: s for s in snapshot.get("sites", [])}


def diff_site(old_s, new_s):
    """Diff one site's old vs new metrics dict. old_s may be None (site is new)."""
    new_links = set(new_s.get("links", []) or [])
    old_links = set(old_s.get("links", []) or []) if old_s else set()
    added = sorted(new_links - old_links)
    removed = sorted(old_links - new_links)

    old_words = old_s.get("word_count") if old_s else None
    new_words = new_s.get("word_count")
    word_count_delta = (
        new_words - old_words if (old_words is not None and new_words is not None) else None
    )

    title_changed = bool(old_s) and old_s.get("title") != new_s.get("title")
    is_new = old_s is None

    changes = len(added) + len(removed)
    if word_count_delta:
        changes += 1
    if title_changed:
        changes += 1
    if is_new:
        changes += 1

    return {
        "added_links": added,
        "removed_links": removed,
        "word_count_delta": word_count_delta,
        "title_changed": title_changed,
        "is_new": is_new,
        "changes": changes,
    }


def diff_snapshots(old, new):
    """Compare two snapshot dicts by URL. `old` may be None (first-ever run)."""
    old_map = _site_map(old)
    new_map = _site_map(new)

    per_site = {}
    total_changes = 0
    for url, new_s in new_map.items():
        if "error" in new_s or "skipped" in new_s:
            per_site[url] = {
                "added_links": [],
                "removed_links": [],
                "word_count_delta": None,
                "title_changed": False,
                "is_new": url not in old_map,
                "changes": 0,
                "unavailable": True,
            }
            continue

        old_s = old_map.get(url)
        if old_s and ("error" in old_s or "skipped" in old_s):
            old_s = None  # no usable baseline to diff against

        entry = diff_site(old_s, new_s)
        per_site[url] = entry
        total_changes += entry["changes"]

    return {"per_site": per_site, "total_changes": total_changes}


def find_biggest_mover(diff):
    """Return {"url", "word_count_delta"} for the site with the largest absolute
    word-count swing this run, or None if there's no diff or no measurable delta.
    """
    if not diff:
        return None

    best_url, best_delta = None, 0
    for url, entry in diff["per_site"].items():
        delta = entry.get("word_count_delta")
        if delta is None:
            continue
        if abs(delta) > abs(best_delta):
            best_url, best_delta = url, delta

    if best_url is None:
        return None
    return {"url": best_url, "word_count_delta": best_delta}
