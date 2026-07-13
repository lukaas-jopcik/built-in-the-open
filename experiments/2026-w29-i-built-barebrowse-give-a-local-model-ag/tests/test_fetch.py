"""Automated, no-external-network test for barebrowse/fetch.py.

Covers the gzip-decompression regression found while running bench.py against
real sites: several real CDNs (python.org via Fastly/Varnish) send
Content-Encoding: gzip even though barebrowse never sends an Accept-Encoding
request header. Without decompressing, fetch() silently returned compressed
bytes decoded as "text" -- html.parser then saw binary garbage and produced
an empty (but not crashing) snapshot, which is worse than a loud failure.
"""
import gzip
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from barebrowse.fetch import FetchError, fetch

PLAIN_BODY = "<html><head><title>Plain</title></head><body><p>hello plain</p></body></html>"
GZIP_BODY = "<html><head><title>Gzipped</title></head><body><p>hello gzip</p></body></html>"
LATIN1_BODY = "<html><head><title>Café</title></head><body><p>Café résumé naïve</p></body></html>"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path == "/plain.html":
            body = PLAIN_BODY.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/gzip.html":
            body = gzip.compress(GZIP_BODY.encode("utf-8"))
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Encoding", "gzip")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/latin1.html":
            body = LATIN1_BODY.encode("latin-1")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=iso-8859-1")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/redirect.html":
            self.send_response(302)
            self.send_header("Location", "/plain.html")
            self.end_headers()
        elif self.path == "/slow.html":
            time.sleep(2)
            body = PLAIN_BODY.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()


class FetchGzipTest(unittest.TestCase):
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

    def test_plain_response_unaffected(self):
        final_url, text = fetch(self.base("/plain.html"), timeout=5)
        self.assertIn("hello plain", text)

    def test_gzip_response_is_decompressed(self):
        final_url, text = fetch(self.base("/gzip.html"), timeout=5)
        self.assertIn("hello gzip", text)
        self.assertIn("<title>Gzipped</title>", text)

    def test_non_utf8_encoding_decoded_via_charset_header(self):
        final_url, text = fetch(self.base("/latin1.html"), timeout=5)
        self.assertIn("Café", text)
        self.assertIn("résumé", text)

    def test_redirect_is_followed_and_final_url_updated(self):
        final_url, text = fetch(self.base("/redirect.html"), timeout=5)
        self.assertTrue(final_url.endswith("/plain.html"))
        self.assertIn("hello plain", text)

    def test_timeout_raises_fetch_error_not_a_crash(self):
        with self.assertRaises(FetchError):
            fetch(self.base("/slow.html"), timeout=0.5)


if __name__ == "__main__":
    unittest.main()
