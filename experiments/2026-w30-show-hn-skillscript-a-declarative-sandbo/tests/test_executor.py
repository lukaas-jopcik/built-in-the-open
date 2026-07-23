import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dsl import load_sky
from executor import run_sky

EXAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")


class TestExecutor(unittest.TestCase):
    def test_report_sky_end_to_end(self):
        sky = load_sky(os.path.join(EXAMPLES_DIR, "report.sky"))
        results, final_step, order = run_sky(sky, log=lambda *_: None)
        self.assertEqual(final_step, "report")
        final = results[final_step]
        self.assertEqual(final["status"], "ok")
        self.assertEqual(final["total"], 29)
        self.assertEqual(final["count"], 5)
        names = [it["name"] for it in final["items"]]
        self.assertEqual(names, ["a1", "a2", "a3", "b1", "b3"])

    def test_filter_predicate_applied(self):
        sky = load_sky(os.path.join(EXAMPLES_DIR, "report.sky"))
        results, _, _ = run_sky(sky, log=lambda *_: None)
        self.assertEqual([it["value"] for it in results["filter"]["items"]], [10, 7])

    def test_trace_emits_paired_start_end_events_in_order(self):
        sky = load_sky(os.path.join(EXAMPLES_DIR, "report.sky"))
        trace = []
        results, final_step, order = run_sky(sky, log=lambda *_: None, trace=trace)
        # one start + one end per step, interleaved start/end/start/end...
        self.assertEqual(len(trace), 2 * len(order))
        for i, step_id in enumerate(order):
            start_ev, end_ev = trace[2 * i], trace[2 * i + 1]
            self.assertEqual(start_ev["event"], "start")
            self.assertEqual(start_ev["step_id"], step_id)
            self.assertEqual(end_ev["event"], "end")
            self.assertEqual(end_ev["step_id"], step_id)
            self.assertEqual(end_ev["status"], "ok")
            self.assertIsInstance(end_ev["elapsed_ms"], float)

    def test_trace_marks_blocked_steps_with_reason(self):
        sky = load_sky(os.path.join(EXAMPLES_DIR, "malicious.sky"))
        trace = []
        run_sky(sky, log=lambda *_: None, trace=trace)
        blocked_ends = [e for e in trace if e["event"] == "end" and e["step_id"].startswith("attack_")]
        self.assertEqual(len(blocked_ends), 10)
        for ev in blocked_ends:
            self.assertEqual(ev["status"], "blocked")
            self.assertTrue(ev["reason"])


if __name__ == "__main__":
    unittest.main()
