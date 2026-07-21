#!/usr/bin/env python3
"""Deterministic 50-conversation adaptive-recall vs stateless-baseline benchmark.

No LLM calls, no network. Each "conversation" plants one fact (a unique
subject + a template category + a slot value) in an early session, then is
queried three times later (at +5 / +10 / +20 sessions) about that fact,
interleaved with the other conversations' facts acting as realistic
distractor noise in the same shared memory store.

Two recall strategies answer every query:
  - stateless baseline: has no persistent memory at all, so it can only
    guess a plausible slot value at random (same guess distribution a
    memory-less agent hallucinating a plausible-sounding answer would use).
  - adaptive recall: looks the query up in `memory_core.adaptive_recall`
    against the shared, growing memory store.

Both use the same seeded `random.Random` instance so results are fully
reproducible: running this script twice with the same --seed produces a
byte-identical results.json.
"""

import argparse
import json
import random

import memory_core

SUBJECTS = [
    "Priya", "Marcus", "Elena", "Devon", "Yuki", "Fatima", "Carlos", "Ingrid",
    "Kwame", "Sanjay", "Nadia", "Omar", "Bianca", "Theo", "Aisha", "Lars",
    "Mei", "Rafael", "Greta", "Jonas", "Amara", "Viktor", "Lucia", "Hassan",
    "Sofia", "Dmitri", "Wren", "Tobias", "Layla", "Ezra", "Noor", "Callum",
    "Mireille", "Anders", "Zola", "Emeka", "Ingrid", "Petra", "Kai", "Rosa",
    "Malik", "Tessa", "Ravi", "Ines", "Boaz", "Selin", "Otis", "Freya",
    "Idris", "Camille",
]

TEMPLATES = [
    {
        "key": "launch_date",
        "fact": "{subj}'s project launch date is {value}.",
        "query": "what is {subj}'s project launch date?",
        "values": [
            "March 3", "April 12", "May 19", "June 7", "July 22",
            "August 4", "September 15", "October 9", "November 2",
            "December 18", "January 27", "February 14",
        ],
    },
    {
        "key": "meeting_day",
        "fact": "{subj} said the team meeting moved to {value}.",
        "query": "what day is {subj}'s team meeting?",
        "values": [
            "Monday morning", "Monday afternoon", "Tuesday morning",
            "Tuesday afternoon", "Wednesday morning", "Wednesday afternoon",
            "Thursday morning", "Thursday afternoon", "Friday morning",
            "Friday afternoon", "Saturday morning", "Sunday evening",
        ],
    },
    {
        "key": "budget",
        "fact": "{subj}'s department budget for this quarter is {value}.",
        "query": "what is {subj}'s department budget?",
        "values": [
            "$12,000", "$18,500", "$24,000", "$31,250", "$45,000",
            "$52,750", "$60,000", "$77,300", "$88,000", "$95,500",
            "$103,000", "$120,000",
        ],
    },
    {
        "key": "office_location",
        "fact": "{subj} moved desks to {value}.",
        "query": "where does {subj} sit now?",
        "values": [
            "the 2nd floor", "the 3rd floor west wing", "desk 14B",
            "the annex", "the quiet room", "the 5th floor",
            "the corner pod", "desk 22", "the mezzanine",
            "the north wing", "the lab bench", "the 7th floor",
        ],
    },
    {
        "key": "codename",
        "fact": "{subj}'s project codename is {value}.",
        "query": "what is {subj}'s project codename?",
        "values": [
            "Ironwood", "Blue Kestrel", "Quiet Harbor", "Redshift",
            "Amber Ridge", "Nightjar", "Sable Line", "Windmill",
            "Cobalt Run", "Loose Thread", "Paper Crane", "Longview",
        ],
    },
    {
        "key": "vacation",
        "fact": "{subj} is taking vacation starting {value}.",
        "query": "when does {subj}'s vacation start?",
        "values": [
            "March 1", "April 8", "May 20", "June 3", "July 14",
            "August 25", "September 9", "October 30", "November 11",
            "December 5", "January 6", "February 21",
        ],
    },
    {
        "key": "team_lead",
        "fact": "{subj}'s new team lead is {value}.",
        "query": "who is {subj}'s team lead?",
        "values": [
            "Bertrand", "Aiko", "Simone", "Felix", "Nia", "Grigor",
            "Paloma", "Watanabe", "Delphine", "Osman", "Marguerite",
            "Ezio",
        ],
    },
    {
        "key": "wifi_hint",
        "fact": "{subj} said the office wifi hint is {value}.",
        "query": "what is the office wifi hint {subj} mentioned?",
        "values": [
            "blue umbrella", "old lighthouse", "seven ravens",
            "tall pines", "quiet river", "copper kettle",
            "green door", "north star", "loud static",
            "small anchor", "wide field", "long shadow",
        ],
    },
    {
        "key": "lunch_order",
        "fact": "{subj}'s standing lunch order is {value}.",
        "query": "what is {subj}'s standing lunch order?",
        "values": [
            "a falafel wrap", "miso ramen", "a veggie burrito",
            "pad see ew", "a turkey club", "shakshuka",
            "a poke bowl", "dumplings", "a caprese sandwich",
            "khao soi", "a quinoa salad", "jollof rice",
        ],
    },
    {
        "key": "flight",
        "fact": "{subj}'s flight number for the conference is {value}.",
        "query": "what is {subj}'s flight number for the conference?",
        "values": [
            "AA 204", "UA 815", "DL 47", "BA 112", "LH 933", "AF 226",
            "QF 8", "EK 201", "SQ 21", "KL 605", "NH 9", "AC 850",
        ],
    },
]


def build_conversations(num, rng):
    conversations = []
    for i in range(num):
        template = TEMPLATES[i % len(TEMPLATES)]
        subj = SUBJECTS[i % len(SUBJECTS)]
        value = template["values"][rng.randrange(len(template["values"]))]
        plant_session = rng.randint(1, 5)
        conversations.append(
            {
                "index": i,
                "template": template["key"],
                "subject": subj,
                "value": value,
                "fact_text": template["fact"].format(subj=subj, value=value),
                "query_text": template["query"].format(subj=subj),
                "candidate_values": template["values"],
                "plant_session": plant_session,
            }
        )
    return conversations


def run_benchmark(num_sessions, seed):
    rng = random.Random(seed)
    conversations = build_conversations(num_sessions, rng)

    # Plant every fact into one shared, growing memory store -- the other
    # conversations' facts are the distractor noise for adaptive recall.
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
    total_correct_baseline = 0
    total_correct_adaptive = 0
    total_queries = 0

    for convo in conversations:
        convo["queries"] = []
        for delta in deltas:
            query_session = convo["plant_session"] + delta

            guess = convo["candidate_values"][
                rng.randrange(len(convo["candidate_values"]))
            ]
            baseline_correct = guess == convo["value"]

            top = memory_core.adaptive_recall(
                convo["query_text"],
                k=1,
                current_session=query_session,
                conn=conn,
            )
            adaptive_correct = bool(top) and top[0]["text"] == convo["fact_text"]
            adaptive_score = top[0]["score"] if top else 0.0

            convo["queries"].append(
                {
                    "delta": delta,
                    "query_session": query_session,
                    "baseline_correct": baseline_correct,
                    "adaptive_correct": adaptive_correct,
                    "adaptive_score": adaptive_score,
                }
            )

            total_queries += 1
            total_correct_baseline += int(baseline_correct)
            total_correct_adaptive += int(adaptive_correct)

    conn.close()

    results = {
        "seed": seed,
        "num_conversations": num_sessions,
        "queries_per_conversation": len(deltas),
        "total_queries": total_queries,
        "baseline_correct": total_correct_baseline,
        "adaptive_correct": total_correct_adaptive,
        "baseline_accuracy": round(total_correct_baseline / total_queries, 4),
        "adaptive_accuracy": round(total_correct_adaptive / total_queries, 4),
        "conversations": [
            {
                "index": c["index"],
                "template": c["template"],
                "subject": c["subject"],
                "value": c["value"],
                "plant_session": c["plant_session"],
                "queries": c["queries"],
            }
            for c in conversations
        ],
    }
    return results


DASHBOARD_TEMPLATE = None  # populated by _load_template()


def render_dashboard(results, out_path, template_path):
    with open(template_path, "r") as f:
        template = f.read()
    html = template.replace(
        "/*__RESULTS_JSON__*/null", json.dumps(results)
    )
    with open(out_path, "w") as f:
        f.write(html)


def _cli():
    parser = argparse.ArgumentParser(description="Adaptive recall benchmark")
    parser.add_argument("--sessions", type=int, default=50, help="Number of simulated conversations")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="results.json")
    parser.add_argument("--dashboard-out", default="dashboard.html")
    parser.add_argument(
        "--dashboard-template",
        default="dashboard_template.html",
        help="Static HTML/CSS/JS shell that results are embedded into",
    )
    parser.add_argument(
        "--no-dashboard",
        action="store_true",
        help="Skip regenerating dashboard.html (results.json only)",
    )
    args = parser.parse_args()

    results = run_benchmark(args.sessions, args.seed)

    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)
        f.write("\n")

    print(
        f"Wrote {args.out}: baseline_accuracy={results['baseline_accuracy']} "
        f"adaptive_accuracy={results['adaptive_accuracy']} "
        f"({results['adaptive_correct']}/{results['total_queries']} vs "
        f"{results['baseline_correct']}/{results['total_queries']})"
    )

    if not args.no_dashboard:
        render_dashboard(results, args.dashboard_out, args.dashboard_template)
        print(f"Wrote {args.dashboard_out}")


if __name__ == "__main__":
    _cli()
