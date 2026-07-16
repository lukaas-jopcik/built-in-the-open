"""Slice 2 demo CLI: runs a batch of tasks through a real thread pool
(stdlib threading), comparing naive mode (single worker thread, no retries,
no routing) against control-plane mode (N worker threads, failed tasks
requeued and retried per RetryPolicy) on the identical seeded failure model.

Writes every state transition to events.jsonl and prints a summary table
with wall-clock elapsed time per mode.
"""
import argparse
import random
import time

from swarmdeck.core import (
    Observer,
    RetryPolicy,
    Router,
    Task,
    build_workers,
    run_batch_concurrent,
)


def run_batch(n_tasks, failure_rate, seed, n_workers, max_attempts, observer, run_mode):
    rng = random.Random(seed)
    workers = build_workers(n_workers, failure_rate, (10, 60), rng)
    router = Router(list(workers.keys()))
    retry_policy = RetryPolicy(max_attempts=max_attempts)
    tasks = [Task(id=i) for i in range(n_tasks)]

    start = time.time()
    results = run_batch_concurrent(
        tasks, workers, router, retry_policy, observer, run_mode, n_workers
    )
    elapsed = time.time() - start
    return results, elapsed


def main():
    parser = argparse.ArgumentParser(description="SwarmDeck slice-2 concurrent demo")
    parser.add_argument("--tasks", type=int, default=50)
    parser.add_argument("--failure-rate", type=float, default=0.3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--out", type=str, default="events.jsonl")
    args = parser.parse_args()

    # truncate the log file at the start of a fresh CLI run
    open(args.out, "w").close()

    with Observer(args.out, mode="a") as observer:
        naive_results, naive_elapsed = run_batch(
            args.tasks, args.failure_rate, args.seed, args.workers, args.max_attempts,
            observer, "naive",
        )
        control_results, control_elapsed = run_batch(
            args.tasks, args.failure_rate, args.seed, args.workers, args.max_attempts,
            observer, "control",
        )

    naive_success = sum(1 for v in naive_results.values() if v == "done")
    control_success = sum(1 for v in control_results.values() if v == "done")
    n = args.tasks

    print(f"{'mode':<10}{'success':<10}{'total':<10}{'success_rate':<14}{'elapsed_s':<10}")
    print(f"{'naive':<10}{naive_success:<10}{n:<10}{naive_success / n:<14.2%}{naive_elapsed:<10.2f}")
    print(f"{'control':<10}{control_success:<10}{n:<10}{control_success / n:<14.2%}{control_elapsed:<10.2f}")
    print(f"\nevents written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
