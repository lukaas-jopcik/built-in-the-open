import io
import os
import re
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import replay

ANSI_RE = re.compile(r"\033\[[0-9;]*m")


class TestReplay(unittest.TestCase):
    def _run_fast(self):
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            rc = replay.main(["replay.py", "--fast"])
        finally:
            sys.stdout = old_stdout
        return rc, buf.getvalue()

    def test_fast_mode_is_actually_fast(self):
        start = time.time()
        rc, _ = self._run_fast()
        elapsed = time.time() - start
        self.assertEqual(rc, 0)
        # unpaced run should take a fraction of a second, not the ~25s the
        # full STEP_DELAY/END_DELAY/RUN_GAP pacing would otherwise cost.
        self.assertLess(elapsed, 3.0)

    def test_contains_all_three_runs_in_order(self):
        _, text = self._run_fast()
        plain = ANSI_RE.sub("", text)
        clean_pos = plain.index("CLEAN RUN")
        attack_pos = plain.index("ATTACK RUN")
        parallel_pos = plain.index("PARALLEL FAN-OUT")
        self.assertLess(clean_pos, attack_pos)
        self.assertLess(attack_pos, parallel_pos)

    def test_attack_scoreboard_matches_known_corpus_size(self):
        _, text = self._run_fast()
        plain = ANSI_RE.sub("", text)
        self.assertIn("10/10 attack vectors blocked, 0 escapes", plain)

    def test_parallel_speedup_line_is_a_real_number_greater_than_one(self):
        _, text = self._run_fast()
        plain = ANSI_RE.sub("", text)
        m = re.search(r"([\d.]+)x real speedup -- measured, not simulated", plain)
        self.assertIsNotNone(m)
        self.assertGreater(float(m.group(1)), 1.0)

    def test_clean_report_line_matches_expected_report(self):
        _, text = self._run_fast()
        plain = ANSI_RE.sub("", text)
        self.assertIn("[REPORT] status=ok total=29 count=5", plain)

    def test_every_start_has_a_matching_end(self):
        _, text = self._run_fast()
        plain = ANSI_RE.sub("", text)
        starts = plain.count("→ ")
        oks = plain.count("✓ ")
        blocked = plain.count("✕ ")
        self.assertEqual(starts, oks + blocked)

    def test_env_var_also_triggers_fast_mode(self):
        os.environ["SKILLCAGE_REPLAY_FAST"] = "1"
        try:
            buf = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = buf
            start = time.time()
            try:
                rc = replay.main(["replay.py"])
            finally:
                sys.stdout = old_stdout
            elapsed = time.time() - start
        finally:
            del os.environ["SKILLCAGE_REPLAY_FAST"]
        self.assertEqual(rc, 0)
        self.assertLess(elapsed, 3.0)


if __name__ == "__main__":
    unittest.main()
