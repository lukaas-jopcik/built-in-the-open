"""Runs a parsed .sky graph in topological order against the tool registry.

Every step runs under two guards: the AST-whitelist sandbox (safe_eval,
tripped by tools like `evaluate`/`filter_step` on unsafe expressions) and a
wall-clock timeout (SIGALRM). Either guard tripping marks that step BLOCKED
instead of raising -- so one caged attack step doesn't take down the rest of
an independent DAG. Only a genuine tool misconfiguration (ToolError, e.g.
unknown tool/missing arg) aborts the whole run.
"""
import concurrent.futures
import signal
import time

from dag import topological_order, topological_waves
from safe_eval import UnsafeExpressionError
from tools import TOOLS, ToolError

DEFAULT_TIMEOUT_SECONDS = 2


class StepFailure(RuntimeError):
    def __init__(self, step_id, reason):
        super().__init__(f"step '{step_id}' failed: {reason}")
        self.step_id = step_id
        self.reason = reason


class StepTimeout(RuntimeError):
    pass


def _run_with_timeout(tool, dep_inputs, args, ctx, timeout_seconds):
    def _handler(signum, frame):
        raise StepTimeout(f"exceeded {timeout_seconds}s wall-clock limit")

    old_handler = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(timeout_seconds)
    try:
        return tool(dep_inputs, args, ctx)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def run_sky(sky, log=print, trace=None):
    """Execute all steps. Returns (results_dict, final_step_id, order).

    Blocked steps land in `results[id]` as {"__blocked__": True, "reason": ...}
    rather than raising, so downstream/independent steps keep executing.

    If `trace` is a list, a {"event": "start"|"end", ...} dict is appended per
    step -- this is the JSONL feed the dashboard animates from (see
    gen_trace.py)."""
    order = topological_order(sky["steps"])
    steps_by_id = {s["id"]: s for s in sky["steps"]}
    ctx = {"base_dir": sky["_base_dir"]}

    results = {}
    for step_id in order:
        step = steps_by_id[step_id]
        tool_name = step["tool"]
        deps = step["deps"]
        tool = TOOLS.get(tool_name)
        if tool is None:
            raise StepFailure(step_id, f"unknown tool '{tool_name}'")
        dep_inputs = {d: results[d] for d in deps}
        timeout_seconds = step.get("timeout", DEFAULT_TIMEOUT_SECONDS)

        if trace is not None:
            trace.append({"event": "start", "step_id": step_id, "tool": tool_name, "deps": deps})

        start = time.time()
        try:
            result = _run_with_timeout(tool, dep_inputs, step.get("args", {}), ctx, timeout_seconds)
        except UnsafeExpressionError as e:
            elapsed_ms = (time.time() - start) * 1000
            results[step_id] = {"__blocked__": True, "reason": str(e)}
            log(f"[STEP] {step_id:<24} tool={tool_name:<14} status=BLOCKED reason={e} time={elapsed_ms:.3f}ms")
            if trace is not None:
                trace.append({"event": "end", "step_id": step_id, "tool": tool_name, "deps": deps,
                               "status": "blocked", "reason": str(e), "elapsed_ms": elapsed_ms})
            continue
        except StepTimeout as e:
            elapsed_ms = (time.time() - start) * 1000
            results[step_id] = {"__blocked__": True, "reason": str(e)}
            log(f"[STEP] {step_id:<24} tool={tool_name:<14} status=TIMEOUT  reason={e} time={elapsed_ms:.3f}ms")
            if trace is not None:
                trace.append({"event": "end", "step_id": step_id, "tool": tool_name, "deps": deps,
                               "status": "timeout", "reason": str(e), "elapsed_ms": elapsed_ms})
            continue
        except ToolError as e:
            raise StepFailure(step_id, str(e)) from e
        elapsed_ms = (time.time() - start) * 1000
        results[step_id] = result
        log(f"[STEP] {step_id:<24} tool={tool_name:<14} status=ok      time={elapsed_ms:.3f}ms")
        if trace is not None:
            trace.append({"event": "end", "step_id": step_id, "tool": tool_name, "deps": deps,
                           "status": "ok", "reason": None, "elapsed_ms": elapsed_ms})

    final_step = sky.get("final") or order[-1]
    return results, final_step, order


def run_sky_parallel(sky, log=print, trace=None, max_workers=8):
    """Same contract as run_sky (returns (results, final_step, order), same
    __blocked__ sentinel convention, same trace event shapes) but fans each
    "wave" of the DAG (steps whose deps are all already satisfied and which
    don't depend on each other -- see dag.topological_waves) out across a
    thread pool instead of running steps one at a time. This is what proves
    the executor does *real* concurrent execution, not just a DAG that could
    be run in parallel: independent slow_step branches genuinely overlap on
    the wall clock (see parallel_bench.py).

    signal.alarm only works on the main thread, so per-step timeouts here are
    enforced via Future.result(timeout=...) instead of SIGALRM -- a thread
    that overruns its timeout is abandoned (not killed; Python has no safe way
    to kill a thread) rather than aborting the wave, matching run_sky's
    "one caged/timed-out step doesn't take down the rest of the DAG" contract.
    """
    waves = topological_waves(sky["steps"])
    steps_by_id = {s["id"]: s for s in sky["steps"]}
    ctx = {"base_dir": sky["_base_dir"]}
    order = [step_id for wave in waves for step_id in wave]

    results = {}
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
    try:
        for wave_index, wave in enumerate(waves):
            wave_start = time.time()
            futures = {}
            for step_id in wave:
                step = steps_by_id[step_id]
                tool_name = step["tool"]
                tool = TOOLS.get(tool_name)
                if tool is None:
                    raise StepFailure(step_id, f"unknown tool '{tool_name}'")
                dep_inputs = {d: results[d] for d in step["deps"]}
                if trace is not None:
                    trace.append({"event": "start", "step_id": step_id, "tool": tool_name,
                                   "deps": step["deps"], "wave": wave_index})
                futures[step_id] = (
                    pool.submit(tool, dep_inputs, step.get("args", {}), ctx),
                    time.time(),
                )

            for step_id in wave:
                step = steps_by_id[step_id]
                tool_name = step["tool"]
                timeout_seconds = step.get("timeout", DEFAULT_TIMEOUT_SECONDS)
                future, start = futures[step_id]
                try:
                    result = future.result(timeout=timeout_seconds)
                except UnsafeExpressionError as e:
                    elapsed_ms = (time.time() - start) * 1000
                    results[step_id] = {"__blocked__": True, "reason": str(e)}
                    log(f"[STEP] {step_id:<24} tool={tool_name:<14} status=BLOCKED reason={e} "
                        f"time={elapsed_ms:.3f}ms wave={wave_index}")
                    if trace is not None:
                        trace.append({"event": "end", "step_id": step_id, "tool": tool_name,
                                       "deps": step["deps"], "status": "blocked", "reason": str(e),
                                       "elapsed_ms": elapsed_ms, "wave": wave_index})
                    continue
                except concurrent.futures.TimeoutError:
                    reason = f"exceeded {timeout_seconds}s wall-clock limit"
                    elapsed_ms = (time.time() - start) * 1000
                    results[step_id] = {"__blocked__": True, "reason": reason}
                    log(f"[STEP] {step_id:<24} tool={tool_name:<14} status=TIMEOUT  reason={reason} "
                        f"time={elapsed_ms:.3f}ms wave={wave_index}")
                    if trace is not None:
                        trace.append({"event": "end", "step_id": step_id, "tool": tool_name,
                                       "deps": step["deps"], "status": "timeout", "reason": reason,
                                       "elapsed_ms": elapsed_ms, "wave": wave_index})
                    continue
                except ToolError as e:
                    raise StepFailure(step_id, str(e)) from e
                elapsed_ms = (time.time() - start) * 1000
                results[step_id] = result
                log(f"[STEP] {step_id:<24} tool={tool_name:<14} status=ok      "
                    f"time={elapsed_ms:.3f}ms wave={wave_index}")
                if trace is not None:
                    trace.append({"event": "end", "step_id": step_id, "tool": tool_name,
                                   "deps": step["deps"], "status": "ok", "reason": None,
                                   "elapsed_ms": elapsed_ms, "wave": wave_index})

            wave_elapsed_ms = (time.time() - wave_start) * 1000
            log(f"[WAVE]  {wave_index} -- {len(wave)} step(s) concurrently, wall={wave_elapsed_ms:.3f}ms")
            if trace is not None:
                trace.append({"event": "wave_done", "wave": wave_index, "size": len(wave),
                               "elapsed_ms": wave_elapsed_ms})
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    final_step = sky.get("final") or order[-1]
    return results, final_step, order
