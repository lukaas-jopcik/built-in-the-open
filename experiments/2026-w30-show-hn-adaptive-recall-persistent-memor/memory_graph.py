#!/usr/bin/env python3
"""Depth extension #4: a second, differently-shaped wow visual.

Reads the benchmark's `results.json` (no recompute, no new randomness --
same underlying run as the split-screen dashboard) and re-shapes it into a
force-directed graph dataset: one "fact" node per planted fact, one "query"
node per recall attempt against it (+5/+10/+20 sessions later), and an edge
between them colored by whether the adaptive-recall agent answered that
query correctly. The browser lays the graph out itself (simple physics
simulation in plain JS/SVG, no charting deps) so the same 50-fact/150-query
benchmark tells its story as a graph instead of a grid.
"""

import argparse
import json


def build_graph(results):
    nodes = []
    edges = []
    for convo in results["conversations"]:
        fact_id = f"f{convo['index']}"
        nodes.append(
            {
                "id": fact_id,
                "type": "fact",
                "label": f"{convo['subject']} · {convo['template']}",
                "template": convo["template"],
            }
        )
        for q in convo["queries"]:
            query_id = f"q{convo['index']}_{q['delta']}"
            nodes.append(
                {
                    "id": query_id,
                    "type": "query",
                    "label": f"+{q['delta']}",
                    "delta": q["delta"],
                    "adaptive_correct": q["adaptive_correct"],
                    "baseline_correct": q["baseline_correct"],
                    "adaptive_score": q["adaptive_score"],
                }
            )
            edges.append(
                {
                    "source": fact_id,
                    "target": query_id,
                    "correct": q["adaptive_correct"],
                }
            )

    by_delta = {}
    for convo in results["conversations"]:
        for q in convo["queries"]:
            d = by_delta.setdefault(
                q["delta"], {"correct": 0, "total": 0}
            )
            d["total"] += 1
            d["correct"] += int(q["adaptive_correct"])

    return {
        "seed": results["seed"],
        "num_conversations": results["num_conversations"],
        "total_queries": results["total_queries"],
        "adaptive_correct": results["adaptive_correct"],
        "adaptive_accuracy": results["adaptive_accuracy"],
        "baseline_accuracy": results["baseline_accuracy"],
        "by_delta": [
            {"delta": d, "correct": v["correct"], "total": v["total"]}
            for d, v in sorted(by_delta.items())
        ],
        "nodes": nodes,
        "edges": edges,
    }


def render(graph, out_path, template_path):
    with open(template_path, "r") as f:
        template = f.read()
    html = template.replace("/*__GRAPH_JSON__*/null", json.dumps(graph))
    with open(out_path, "w") as f:
        f.write(html)


def _cli():
    parser = argparse.ArgumentParser(
        description="Render the memory recall graph from results.json"
    )
    parser.add_argument("--results", default="results.json")
    parser.add_argument("--out", default="memory_graph.html")
    parser.add_argument("--template", default="memory_graph_template.html")
    args = parser.parse_args()

    with open(args.results, "r") as f:
        results = json.load(f)

    graph = build_graph(results)
    render(graph, args.out, args.template)
    print(
        f"Wrote {args.out}: {len(graph['nodes'])} nodes / {len(graph['edges'])} edges "
        f"({graph['adaptive_correct']}/{graph['total_queries']} correct edges)"
    )


if __name__ == "__main__":
    _cli()
