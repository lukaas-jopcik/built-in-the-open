#!/usr/bin/env python3
"""Stdlib-only SQLite-backed persistent memory store.

remember(text, tags) writes a fact; recall(query, k) reads facts back
ranked by relevance. Two separate process invocations of this CLI against
the same memory.db prove persistence across "sessions" with zero
long-running server.
"""

import argparse
import json
import math
import os
import re
import sqlite3
import sys
import time

DB_FILENAME = "memory.db"

# Simple cap: once the store holds more than this many facts, the oldest
# (by created_at) are evicted on the next remember() call. Keeps sustained
# writers from growing memory.db without bound; not an LRU/relevance policy
# (see prd.md "Out of scope").
MAX_FACTS = 5000


def db_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), DB_FILENAME)


def connect(path=None):
    conn = sqlite3.connect(path or db_path(), timeout=10.0)
    conn.execute("PRAGMA busy_timeout=10000")
    # Switching journal_mode to WAL and creating the schema both need a
    # brief exclusive lock. When many processes/threads race to open a
    # brand-new db file at once (see test_hardening's 40-way concurrency
    # test), that momentary lock can surface as "database is locked" even
    # with busy_timeout set, because SQLite's busy handler isn't always
    # engaged for the lock taken during a journal-mode switch. Retry with
    # backoff rather than letting a transient startup race crash the caller.
    last_err = None
    for attempt in range(20):
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    tags TEXT,
                    created_at REAL NOT NULL,
                    session INTEGER
                )
                """
            )
            conn.commit()
            return conn
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc) and "busy" not in str(exc):
                raise
            last_err = exc
            time.sleep(0.01 * (attempt + 1))
    raise last_err


_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text):
    return _WORD_RE.findall(text.lower())


def remember(text, tags=None, session=None, conn=None, now=None, max_facts=MAX_FACTS):
    """Persist a fact. Returns the new row id.

    If the store now holds more than `max_facts` rows, evicts the oldest
    (by created_at, ties broken by id) down to the cap so sustained writers
    can't grow memory.db without bound.
    """
    own_conn = conn is None
    conn = conn or connect()
    try:
        cur = conn.execute(
            "INSERT INTO facts (text, tags, created_at, session) VALUES (?, ?, ?, ?)",
            (text, ",".join(tags) if tags else "", now if now is not None else time.time(), session),
        )
        row_id = cur.lastrowid
        if max_facts is not None:
            total = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
            if total > max_facts:
                conn.execute(
                    """
                    DELETE FROM facts WHERE id IN (
                        SELECT id FROM facts ORDER BY created_at ASC, id ASC
                        LIMIT ?
                    )
                    """,
                    (total - max_facts,),
                )
        conn.commit()
        return row_id
    finally:
        if own_conn:
            conn.close()


def _overlap_score(query_words, fact_words):
    if not query_words or not fact_words:
        return 0.0
    query_set = set(query_words)
    fact_set = set(fact_words)
    shared = query_set & fact_set
    if not shared:
        return 0.0
    # Jaccard-ish overlap, weighted toward query coverage so short facts
    # that fully match a query score highest.
    return len(shared) / len(query_set | fact_set) + 0.5 * (len(shared) / len(query_set))


def recall(query, k=5, conn=None):
    """Return up to k facts ranked by keyword overlap with query."""
    own_conn = conn is None
    conn = conn or connect()
    try:
        rows = conn.execute(
            "SELECT id, text, tags, created_at, session FROM facts"
        ).fetchall()
    finally:
        if own_conn:
            conn.close()

    query_words = _tokenize(query)
    scored = []
    for row_id, text, tags, created_at, session in rows:
        score = _overlap_score(query_words, _tokenize(text))
        if score > 0:
            scored.append(
                {
                    "id": row_id,
                    "text": text,
                    "tags": tags.split(",") if tags else [],
                    "created_at": created_at,
                    "session": session,
                    "score": round(score, 4),
                }
            )

    scored.sort(key=lambda r: (r["score"], r["created_at"]), reverse=True)
    return scored[:k]


def adaptive_recall(
    query,
    k=5,
    half_life_sessions=10.0,
    keyword_weight=0.6,
    recency_weight=0.4,
    current_session=None,
    conn=None,
):
    """Rank facts by keyword overlap blended with exponential recency decay.

    When facts and the caller both carry a session number (as the Slice 3
    benchmark does), recency decays across simulated sessions using
    `half_life_sessions`. Otherwise it falls back to elapsed wall-clock
    minutes so the MCP/demo path still produces a sane ranking without
    session bookkeeping. A fact must have nonzero keyword overlap to surface
    at all -- recency alone never resurfaces an irrelevant fact.
    """
    own_conn = conn is None
    conn = conn or connect()
    try:
        rows = conn.execute(
            "SELECT id, text, tags, created_at, session FROM facts"
        ).fetchall()
    finally:
        if own_conn:
            conn.close()

    query_words = _tokenize(query)
    now = time.time()
    scored = []
    for row_id, text, tags, created_at, session in rows:
        kw_score = _overlap_score(query_words, _tokenize(text))
        if kw_score <= 0:
            continue

        if current_session is not None and session is not None:
            elapsed = max(0.0, current_session - session)
        else:
            elapsed = max(0.0, (now - created_at) / 60.0)

        recency_score = math.exp(-math.log(2) * elapsed / half_life_sessions)
        blended = keyword_weight * kw_score + recency_weight * recency_score

        scored.append(
            {
                "id": row_id,
                "text": text,
                "tags": tags.split(",") if tags else [],
                "created_at": created_at,
                "session": session,
                "keyword_score": round(kw_score, 4),
                "recency_score": round(recency_score, 4),
                "score": round(blended, 4),
            }
        )

    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[:k]


def _cli():
    parser = argparse.ArgumentParser(description="Persistent memory core CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_remember = sub.add_parser("remember", help="Store a fact")
    p_remember.add_argument("text")
    p_remember.add_argument("--tags", default="", help="Comma-separated tags")

    p_recall = sub.add_parser("recall", help="Retrieve facts matching a query")
    p_recall.add_argument("query")
    p_recall.add_argument("--k", type=int, default=5)
    p_recall.add_argument("--json", action="store_true", help="Emit JSON output")

    args = parser.parse_args()

    if args.command == "remember":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        row_id = remember(args.text, tags=tags)
        print(f"Remembered (id={row_id}): {args.text}")
    elif args.command == "recall":
        results = recall(args.query, k=args.k)
        if args.json:
            print(json.dumps(results))
        elif not results:
            print("(no matching facts)")
        else:
            for i, r in enumerate(results, 1):
                tag_str = f" (tags: {', '.join(r['tags'])})" if r["tags"] else ""
                print(f"{i}. [score={r['score']}] {r['text']}{tag_str}")


if __name__ == "__main__":
    _cli()
