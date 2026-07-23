import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fuzz_corpus import (
    build_report,
    generate_benign_corpus,
    generate_malicious_corpus,
    run_benign_fuzz,
    run_malicious_fuzz,
)


class TestFuzzedMaliciousCorpus(unittest.TestCase):
    def test_corpus_has_at_least_fifty_variants(self):
        self.assertGreaterEqual(len(generate_malicious_corpus()), 50)

    def test_all_variants_are_syntactically_valid_python(self):
        # A generator bug that emits broken syntax would trivially "block"
        # (SyntaxError -> UnsafeExpressionError) without proving anything.
        import ast
        for combo in generate_malicious_corpus():
            ast.parse(combo["expr"], mode="eval")  # raises if malformed

    def test_block_rate_at_least_ninety_five_percent(self):
        results = run_malicious_fuzz()
        blocked = sum(1 for r in results if r["blocked"])
        self.assertGreaterEqual(blocked / len(results), 0.95)

    def test_every_result_carries_a_technique_and_reason_when_blocked(self):
        for r in run_malicious_fuzz():
            self.assertTrue(r["technique"])
            if r["blocked"]:
                self.assertTrue(r["reason"])


class TestFuzzedBenignCorpus(unittest.TestCase):
    def test_benign_corpus_nonempty(self):
        self.assertGreater(len(generate_benign_corpus()), 0)

    def test_no_false_positives(self):
        results = run_benign_fuzz()
        false_positives = [r for r in results if r["false_positive"]]
        self.assertEqual(false_positives, [])


class TestFuzzReport(unittest.TestCase):
    def test_report_passes(self):
        report = build_report()
        self.assertTrue(report["pass"])
        self.assertEqual(report["benign_fuzz"]["false_positives"], 0)
        self.assertGreaterEqual(report["malicious_fuzz"]["block_rate"], 0.95)


if __name__ == "__main__":
    unittest.main()
