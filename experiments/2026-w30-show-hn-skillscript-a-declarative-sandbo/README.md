# Skillcage

A tiny declarative DSL (`.sky` files) that orchestrates chained "tool calls"
as a DAG, executes every step inside a pure-Python AST-whitelist sandbox, and
replays the run as an animated HTML dashboard — so a step that tries to
`os.system(...)`, read `/etc/passwd`, or pull off a `.__class__.__mro__`
gadget escape gets caught and flashed red instead of silently running.

This doc is for someone who wants to drop in their own tools/recipes
tomorrow. For the design rationale and success criteria, see `prd.md`. For
the iteration-by-iteration build history, see `build-log.md`.

## Quickstart

```bash
python3 -m unittest discover tests/          # 58+ unit tests
python3 run.py examples/report.sky           # sequential DAG run -> report.json
python3 run.py --parallel examples/parallel_fanout.sky   # concurrent wave execution
python3 run.py examples/malicious.sky        # 10 attack techniques, all blocked
python3 benchmark.py                         # 20-attack corpus + false-positive + overhead
python3 fuzz_corpus.py                       # 154 auto-generated gadget variants
python3 parallel_bench.py                    # measured sequential-vs-parallel speedup
python3 -m http.server 8000                  # then open http://localhost:8000/dashboard.html
python3 replay.py                            # same demo, as a paced terminal replay
```

`dashboard.html` reads `trace.jsonl`. Regenerate it with `python3 gen_trace.py`
any time you change a `.sky` file or a tool and want the animation to reflect it.

No browser handy, or want something LinkedIn-postable that isn't a screen
recording of a browser tab? `replay.py` re-plays the exact same trace data
`gen_trace.py` builds (clean run, then attack run, then parallel fan-out) as
colored, `time.sleep`-paced terminal output, with the same pacing constants
and scoreboard/speedup wording as the dashboard so the two artifacts read as
one demo. It's plain stdout with ANSI codes, so it's asciinema-ready:

```bash
asciinema rec skillcage-demo.cast -c 'python3 replay.py'
```

Pass `--fast` (or set `SKILLCAGE_REPLAY_FAST=1`) to skip the pacing and dump
the whole trace instantly — that's what `tests/test_replay.py` does.

## Anatomy of a `.sky` file

`.sky` files are plain JSON (no PyYAML, no custom parser) — see `dsl.py`.

```json
{
  "steps": [
    {"id": "fetch_a", "tool": "fetch", "args": {"file": "fixtures/a.json"}},
    {"id": "filtered", "tool": "filter_step", "deps": ["fetch_a"], "args": {"predicate": "value > 5"}},
    {"id": "report", "tool": "report_step", "deps": ["filtered"], "args": {}}
  ],
  "output": "my_report.json"
}
```

- `id` — unique string, referenced by other steps' `deps`.
- `tool` — a key into the `TOOLS` registry in `tools.py`.
- `deps` — list of step ids that must run first; their results are passed
  into this step's `inputs` dict keyed by id. Omit for no deps (defaults to `[]`).
- `args` — arbitrary JSON passed to the tool as-is. Omit for `{}`.
- `output` (top-level, optional) — where `run.py` writes the final step's
  result. Defaults to `report.json`.

The engine (`dag.py`) topologically sorts steps by `deps`, so **order in the
file doesn't matter** — only the dependency edges do. Unknown deps, cycles,
and duplicate ids all raise a clear `ValueError` before anything executes.

There are no loops, conditionals, or user-defined functions in the DSL —
by design (see `prd.md`'s Out of scope). It's steps + a DAG + one safe
expression language for predicates, not a general-purpose language.

## Adding your own tool

Every tool is a plain Python function with signature
`(inputs: dict, args: dict, ctx: dict) -> JSON-serializable result`, added to
the `TOOLS` dict at the bottom of `tools.py`:

```python
def word_count(inputs, args, ctx):
    """Count words across all dependency 'text' fields."""
    total = sum(len(dep.get("text", "").split()) for dep in inputs.values())
    return {"word_count": total}

TOOLS["word_count"] = word_count
```

Rules for a tool to stay inside the sandbox's guarantees:

- **No real I/O, network, or subprocess calls.** `fetch`'s fixture reads are
  confined to the `.sky` file's own directory (`_resolve_fixture_path` in
  `tools.py` rejects any `../` escape) — follow that pattern if your tool
  touches the filesystem at all. This repo's own rule (see `prd.md`'s Out of
  scope) is local JSON fixtures only, no external/paid APIs.
- **Anything you `eval` on user-controlled input must go through
  `safe_eval()`** (see below), never Python's builtin `eval`/`exec`. `filter_step`
  and `evaluate` are the two existing examples.
- **Keep it a pure function of its inputs.** The executor may run your tool
  on a worker thread under `run_sky_parallel` (see Parallel execution below),
  so don't rely on main-thread-only state (e.g. `signal`).
- Raise `tools.ToolError` for misconfiguration (missing required `args`,
  wrong number of deps) — that's the one exception type that legitimately
  aborts the whole run (`StepFailure` in `executor.py`), as opposed to a
  sandbox trip or timeout, which only blocks that one step.

Then write a `.sky` file that references `"tool": "word_count"` and run it
with `python3 run.py your_file.sky`.

## The sandbox: what's safe to `eval`

`safe_eval.py` is an AST-whitelist expression evaluator used by
`filter_step`'s `predicate` and `evaluate`'s `expr` args — i.e. wherever a
`.sky` file supplies an expression as a *string* that gets evaluated at run
time. It allows exactly: comparisons (`<`, `<=`, `>`, `>=`, `==`, `!=`),
boolean logic (`and`, `or`, `not`), arithmetic (`+ - * / % //`), literals,
and name lookups against an explicit `names` dict you pass in. It rejects
`Call`, `Attribute`, `Subscript`, `Lambda`, comprehensions, `Starred`, and
`Import` nodes **by node type**, not by blacklisting specific function names
— that's what stops the whole `os.system`/`open`/`eval`/`exec`/`globals()`/
`.__class__.__mro__` family: none of them are reachable without a `Call` or
`Attribute` node appearing *somewhere* in the parse tree, and the sandbox
recurses into every branch (`Compare` comparators, both sides of a `BinOp`,
every `BoolOp` value) looking for one.

This is a **language-level mitigation, not a formal security boundary** —
it runs in the same OS process as the caller with no seccomp/container/VM
isolation (see `prd.md`'s Out of scope). Measured results as of this build:
20/20 hand-written attack techniques blocked (`benchmark.py`), 154/154
auto-generated gadget variants across 14 seeds × 11 burial positions blocked
(`fuzz_corpus.py`), 0 false positives on 46 legitimate expressions across
both. If you add a new tool that calls `eval`/`exec`/`os.system` directly
instead of routing through `safe_eval`, you have personally reopened the
hole this whole project exists to close — don't do that.

## Parallel execution

Independent branches of the DAG (no dependency edge between them) can run
concurrently instead of one at a time:

```bash
python3 run.py --parallel your_file.sky
```

`dag.py`'s `topological_waves()` groups steps into waves where everything in
wave N is safe to run concurrently once waves `0..N-1` are done.
`executor.py`'s `run_sky_parallel()` fans each wave across a
`ThreadPoolExecutor` and enforces per-step timeouts via `Future.result(timeout=...)`
instead of `signal.alarm` (which only works on the main thread). The
sandbox's guarantees are unaffected — an `UnsafeExpressionError` raised
inside a worker thread propagates through `future.result()` and gets caught
identically to the sequential path. Measured speedup on the included
5-branch example (`examples/parallel_fanout.sky`, 60ms/branch): ~4.8x,
against a theoretical ceiling of 5x for one wave of 5 equal-delay branches —
see `parallel_bench.py`.

## Project layout

| File | Purpose |
|---|---|
| `dsl.py` | Parses/validates `.sky` JSON |
| `dag.py` | Topological order (`topological_order`) and wave grouping (`topological_waves`) |
| `safe_eval.py` | AST-whitelist expression sandbox |
| `tools.py` | The tool registry — add new tools here |
| `executor.py` | Runs the DAG (`run_sky` sequential, `run_sky_parallel` concurrent), timeouts, trace events |
| `run.py` | CLI entry point |
| `gen_trace.py` | Runs the clean/attack/parallel example recipes and writes `trace.jsonl` for the dashboard |
| `dashboard.html` | Self-contained (no CDN) animated DAG replay of `trace.jsonl` |
| `benchmark.py` | 20-technique attack corpus + false-positive + overhead report |
| `fuzz_corpus.py` | 154-variant auto-generated gadget-burial fuzz test |
| `parallel_bench.py` | Sequential-vs-parallel correctness + speedup check |
| `replay.py` | Text/ANSI terminal replay of the same trace, asciinema-ready, for viewers without a browser |
| `examples/` | `.sky` recipes: `report.sky` (happy path), `malicious.sky` (10 attacks), `attacks/*.sky` (20 single-technique files), `legit_*.sky` (false-positive controls), `parallel_fanout.sky` |
| `tests/` | `unittest` suite, one file per module above |

## Known limitations (honest, not swept under the rug)

- No headless browser is available in the build sandbox this project was
  developed in, so `dashboard.html`'s actual animation has been verified by
  re-running its layout/parsing JS functions against real trace data and
  confirming byte-identical serving over `http.server` — not by a human
  watching it render. Do a quick visual pass before using it in a demo.
- The AST whitelist is a mitigation against a known-leaky class of problem
  (pure-Python sandboxing), not a claim of formal soundness — see the Out of
  scope / Kill criteria sections of `prd.md`.
