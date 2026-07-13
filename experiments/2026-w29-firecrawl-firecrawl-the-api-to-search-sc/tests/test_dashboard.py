import os
import tempfile
import unittest
from html.parser import HTMLParser

from lib.dashboard import render
from lib.diff import diff_snapshots, find_biggest_mover


def make_snapshot():
    return {
        "timestamp": "20260713T000000",
        "sites": [
            {
                "url": "http://a.example",
                "title": "A",
                "word_count": 10,
                "link_count": 2,
                "image_count": 0,
                "links": ["http://a.example/1", "http://a.example/2"],
                "bytes": 100,
                "status": 200,
            },
            {
                "url": "http://b.example",
                "title": "B",
                "word_count": 5,
                "link_count": 1,
                "image_count": 0,
                "links": ["http://b.example/1"],
                "bytes": 50,
                "status": 200,
            },
        ],
    }


def make_mutated_snapshot():
    snap = make_snapshot()
    snap["timestamp"] = "20260713T000100"
    snap["sites"][0]["links"] = [
        "http://a.example/1",
        "http://a.example/2",
        "http://a.example/3",
    ]
    snap["sites"][0]["link_count"] = 3
    snap["sites"][0]["word_count"] = 15
    return snap


class _StrictParser(HTMLParser):
    """Just needs to run feed() without raising to prove the markup is parseable."""

    pass


class TestDashboardRender(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.out_path = os.path.join(self.tmpdir, "dashboard.html")

    def _read(self):
        with open(self.out_path) as f:
            return f.read()

    def test_renders_parseable_html_with_script_block(self):
        snap = make_snapshot()
        render(snap, None, self.out_path)
        html = self._read()

        parser = _StrictParser()
        parser.feed(html)  # must not raise

        self.assertIn("<script>", html)
        self.assertIn("requestAnimationFrame", html)

    def test_first_run_has_no_prior_state(self):
        snap = make_snapshot()
        render(snap, None, self.out_path)
        html = self._read()
        self.assertIn("No prior run", html)
        self.assertIn('data-metric="total_changes" data-value="0"', html)

    def test_aggregate_numbers_match_snapshot_and_diff(self):
        old_snap = make_snapshot()
        new_snap = make_mutated_snapshot()
        diff = diff_snapshots(old_snap, new_snap)

        render(new_snap, diff, self.out_path)
        html = self._read()

        # sites tracked = 2, total_words = 15 + 5 = 20, total_links = 3 + 1 = 4
        self.assertIn('data-metric="sites_tracked" data-value="2"', html)
        self.assertIn('data-metric="total_words" data-value="20"', html)
        self.assertIn('data-metric="total_links" data-value="4"', html)
        self.assertIn(
            f'data-metric="total_changes" data-value="{diff["total_changes"]}"', html
        )
        self.assertGreater(diff["total_changes"], 0)

        # the added link shows up as a rendered diff row
        self.assertIn("http://a.example/3", html)

    def test_error_site_does_not_crash_render(self):
        snap = make_snapshot()
        snap["sites"].append({"url": "http://c.example", "error": "TimeoutError: timed out"})
        diff = diff_snapshots(None, snap)
        render(snap, diff, self.out_path)
        html = self._read()
        self.assertIn("error: TimeoutError", html)

    def test_health_badge_renders_per_site_score(self):
        snap = make_snapshot()
        health_scores = {
            "http://a.example": {"score": 100, "runs": 3, "ok_runs": 3},
            "http://b.example": {"score": 33, "runs": 3, "ok_runs": 1},
        }
        render(snap, None, self.out_path, health_scores=health_scores)
        html = self._read()
        self.assertIn('<span class="badge health good">100% healthy</span>', html)
        self.assertIn('<span class="badge health bad">33% healthy</span>', html)

    def test_missing_health_score_renders_no_badge(self):
        snap = make_snapshot()
        render(snap, None, self.out_path, health_scores={})
        html = self._read()
        self.assertNotIn("healthy", html)

    def test_biggest_mover_callout_renders(self):
        old_snap = make_snapshot()
        new_snap = make_mutated_snapshot()
        diff = diff_snapshots(old_snap, new_snap)
        mover = find_biggest_mover(diff)

        render(new_snap, diff, self.out_path, biggest_mover=mover)
        html = self._read()
        self.assertIn('<div class="mover-label">Biggest mover</div>', html)
        self.assertIn("http://a.example", html.split('class="mover-card"')[1])
        self.assertIn("+5 words", html)

    def test_no_biggest_mover_omits_callout(self):
        snap = make_snapshot()
        render(snap, None, self.out_path, biggest_mover=None)
        html = self._read()
        self.assertNotIn('<div class="mover-card">', html)
        self.assertNotIn("Biggest mover", html)


if __name__ == "__main__":
    unittest.main()
