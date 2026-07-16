"""Core primitives for SwarmDeck: Task, Router, RetryPolicy, SimWorker, Observer.

Stdlib only. No network, no third-party deps.
"""
import json
import queue
import random
import threading
import time
from dataclasses import dataclass


@dataclass
class Task:
    id: int
    payload: str = ""


class RetryPolicy:
    """Exponential backoff with a max attempt cap."""

    def __init__(self, max_attempts=3, base_delay_ms=50, backoff_factor=2.0):
        self.max_attempts = max_attempts
        self.base_delay_ms = base_delay_ms
        self.backoff_factor = backoff_factor

    def delay_ms(self, attempt):
        """attempt is 1-indexed; delay before retrying after this failed attempt."""
        return self.base_delay_ms * (self.backoff_factor ** (attempt - 1))

    def should_retry(self, attempt):
        return attempt < self.max_attempts


class Router:
    """Round-robin router across N simulated worker ids."""

    def __init__(self, worker_ids):
        self.worker_ids = list(worker_ids)
        self._i = 0

    def next_worker(self):
        wid = self.worker_ids[self._i % len(self.worker_ids)]
        self._i += 1
        return wid


class SimWorker:
    """A simulated worker with a seeded failure rate and latency jitter."""

    def __init__(self, worker_id, failure_rate=0.3, latency_ms_range=(10, 60), rng=None):
        self.worker_id = worker_id
        self.failure_rate = failure_rate
        self.latency_ms_range = latency_ms_range
        self.rng = rng or random.Random()

    def run(self, task):
        """Simulate executing a task. Returns (success: bool, latency_ms: float)."""
        latency_ms = self.rng.uniform(*self.latency_ms_range)
        time.sleep(latency_ms / 1000.0)
        success = self.rng.random() >= self.failure_rate
        return success, latency_ms


class Observer:
    """Logs every task state transition as a JSONL line."""

    STATES = ("queued", "running", "failed", "retrying", "done")

    def __init__(self, path="events.jsonl", mode="a"):
        self.path = path
        self._fh = open(path, mode)
        self._lock = threading.Lock()

    def log(self, task_id, state, attempt, worker_id, latency_ms, run_mode):
        event = {
            "ts": time.time(),
            "task_id": task_id,
            "state": state,
            "attempt": attempt,
            "worker_id": worker_id,
            "latency_ms": round(latency_ms, 3),
            "mode": run_mode,
        }
        line = json.dumps(event) + "\n"
        with self._lock:
            self._fh.write(line)
            self._fh.flush()
        return event

    def close(self):
        self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


def run_task_sequential(task, workers, router, retry_policy, observer, run_mode):
    """Run a single task to completion (success or exhausted retries), sequentially.

    run_mode: "control" uses router + retries; "naive" always uses worker 0,
    no retries (single attempt only), no recovery.
    Returns final state: "done" or "failed".
    """
    observer.log(task.id, "queued", 0, None, 0.0, run_mode)

    attempt = 0
    while True:
        attempt += 1
        if run_mode == "control":
            worker_id = router.next_worker()
        else:
            worker_id = workers[0].worker_id
        worker = workers[worker_id]

        observer.log(task.id, "running", attempt, worker_id, 0.0, run_mode)
        success, latency_ms = worker.run(task)

        if success:
            observer.log(task.id, "done", attempt, worker_id, latency_ms, run_mode)
            return "done"

        observer.log(task.id, "failed", attempt, worker_id, latency_ms, run_mode)

        if run_mode == "naive" or not retry_policy.should_retry(attempt):
            return "failed"

        observer.log(task.id, "retrying", attempt, worker_id, latency_ms, run_mode)


def run_batch_concurrent(tasks, workers, router, retry_policy, observer, run_mode, n_workers):
    """Run a batch of tasks through a real thread pool (stdlib threading + queue).

    naive mode: a single thread pinned to worker 0; one attempt per task,
    no requeue on failure (no recovery, no routing) -- mirrors run_task_sequential's
    naive path but as a real (if degenerate) worker pool.
    control mode: n_workers threads pull from one shared queue; a failed task
    is requeued (any free worker may pick up the retry) until retry_policy
    exhausts attempts. This is genuine cross-worker routing driven by whichever
    worker becomes free first, not a fixed round-robin schedule.

    Returns {task_id: "done"|"failed"}.
    """
    results = {}
    results_lock = threading.Lock()
    attempts = {}
    attempts_lock = threading.Lock()

    task_queue = queue.Queue()
    for t in tasks:
        observer.log(t.id, "queued", 0, None, 0.0, run_mode)
        attempts[t.id] = 0
        task_queue.put(t)

    active_ids = list(workers.keys())[:n_workers] if run_mode == "control" else [0]
    STOP = object()

    def worker_loop(wid):
        worker = workers[wid]
        while True:
            item = task_queue.get()
            if item is STOP:
                task_queue.task_done()
                return

            task = item
            with attempts_lock:
                attempts[task.id] += 1
                attempt = attempts[task.id]

            observer.log(task.id, "running", attempt, wid, 0.0, run_mode)
            success, latency_ms = worker.run(task)

            if success:
                observer.log(task.id, "done", attempt, wid, latency_ms, run_mode)
                with results_lock:
                    results[task.id] = "done"
            else:
                observer.log(task.id, "failed", attempt, wid, latency_ms, run_mode)
                if run_mode == "control" and retry_policy.should_retry(attempt):
                    observer.log(task.id, "retrying", attempt, wid, latency_ms, run_mode)
                    task_queue.put(task)
                else:
                    with results_lock:
                        results[task.id] = "failed"
            task_queue.task_done()

    threads = [threading.Thread(target=worker_loop, args=(wid,)) for wid in active_ids]
    for th in threads:
        th.start()

    task_queue.join()
    for _ in threads:
        task_queue.put(STOP)
    for th in threads:
        th.join()

    return results


def build_workers(n_workers, failure_rate, latency_ms_range, rng):
    return {
        wid: SimWorker(wid, failure_rate=failure_rate, latency_ms_range=latency_ms_range, rng=rng)
        for wid in range(n_workers)
    }
