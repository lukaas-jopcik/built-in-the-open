"""End-to-end test: run crawl.py as a subprocess against a local fixture
server (not real internet, for determinism), twice in a row, and check the
whole fetch -> snapshot -> diff -> dashboard pipeline holds together.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FIXTURE_HTML = """<html><head><title>E2E Fixture</title></head>
<body><p>Some stable words that never change between runs</p>
<a href="/a">A</a><a href="/b">B</a></body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = FIXTURE_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class EndToEndTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _Handler)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=2)

    def _run_crawl(self, sites_path, out_path, data_dir):
        return subprocess.run(
            [
                sys.executable,
                os.path.join(REPO_ROOT, "crawl.py"),
                "--sites", sites_path,
                "--out", out_path,
                "--data-dir", data_dir,
                "--timeout", "5",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_two_consecutive_runs_exit_zero_and_report_no_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            sites_path = os.path.join(tmp, "sites.json")
            with open(sites_path, "w") as f:
                json.dump([f"http://127.0.0.1:{self.port}/"], f)
            out_path = os.path.join(tmp, "dashboard.html")
            data_dir = os.path.join(tmp, "runs")

            r1 = self._run_crawl(sites_path, out_path, data_dir)
            self.assertEqual(r1.returncode, 0, msg=r1.stdout + r1.stderr)
            self.assertIn("(no prior run)", r1.stdout)

            r2 = self._run_crawl(sites_path, out_path, data_dir)
            self.assertEqual(r2.returncode, 0, msg=r2.stdout + r2.stderr)

            self.assertTrue(os.path.exists(out_path))

            snap_files = sorted(f for f in os.listdir(data_dir) if f.endswith(".json"))
            self.assertEqual(len(snap_files), 2)
            timestamps = set()
            for fname in snap_files:
                with open(os.path.join(data_dir, fname)) as f:
                    timestamps.add(json.load(f)["timestamp"])
            self.assertEqual(len(timestamps), 2, "two runs must produce two distinct snapshot timestamps")

            with open(out_path) as f:
                dashboard_html = f.read()
            # Fixture content is identical across both runs, so the second run
            # should report a small "changes since last run" number, not
            # crash and not report the site as brand-new again.
            self.assertIn('data-metric="total_changes" data-value="0"', dashboard_html)
            self.assertIn("Changes since last run: 0", r2.stdout)

    def test_unreachable_site_is_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            sites_path = os.path.join(tmp, "sites.json")
            with open(sites_path, "w") as f:
                json.dump(
                    [f"http://127.0.0.1:{self.port}/", "http://127.0.0.1:1/unreachable"],
                    f,
                )
            out_path = os.path.join(tmp, "dashboard.html")
            data_dir = os.path.join(tmp, "runs")

            r = self._run_crawl(sites_path, out_path, data_dir)
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            self.assertIn("FAIL http://127.0.0.1:1/unreachable", r.stdout)
            self.assertIn("1/2 sites fetched successfully", r.stdout)
            self.assertTrue(os.path.exists(out_path))


if __name__ == "__main__":
    unittest.main()
