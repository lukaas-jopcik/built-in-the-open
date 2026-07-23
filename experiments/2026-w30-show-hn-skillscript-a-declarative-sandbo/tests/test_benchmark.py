import glob
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import ATTACKS_DIR, LEGIT_FILES, check_false_positives, measure_overhead, run_attack_corpus


class TestAttackCorpus(unittest.TestCase):
    def test_corpus_has_at_least_twenty_distinct_files(self):
        files = glob.glob(os.path.join(ATTACKS_DIR, "*.sky"))
        self.assertGreaterEqual(len(files), 20)

    def test_block_rate_at_least_ninety_percent(self):
        results = run_attack_corpus()
        blocked = sum(1 for r in results if r["blocked"])
        self.assertGreaterEqual(blocked / len(results), 0.90)

    def test_every_technique_result_has_a_technique_label(self):
        results = run_attack_corpus()
        for r in results:
            self.assertTrue(r["technique"])


class TestFalsePositives(unittest.TestCase):
    def test_five_legitimate_examples_checked(self):
        self.assertEqual(len(LEGIT_FILES), 5)

    def test_no_false_positives_on_legitimate_examples(self):
        results = check_false_positives()
        false_positives = [r for r in results if r["false_positive"]]
        self.assertEqual(false_positives, [])


class TestOverhead(unittest.TestCase):
    def test_overhead_report_has_numeric_percentage(self):
        report = measure_overhead(iterations=10)
        self.assertIsInstance(report["overhead_pct"], float)
        self.assertGreater(report["safe_eval_avg_us"], 0)
        self.assertGreater(report["raw_eval_avg_us"], 0)


if __name__ == "__main__":
    unittest.main()
