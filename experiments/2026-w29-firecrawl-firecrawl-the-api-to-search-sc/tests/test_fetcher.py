import gzip
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from lib import fetcher

FIXTURE_HTML = """<html><head><title> Test Page </title></head>
<body>
<p>Hello world this is a test page with some words</p>
<a href="/a">A</a><a href="/b">B</a>
<img src="/img1.png">
<script>var shouldNotCountAsWords = 1;</script>
</body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = FIXTURE_HTML.encode("utf-8")
        headers = {"Content-Type": "text/html; charset=utf-8"}
        if self.path == "/gzip":
            body = gzip.compress(body)
            headers["Content-Encoding"] = "gzip"
        self.send_response(200)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class FetcherTest(unittest.TestCase):
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

    def test_fetch_extracts_expected_metrics(self):
        r = fetcher.fetch(f"http://127.0.0.1:{self.port}/")
        self.assertEqual(r["status"], 200)
        self.assertEqual(r["title"], "Test Page")
        self.assertEqual(r["link_count"], 2)
        self.assertEqual(r["image_count"], 1)
        self.assertEqual(sorted(r["links"]), ["/a", "/b"])
        # Script contents must not leak into word count.
        self.assertNotIn("shouldNotCountAsWords", r.get("links", []))
        self.assertGreaterEqual(r["word_count"], 9)
        self.assertLess(r["word_count"], 20)  # script text must not have been counted

    def test_fetch_transparently_decodes_gzip(self):
        # Some CDNs (e.g. python.org) send gzip bodies unconditionally; regression
        # test for the bug found while running crawl.py against real sites.
        r = fetcher.fetch(f"http://127.0.0.1:{self.port}/gzip")
        self.assertEqual(r["title"], "Test Page")
        self.assertEqual(r["link_count"], 2)


if __name__ == "__main__":
    unittest.main()
