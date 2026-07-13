"""Automated, no-network test for the agent loop (run_once / rule_based_policy).

Mirrors test_browser.py's approach: a tiny stdlib http.server fixture site
stands in for Wikipedia so the agent's search -> follow-result-link ->
extract-fact loop is proven mechanically, without depending on a live site
being reachable or its markup staying stable.
"""
import json
import os
import tempfile
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

from barebrowse import agent as agent_mod
from barebrowse.agent import _parse_llm_action, main, rule_based_policy, run_once

HOME_PAGE = """
    <html><head><title>Fixture Search Engine</title></head>
    <body>
        <form action="/search" method="GET">
            <input type="text" name="q" placeholder="search">
            <button type="submit">Go</button>
        </form>
    </body></html>
"""

RESULTS_TEMPLATE = """
    <html><head><title>Results for {q}</title></head>
    <body>
        <ul>
            <li><a href="/page/decoy">Decoy Page</a></li>
            <li><a href="/page/target">The Target Page you want</a></li>
        </ul>
    </body></html>
"""

TARGET_PAGE = """
    <html><head><title>The Target Page - Fixture</title></head>
    <body><p>Fact: 4242</p></body></html>
"""

DECOY_PAGE = """
    <html><head><title>Decoy - Fixture</title></head>
    <body><p>Fact: 0</p></body></html>
"""


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            body = HOME_PAGE
        elif parsed.path == "/search":
            qs = urllib.parse.parse_qs(parsed.query)
            body = RESULTS_TEMPLATE.format(q=qs.get("q", [""])[0])
        elif parsed.path == "/page/target":
            body = TARGET_PAGE
        elif parsed.path == "/page/decoy":
            body = DECOY_PAGE
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))


class AgentLoopTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)

    def base(self, path=""):
        return f"http://127.0.0.1:{self.port}{path}"

    def make_task(self):
        return {
            "description": "fixture task",
            "start_url": self.base("/"),
            "query": "anything",
            "target_substring": "Target Page",
            "extract_regex": r"Fact:\s*(\d+)",
            "max_steps": 6,
        }

    def test_rule_based_policy_completes_task(self):
        result = run_once(self.make_task(), rule_based_policy, "rule")
        self.assertTrue(result["success"], result)
        self.assertEqual(result["extracted"], "4242")
        self.assertEqual(result["final_url"], self.base("/page/target"))
        # type -> click(submit) -> click(target link) -> done == 4 steps
        self.assertEqual(len(result["steps"]), 4)
        self.assertEqual(result["steps"][0]["action"]["type"], "type")
        self.assertEqual(result["steps"][-1]["action"]["type"], "done")

    def test_rule_based_policy_reports_failure_when_target_missing(self):
        task = self.make_task()
        task["target_substring"] = "Something Not On The Page"
        result = run_once(task, rule_based_policy, "rule")
        self.assertFalse(result["success"])
        self.assertIsNotNone(result["error"])

    def test_main_writes_run_log_and_computes_success_rate(self):
        with tempfile.TemporaryDirectory() as d:
            task_path = os.path.join(d, "task.json")
            out_path = os.path.join(d, "run_log.jsonl")
            with open(task_path, "w") as f:
                json.dump(self.make_task(), f)

            old_cwd = os.getcwd()
            os.chdir(d)
            try:
                rc = main(["--task", task_path, "--runs", "3", "--out", out_path, "--policy", "rule"])
            finally:
                os.chdir(old_cwd)

            self.assertEqual(rc, 0)
            with open(out_path) as f:
                lines = [json.loads(line) for line in f if line.strip()]
            self.assertEqual(len(lines), 3)
            self.assertTrue(all(r["success"] for r in lines))

    def test_ollama_unavailable_falls_back_to_rule_policy(self):
        original = agent_mod.is_ollama_available
        agent_mod.is_ollama_available = lambda *a, **k: False
        try:
            name, _ = agent_mod.choose_policy("auto", "llama3.2")
        finally:
            agent_mod.is_ollama_available = original
        self.assertEqual(name, "rule")


class ParseLlmActionTest(unittest.TestCase):
    def test_parses_type_action(self):
        action = _parse_llm_action("I will search.\nACTION: type e19 Guido van Rossum\n")
        self.assertEqual(action, {"type": "type", "ref": "e19", "text": "Guido van Rossum"})

    def test_parses_click_action(self):
        action = _parse_llm_action("ACTION: click e54")
        self.assertEqual(action, {"type": "click", "ref": "e54"})

    def test_parses_done_action(self):
        action = _parse_llm_action("ACTION: done 1956-01-31")
        self.assertEqual(action, {"type": "done", "success": True, "extracted": "1956-01-31"})

    def test_garbage_returns_none(self):
        self.assertIsNone(_parse_llm_action("I don't know what to do here."))


if __name__ == "__main__":
    unittest.main()
