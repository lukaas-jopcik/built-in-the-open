import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dsl import load_sky
from executor import run_sky, StepTimeout, _run_with_timeout
from safe_eval import UnsafeExpressionError, safe_eval

EXAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")

ATTACK_EXPRESSIONS = [
    "__import__('os').system('id')",
    "open('/etc/passwd').read()",
    "__import__('socket').socket().connect(('127.0.0.1', 80))",
    "__import__('subprocess').run(['ls'])",
    "__import__('os')",
    "eval('1+1')",
    "exec('import os')",
    "globals()['__builtins__']",
    "().__class__.__mro__[1].__subclasses__()",
    "(lambda: __import__('os').system('id'))()",
]


class TestSafeEvalAccepts(unittest.TestCase):
    def test_comparison(self):
        self.assertTrue(safe_eval("value > 5", {"value": 10}))
        self.assertFalse(safe_eval("value > 5", {"value": 1}))

    def test_bool_and_arith(self):
        self.assertTrue(safe_eval("value > 5 and value < 20", {"value": 10}))
        self.assertEqual(safe_eval("a + b * 2", {"a": 1, "b": 3}), 7)

    def test_unary_not_and_neg(self):
        self.assertTrue(safe_eval("not flag", {"flag": False}))
        self.assertEqual(safe_eval("-value", {"value": 5}), -5)


class TestSafeEvalRejects(unittest.TestCase):
    def test_all_attack_expressions_blocked(self):
        for expr in ATTACK_EXPRESSIONS:
            with self.assertRaises(UnsafeExpressionError, msg=expr):
                safe_eval(expr, {})

    def test_unknown_name_rejected(self):
        with self.assertRaises(UnsafeExpressionError):
            safe_eval("__builtins__", {})

    def test_bad_syntax_rejected(self):
        with self.assertRaises(UnsafeExpressionError):
            safe_eval("def f(): pass", {})

    def test_comprehension_rejected(self):
        with self.assertRaises(UnsafeExpressionError):
            safe_eval("[x for x in range(10)]", {})


class TestExecutorSandbox(unittest.TestCase):
    def test_malicious_sky_blocks_all_ten(self):
        sky = load_sky(os.path.join(EXAMPLES_DIR, "malicious.sky"))
        results, final_step, order = run_sky(sky, log=lambda *_: None)
        self.assertEqual(final_step, "scoreboard")
        board = results["scoreboard"]
        self.assertEqual(board["status"], "blocked")
        self.assertEqual(board["total"], 10)
        self.assertEqual(board["blocked"], 10)
        self.assertEqual(board["escaped"], 0)

    def test_malicious_sky_does_not_crash_interpreter(self):
        sky = load_sky(os.path.join(EXAMPLES_DIR, "malicious.sky"))
        # If any attack escaped the sandbox this call itself would blow up
        # the test process (e.g. via os.system) instead of raising cleanly.
        run_sky(sky, log=lambda *_: None)

    def test_each_attack_step_records_blocked_sentinel_with_reason(self):
        sky = load_sky(os.path.join(EXAMPLES_DIR, "malicious.sky"))
        results, _, _ = run_sky(sky, log=lambda *_: None)
        for step in sky["steps"]:
            if step["id"] == "scoreboard":
                continue
            r = results[step["id"]]
            self.assertTrue(r.get("__blocked__"), step["id"])
            self.assertTrue(r.get("reason"), step["id"])

    def test_legit_report_sky_unaffected_by_sandbox_changes(self):
        sky = load_sky(os.path.join(EXAMPLES_DIR, "report.sky"))
        results, final_step, _ = run_sky(sky, log=lambda *_: None)
        self.assertEqual(results[final_step]["status"], "ok")


class TestTimeout(unittest.TestCase):
    def test_slow_tool_raises_step_timeout(self):
        def slow_tool(inputs, args, ctx):
            time.sleep(2)
            return {"ok": True}

        with self.assertRaises(StepTimeout):
            _run_with_timeout(slow_tool, {}, {}, {}, timeout_seconds=1)

    def test_fast_tool_completes_within_timeout(self):
        def fast_tool(inputs, args, ctx):
            return {"ok": True}

        result = _run_with_timeout(fast_tool, {}, {}, {}, timeout_seconds=1)
        self.assertEqual(result, {"ok": True})


if __name__ == "__main__":
    unittest.main()
