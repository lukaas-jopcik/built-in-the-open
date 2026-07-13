"""Automated, no-network test for Browser.goto/click/type/submit.

Spins up a tiny stdlib http.server on localhost serving a fixed 3-page
fixture site (link -> form -> submit -> result page), then drives it
purely by refs pulled out of the snapshot text, exactly like a real agent
would. No external network, no manual watching, exits 0/1.
"""
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

from barebrowse.browser import Browser, BrowserError

PAGES = {
    "/index.html": """
        <html><head><title>Home</title></head>
        <body>
            <h1>Fixture Home</h1>
            <nav><a href="/search.html">Go to search</a></nav>
        </body></html>
    """,
    "/search.html": """
        <html><head><title>Search</title></head>
        <body>
            <form action="/results.html" method="GET">
                <input type="text" name="q" placeholder="query">
                <button type="submit">Search</button>
            </form>
        </body></html>
    """,
}

RESULTS_TEMPLATE = """
    <html><head><title>Results</title></head>
    <body>
        <p>You searched for: {q}</p>
        <a href="/thankyou.html">Continue</a>
    </body></html>
"""

THANKYOU_PAGE = """
    <html><head><title>Thank You</title></head>
    <body><h1>All done</h1></body></html>
"""


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silence test output

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/results.html":
            qs = urllib.parse.parse_qs(parsed.query)
            q = qs.get("q", [""])[0]
            body = RESULTS_TEMPLATE.format(q=q).encode("utf-8")
        elif parsed.path == "/thankyou.html":
            body = THANKYOU_PAGE.encode("utf-8")
        elif parsed.path in PAGES:
            body = PAGES[parsed.path].encode("utf-8")
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)


class BrowserNavigationTest(unittest.TestCase):
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

    def _ref_by_role_name(self, snapshot, role, contains):
        for ref, entry in snapshot.ref_index.items():
            if entry["role"] == role and contains.lower() in entry["name"].lower():
                return ref
        self.fail(f"no {role} ref containing {contains!r} in snapshot:\n{snapshot.render()}")

    def test_multi_step_navigation_via_refs(self):
        browser = Browser(timeout=5)

        # Step 1: goto the home page.
        snap = browser.goto(self.base("/index.html"))
        self.assertEqual(snap.title, "Home")

        # Step 2: click the nav link purely by its ref.
        link_ref = self._ref_by_role_name(snap, "link", "search")
        snap = browser.click(link_ref)
        self.assertEqual(snap.title, "Search")

        # Step 3: type into the textbox ref, then click the submit button ref
        # (which resolves the enclosing form and does the GET submit).
        box_ref = self._ref_by_role_name(snap, "textbox", "query")
        browser.type(box_ref, "barebrowse rocks")
        button_ref = self._ref_by_role_name(snap, "button", "search")
        snap = browser.click(button_ref)
        self.assertEqual(snap.title, "Results")
        self.assertIn("barebrowse rocks", snap.render())
        self.assertIn("q=barebrowse", browser.url)

        # Step 4: one more hop, purely by ref, to prove the chain keeps going.
        continue_ref = self._ref_by_role_name(snap, "link", "continue")
        snap = browser.click(continue_ref)
        self.assertEqual(snap.title, "Thank You")

    def test_unknown_ref_raises(self):
        browser = Browser(timeout=5)
        browser.goto(self.base("/index.html"))
        with self.assertRaises(BrowserError):
            browser.click("e999")

    def test_post_form_is_refused_not_silently_downgraded(self):
        browser = Browser(timeout=5)
        html = """
            <html><body>
            <form action="/results.html" method="POST">
                <input type="text" name="q">
                <button type="submit">Go</button>
            </form>
            </body></html>
        """
        # Serve inline via a throwaway page registered on the fly.
        PAGES["/post_form.html"] = html
        snap = browser.goto(self.base("/post_form.html"))
        button_ref = self._ref_by_role_name(snap, "button", "go")
        with self.assertRaises(BrowserError):
            browser.click(button_ref)


if __name__ == "__main__":
    unittest.main()
