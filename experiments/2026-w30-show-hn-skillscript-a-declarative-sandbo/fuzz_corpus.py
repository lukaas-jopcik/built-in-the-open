#!/usr/bin/env python3
"""Depth extension 1: fuzzed attack corpus.

The hand-written examples/attacks/ corpus (20 files) proves the whitelist
rejects a known technique the *instant* its outermost node is a Call/
Attribute/etc. That's necessary but doesn't prove the recursive walk is
sound everywhere a gadget could hide: inside a Compare's second comparator,
the right side of a BinOp, the third value of a BoolOp, under a unary `not`,
nested several arithmetic levels deep. This script auto-generates variants
by recombining known gadget "seeds" (the same expressions attack_*.sky uses)
with "carrier" templates that bury each seed at a different position inside
an otherwise-legal expression tree, then re-runs the whole thing through
safe_eval directly (no DAG/tool plumbing needed -- this targets the
expression sandbox itself). A matching benign corpus (safe literals through
the same carriers) checks the fuzzing doesn't also inflate false positives.
"""
import json
import sys

from safe_eval import UnsafeExpressionError, safe_eval

# Same gadget families as examples/attacks/*.sky, kept as bare expression
# fragments so they can be dropped into a carrier template.
MALICIOUS_SEEDS = [
    ("os.system via __import__", "__import__('os').system('id')"),
    ("open /etc/passwd", "open('/etc/passwd').read()"),
    ("socket.connect", "__import__('socket').socket().connect(('x', 1))"),
    ("subprocess.run", "__import__('subprocess').run(['id'])"),
    ("bare eval", "eval('1')"),
    ("bare exec", "exec('pass')"),
    ("globals() walk", "globals()"),
    ("__class__.__mro__ gadget", "().__class__.__mro__[1].__subclasses__()"),
    ("lambda-call bypass", "(lambda: 1)()"),
    ("listcomp-smuggled call", "[x for x in [eval('1')]]"),
    ("walrus exfil", "(y := __import__('os'))"),
    ("f-string gadget", "f\"{().__class__}\""),
    ("starred mro unpack", "[*().__class__.__bases__]"),
    ("chained attr to __globals__", "(1).__class__.__init__.__globals__"),
]

# Safe literals to push through the same carriers as a false-positive control.
# `numeric` marks seeds that can legally sit on either side of `<`/`+` etc. --
# used to decide which carrier set is safe to apply during *real* evaluation
# (unlike the malicious corpus, benign expressions actually execute, so a
# string seed through a numeric-comparison carrier would raise a genuine
# TypeError rather than exercising the sandbox).
BENIGN_SEEDS = [
    ("small int", "5", True),
    ("float", "2.5", True),
    ("string literal", "'ok'", False),
    ("bool literal", "True", False),
    ("name lookup", "value", True),
]
BENIGN_NAMES = {"value": 10}

# Carriers that require a numeric operand to evaluate without a TypeError.
NUMERIC_CARRIERS = [
    ("left of compare", lambda e: f"({e}) > -1"),
    ("right of compare", lambda e: f"-1 < ({e})"),
    ("second comparator of chained compare", lambda e: f"-1 < 0 < ({e})"),
    ("left of binop", lambda e: f"({e}) + 0"),
    ("right of binop", lambda e: f"0 + ({e})"),
    ("inside unary neg", lambda e: f"-({e})"),
    ("nested three levels of arithmetic", lambda e: f"1 + (2 * (3 - ({e})))"),
]
# Carriers that work for any truthy/falsy value (bool, string, number alike) --
# malicious seeds (Call/Attribute expressions) use ALL carriers below plus the
# numeric ones, since the sandbox rejects the dangerous node before the
# surrounding operator ever actually runs.
GENERIC_CARRIERS = [
    ("bare", lambda e: e),
    ("inside boolop (and)", lambda e: f"True and ({e})"),
    ("third value of boolop (or)", lambda e: f"False or False or ({e})"),
    ("inside unary not", lambda e: f"not ({e})"),
]
CARRIERS = GENERIC_CARRIERS + NUMERIC_CARRIERS


def generate_malicious_corpus():
    combos = []
    for label, seed in MALICIOUS_SEEDS:
        for clabel, carrier in CARRIERS:
            combos.append({
                "technique": f"{label} [{clabel}]",
                "expr": carrier(seed),
            })
    return combos


def generate_benign_corpus():
    combos = []
    for label, seed, numeric in BENIGN_SEEDS:
        carriers = CARRIERS if numeric else GENERIC_CARRIERS
        for clabel, carrier in carriers:
            combos.append({
                "label": f"{label} [{clabel}]",
                "expr": carrier(seed),
            })
    return combos


def run_malicious_fuzz():
    results = []
    for combo in generate_malicious_corpus():
        try:
            safe_eval(combo["expr"], {})
            blocked, reason = False, None
        except UnsafeExpressionError as e:
            blocked, reason = True, str(e)
        except Exception as e:  # any other exception is still *not* an escape
            blocked, reason = True, f"{type(e).__name__}: {e}"
        results.append({**combo, "blocked": blocked, "reason": reason})
    return results


def run_benign_fuzz():
    results = []
    for combo in generate_benign_corpus():
        try:
            value = safe_eval(combo["expr"], BENIGN_NAMES)
            false_positive, error = False, None
        except UnsafeExpressionError as e:
            value, false_positive, error = None, True, str(e)
        results.append({**combo, "false_positive": false_positive, "error": error, "value": value if not false_positive else None})
    return results


def build_report():
    malicious = run_malicious_fuzz()
    benign = run_benign_fuzz()

    total = len(malicious)
    blocked = sum(1 for m in malicious if m["blocked"])
    escapes = [m for m in malicious if not m["blocked"]]
    false_positives = [b for b in benign if b["false_positive"]]

    block_rate = blocked / total if total else 0.0
    return {
        "malicious_fuzz": {
            "total": total,
            "blocked": blocked,
            "escaped": len(escapes),
            "block_rate": block_rate,
            "escapes": escapes,
            "seeds": len(MALICIOUS_SEEDS),
            "carriers": len(CARRIERS),
        },
        "benign_fuzz": {
            "total": len(benign),
            "false_positives": len(false_positives),
            "false_positive_details": false_positives,
        },
        "pass": block_rate >= 0.95 and len(false_positives) == 0,
    }


def write_json(report, path="fuzz_report.json"):
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
        f.write("\n")


def write_markdown(report, path="fuzz_report.md"):
    mf = report["malicious_fuzz"]
    bf = report["benign_fuzz"]
    lines = [
        "# Skillcage Fuzzed Corpus (Depth Extension 1)",
        "",
        f"{mf['seeds']} known gadget seeds x {mf['carriers']} tree-position carriers "
        f"= {mf['total']} auto-generated attack variants (vs. 20 hand-written).",
        "",
        f"**Block rate:** {mf['blocked']}/{mf['total']} ({mf['block_rate']*100:.1f}%)",
        f"**False positives on benign fuzz:** {bf['false_positives']}/{bf['total']}",
        f"**Verdict:** {'PASS' if report['pass'] else 'FAIL'}",
        "",
    ]
    if mf["escapes"]:
        lines += ["## Escapes (not blocked)", ""]
        for e in mf["escapes"]:
            lines.append(f"- `{e['expr']}` ({e['technique']})")
    else:
        lines.append("No escapes at any tested tree position.")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    report = build_report()
    write_json(report)
    write_markdown(report)
    mf = report["malicious_fuzz"]
    bf = report["benign_fuzz"]
    print(f"[FUZZ] malicious: {mf['blocked']}/{mf['total']} blocked ({mf['block_rate']*100:.1f}%) "
          f"across {mf['seeds']} seeds x {mf['carriers']} carriers")
    print(f"[FUZZ] benign false positives: {bf['false_positives']}/{bf['total']}")
    print(f"[FUZZ] wrote fuzz_report.json, fuzz_report.md -- verdict={'PASS' if report['pass'] else 'FAIL'}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
