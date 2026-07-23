"""Whitelisted mock tool registry. Every tool is a pure function of
(inputs, args, ctx) -> JSON-serializable result. No network, no subprocess."""
import json
import os
import time

from safe_eval import safe_eval


class ToolError(RuntimeError):
    pass


def _resolve_fixture_path(ctx, filename):
    base = os.path.abspath(ctx["base_dir"])
    path = os.path.abspath(os.path.join(base, filename))
    if not (path == base or path.startswith(base + os.sep)):
        raise ToolError(f"fixture path escapes base dir: {filename}")
    return path


def fetch(inputs, args, ctx):
    """Read a local JSON fixture. args: {'file': 'fixtures/a.json'}"""
    filename = args.get("file")
    if not filename:
        raise ToolError("fetch requires args.file")
    path = _resolve_fixture_path(ctx, filename)
    with open(path, "r") as f:
        return json.load(f)


def transform(inputs, args, ctx):
    """Apply a named op to the single dependency's 'items' list.
    args: {'op': 'double_values'}"""
    if len(inputs) != 1:
        raise ToolError("transform expects exactly one dependency")
    (data,) = inputs.values()
    op = args.get("op")
    items = data.get("items", [])
    if op == "double_values":
        out = [dict(it, value=it["value"] * 2) for it in items]
    elif op == "identity":
        out = list(items)
    else:
        raise ToolError(f"unknown transform op: {op}")
    return {"items": out}


def filter_step(inputs, args, ctx):
    """Filter the single dependency's 'items' list by a safe predicate.
    args: {'predicate': 'value > 5'}"""
    if len(inputs) != 1:
        raise ToolError("filter_step expects exactly one dependency")
    (data,) = inputs.values()
    predicate = args.get("predicate", "True")
    items = data.get("items", [])
    out = [it for it in items if safe_eval(predicate, dict(it))]
    return {"items": out}


def aggregate(inputs, args, ctx):
    """Combine all dependency 'items' lists (in dep order) and sum 'value'."""
    combined = []
    for dep_result in inputs.values():
        combined.extend(dep_result.get("items", []))
    total = sum(it.get("value", 0) for it in combined)
    return {"items": combined, "total": total, "count": len(combined)}


def report_step(inputs, args, ctx):
    """Build the final report dict from the single dependency's aggregate."""
    if len(inputs) != 1:
        raise ToolError("report_step expects exactly one dependency")
    (data,) = inputs.values()
    return {
        "status": "ok",
        "total": data.get("total", 0),
        "count": data.get("count", 0),
        "items": data.get("items", []),
    }


def evaluate(inputs, args, ctx):
    """Evaluate a sandboxed user expression through the AST-whitelist.
    args: {'expr': '...'}. Any dependency dict's keys become names available
    inside the expression. This is the tool the attack corpus targets."""
    expr = args.get("expr")
    if expr is None:
        raise ToolError("evaluate requires args.expr")
    names = {}
    for dep_result in inputs.values():
        if isinstance(dep_result, dict):
            names.update(dep_result)
    return {"result": safe_eval(expr, names)}


def scoreboard_step(inputs, args, ctx):
    """Summarize how many dependency steps were sandbox-blocked vs. completed."""
    total = len(inputs)
    blocked = sum(1 for r in inputs.values() if isinstance(r, dict) and r.get("__blocked__"))
    escaped = total - blocked
    return {
        "status": "blocked" if escaped == 0 else "partial",
        "total": total,
        "blocked": blocked,
        "escaped": escaped,
    }


def slow_step(inputs, args, ctx):
    """Sleeps args.get('delay_ms', 50)ms then returns one 'items' entry
    {'name': args.get('name'), 'value': args.get('value', 0)} -- shaped so it
    composes directly with aggregate/report_step like fetch's output.
    Exists purely to make concurrency measurable: N independent slow_step
    branches take N*delay sequentially but ~1*delay when fanned out across a
    thread pool (see run_sky_parallel / parallel_bench.py). time.sleep is a
    pure stdlib wall-clock wait, no I/O, no network."""
    delay_ms = args.get("delay_ms", 50)
    time.sleep(delay_ms / 1000.0)
    return {"items": [{"name": args.get("name", "branch"), "value": args.get("value", 0)}]}


TOOLS = {
    "fetch": fetch,
    "transform": transform,
    "filter_step": filter_step,
    "aggregate": aggregate,
    "report_step": report_step,
    "evaluate": evaluate,
    "scoreboard_step": scoreboard_step,
    "slow_step": slow_step,
}
