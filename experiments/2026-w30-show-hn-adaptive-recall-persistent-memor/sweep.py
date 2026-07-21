#!/usr/bin/env python3
"""Depth extension: parameter-sensitivity mini-benchmark.

Sweeps `adaptive_recall`'s half_life_sessions (recency-decay knob) and
keyword_weight (keyword-vs-recency blend knob) across the same 50-conversation,
150-query benchmark set used by benchmark.py, and reports adaptive-recall
accuracy for every combination -- "here's the knob and here's the tradeoff",
not just the single (10.0, 0.6) default point already shown on the main
dashboard.

Deterministic and stdlib-only, same as benchmark.py: same --seed produces
the same conversations and therefore a byte-identical sweep_results.json.
"""

import argparse
import json

import benchmark
import memory_core

HALF_LIVES = [5.0, 10.0, 20.0, 50.0]
KEYWORD_WEIGHTS = [0.2, 0.4, 0.6, 0.8]


def run_sweep(num_sessions, seed):
    rng = __import__("random").Random(seed)
    conversations = benchmark.build_conversations(num_sessions, rng)

    conn = memory_core.connect(":memory:")
    for convo in conversations:
        memory_core.remember(
            convo["fact_text"],
            tags=[convo["template"]],
            session=convo["plant_session"],
            conn=conn,
            now=0.0,
        )

    deltas = [5, 10, 20]
    total_queries = num_sessions * len(deltas)

    cells = []
    for half_life in HALF_LIVES:
        for kw_weight in KEYWORD_WEIGHTS:
            correct = 0
            for convo in conversations:
                for delta in deltas:
                    query_session = convo["plant_session"] + delta
                    top = memory_core.adaptive_recall(
                        convo["query_text"],
                        k=1,
                        half_life_sessions=half_life,
                        keyword_weight=kw_weight,
                        recency_weight=1.0 - kw_weight,
                        current_session=query_session,
                        conn=conn,
                    )
                    if top and top[0]["text"] == convo["fact_text"]:
                        correct += 1
            cells.append(
                {
                    "half_life_sessions": half_life,
                    "keyword_weight": kw_weight,
                    "recency_weight": round(1.0 - kw_weight, 4),
                    "correct": correct,
                    "total": total_queries,
                    "accuracy": round(correct / total_queries, 4),
                }
            )

    conn.close()

    best = max(cells, key=lambda c: c["accuracy"])
    worst = min(cells, key=lambda c: c["accuracy"])

    return {
        "seed": seed,
        "num_conversations": num_sessions,
        "total_queries": total_queries,
        "half_lives": HALF_LIVES,
        "keyword_weights": KEYWORD_WEIGHTS,
        "default_point": {"half_life_sessions": 10.0, "keyword_weight": 0.6},
        "cells": cells,
        "best": best,
        "worst": worst,
    }


def render_dashboard(results, out_path, template_path):
    with open(template_path, "r") as f:
        template = f.read()
    html = template.replace("/*__SWEEP_JSON__*/null", json.dumps(results))
    with open(out_path, "w") as f:
        f.write(html)


def _cli():
    parser = argparse.ArgumentParser(description="Parameter-sensitivity sweep")
    parser.add_argument("--sessions", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="sweep_results.json")
    parser.add_argument("--dashboard-out", default="sweep_dashboard.html")
    parser.add_argument("--dashboard-template", default="sweep_dashboard_template.html")
    parser.add_argument("--no-dashboard", action="store_true")
    args = parser.parse_args()

    results = run_sweep(args.sessions, args.seed)

    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)
        f.write("\n")

    print(
        f"Wrote {args.out}: best={results['best']['half_life_sessions']}hl/"
        f"{results['best']['keyword_weight']}kw={results['best']['accuracy']} "
        f"worst={results['worst']['half_life_sessions']}hl/"
        f"{results['worst']['keyword_weight']}kw={results['worst']['accuracy']}"
    )

    if not args.no_dashboard:
        render_dashboard(results, args.dashboard_out, args.dashboard_template)
        print(f"Wrote {args.dashboard_out}")


if __name__ == "__main__":
    _cli()
