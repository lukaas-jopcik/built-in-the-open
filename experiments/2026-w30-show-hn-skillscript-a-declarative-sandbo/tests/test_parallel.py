import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dsl import load_sky
from executor import run_sky, run_sky_parallel

EXAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")


class TestRunSkyParallel(unittest.TestCase):
    def test_matches_sequential_result_on_report_sky(self):
        sky = load_sky(os.path.join(EXAMPLES_DIR, "report.sky"))
        seq_results, seq_final, seq_order = run_sky(sky, log=lambda *_: None)
        sky2 = load_sky(os.path.join(EXAMPLES_DIR, "report.sky"))
        par_results, par_final, par_order = run_sky_parallel(sky2, log=lambda *_: None)
        self.assertEqual(seq_final, par_final)
        self.assertEqual(seq_results[seq_final], par_results[par_final])
        # order can legitimately differ in tie-break, but must be a valid
        # topological order containing the same set of steps
        self.assertEqual(set(seq_order), set(par_order))

    def test_still_blocks_all_attacks_when_run_in_threads(self):
        sky = load_sky(os.path.join(EXAMPLES_DIR, "malicious.sky"))
        results, final_step, order = run_sky_parallel(sky, log=lambda *_: None)
        scoreboard = results[final_step]
        self.assertEqual(scoreboard["blocked"], scoreboard["total"])
        self.assertEqual(scoreboard["escaped"], 0)
        attack_ids = [s for s in order if s.startswith("attack_")]
        self.assertEqual(len(attack_ids), 10)
        for step_id in attack_ids:
            self.assertTrue(results[step_id]["__blocked__"])
            self.assertTrue(results[step_id]["reason"])

    def test_trace_events_carry_wave_field(self):
        sky = load_sky(os.path.join(EXAMPLES_DIR, "parallel_fanout.sky"))
        trace = []
        run_sky_parallel(sky, log=lambda *_: None, trace=trace)
        starts = [e for e in trace if e["event"] == "start"]
        self.assertTrue(all("wave" in e for e in starts))
        wave0 = [e["step_id"] for e in starts if e["wave"] == 0]
        self.assertEqual(set(wave0), {"branch_a", "branch_b", "branch_c", "branch_d", "branch_e"})
        wave_done = [e for e in trace if e["event"] == "wave_done"]
        self.assertGreaterEqual(len(wave_done), 3)  # branches, aggregate, report

    def test_independent_branches_genuinely_overlap_on_wall_clock(self):
        """The 5 slow_step branches in parallel_fanout.sky each sleep ~60ms.
        Run one at a time that's >= 300ms; fanned out across threads in one
        DAG wave it should land well under that -- this is what proves the
        executor does real concurrency, not just a DAG shape that could
        support it."""
        import time

        sky_seq = load_sky(os.path.join(EXAMPLES_DIR, "parallel_fanout.sky"))
        start = time.perf_counter()
        run_sky(sky_seq, log=lambda *_: None)
        seq_elapsed = time.perf_counter() - start

        sky_par = load_sky(os.path.join(EXAMPLES_DIR, "parallel_fanout.sky"))
        start = time.perf_counter()
        run_sky_parallel(sky_par, log=lambda *_: None)
        par_elapsed = time.perf_counter() - start

        self.assertLess(par_elapsed, seq_elapsed * 0.6)


if __name__ == "__main__":
    unittest.main()
