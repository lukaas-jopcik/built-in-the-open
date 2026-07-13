import copy
import unittest

from lib.diff import diff_snapshots, find_biggest_mover


def make_snapshot(**overrides):
    site = {
        "url": "http://a.example",
        "title": "A",
        "word_count": 10,
        "link_count": 2,
        "image_count": 0,
        "links": ["http://a.example/1", "http://a.example/2"],
        "bytes": 100,
        "status": 200,
    }
    site.update(overrides)
    return {"timestamp": "20260713T000000", "sites": [site]}


class TestDiffSnapshots(unittest.TestCase):
    def test_identical_snapshots_have_zero_changes(self):
        snap = make_snapshot()
        result = diff_snapshots(copy.deepcopy(snap), copy.deepcopy(snap))
        self.assertEqual(result["total_changes"], 0)
        entry = result["per_site"]["http://a.example"]
        self.assertEqual(entry["added_links"], [])
        self.assertEqual(entry["removed_links"], [])
        self.assertEqual(entry["word_count_delta"], 0)
        self.assertFalse(entry["title_changed"])

    def test_mutated_snapshot_flags_added_link_and_word_delta(self):
        old_snap = make_snapshot()
        new_snap = make_snapshot(
            links=["http://a.example/1", "http://a.example/2", "http://a.example/3"],
            link_count=3,
            word_count=15,
        )
        result = diff_snapshots(old_snap, new_snap)
        self.assertGreater(result["total_changes"], 0)
        entry = result["per_site"]["http://a.example"]
        self.assertIn("http://a.example/3", entry["added_links"])
        self.assertEqual(entry["removed_links"], [])
        self.assertEqual(entry["word_count_delta"], 5)

    def test_removed_link_is_detected(self):
        old_snap = make_snapshot()
        new_snap = make_snapshot(links=["http://a.example/1"], link_count=1)
        result = diff_snapshots(old_snap, new_snap)
        entry = result["per_site"]["http://a.example"]
        self.assertEqual(entry["added_links"], [])
        self.assertIn("http://a.example/2", entry["removed_links"])
        self.assertGreater(result["total_changes"], 0)

    def test_title_change_counts_as_a_change(self):
        old_snap = make_snapshot()
        new_snap = make_snapshot(title="A New Title")
        result = diff_snapshots(old_snap, new_snap)
        entry = result["per_site"]["http://a.example"]
        self.assertTrue(entry["title_changed"])
        self.assertEqual(result["total_changes"], 1)

    def test_no_prior_snapshot_marks_site_as_new(self):
        new_snap = make_snapshot()
        result = diff_snapshots(None, new_snap)
        entry = result["per_site"]["http://a.example"]
        self.assertTrue(entry["is_new"])
        self.assertGreater(result["total_changes"], 0)

    def test_error_site_is_not_diffed_but_does_not_crash(self):
        old_snap = make_snapshot()
        new_snap = {
            "timestamp": "20260713T000001",
            "sites": [{"url": "http://a.example", "error": "TimeoutError: timed out"}],
        }
        result = diff_snapshots(old_snap, new_snap)
        entry = result["per_site"]["http://a.example"]
        self.assertTrue(entry["unavailable"])
        self.assertEqual(entry["changes"], 0)


if __name__ == "__main__":
    unittest.main()
