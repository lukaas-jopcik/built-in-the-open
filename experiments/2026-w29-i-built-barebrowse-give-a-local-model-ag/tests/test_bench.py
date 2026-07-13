"""Automated, no-external-network test for barebrowse/bench.py.

Serves a local fixture page bloated with scripts/styles/wrapper divs (so a
real reduction is measurable) plus one unreachable URL, and asserts:
  - reachable pages get a real raw>snapshot token count and reduction_pct
  - an unreachable page is skipped (logged), not fatal
  - run_benchmark's aggregate mean_reduction_pct matches its own per-page math
"""
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from barebrowse.bench import bench_page, run_benchmark

BLOATED_PAGE = """
<html><head><title>Bloated</title>
<style>body { color: red; } .wrapper { padding: 4px; }</style>
<script>console.log("tracking pixel nonsense here padding out the raw HTML");</script>
</head>
<body>
<div class="wrapper"><div class="inner"><div class="deeper">
  <h1>Real heading</h1>
  <p>Some real paragraph text a user would actually read.</p>
  <nav><a href="/other.html">A real link</a></nav>
</div></div></div>
<script>var x = 1; function noop() { return x; }</script>
</body></html>
"""


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path == "/bloated.html":
            body = BLOATED_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()


class BenchTest(unittest.TestCase):
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

    def base(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def test_bench_page_reports_real_reduction(self):
        result = bench_page(self.base("/bloated.html"), timeout=5)
        self.assertIsNotNone(result)
        self.assertGreater(result["raw_tokens"], result["snapshot_tokens"])
        self.assertGreater(result["reduction_pct"], 0)
        # the script/style noise must not survive into the snapshot token count
        self.assertLess(result["snapshot_tokens"], 40)

    def test_bench_page_skips_unreachable_url_without_raising(self):
        # nothing is listening on this closed port -> connection refused
        result = bench_page("http://127.0.0.1:1/nope.html", timeout=2)
        self.assertIsNone(result)

    def test_bench_page_skips_404(self):
        result = bench_page(self.base("/missing.html"), timeout=5)
        self.assertIsNone(result)

    def test_run_benchmark_mixes_success_and_skip(self):
        urls = [
            self.base("/bloated.html"),
            "http://127.0.0.1:1/nope.html",
            self.base("/bloated.html"),
        ]
        results = run_benchmark(urls, timeout=5)
        self.assertEqual(results["num_requested"], 3)
        self.assertEqual(results["num_pages"], 2)
        self.assertEqual(len(results["pages"]), 2)
        expected_mean = sum(p["reduction_pct"] for p in results["pages"]) / 2
        self.assertAlmostEqual(results["mean_reduction_pct"], expected_mean)
        self.assertGreater(results["total_raw_tokens"], results["total_snapshot_tokens"])


if __name__ == "__main__":
    unittest.main()
