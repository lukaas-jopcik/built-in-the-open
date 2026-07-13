import unittest

from lib.health import compute_health_scores


def snap(ts, sites):
    return {"timestamp": ts, "sites": sites}


class TestComputeHealthScores(unittest.TestCase):
    def test_all_ok_runs_score_100(self):
        history = [
            snap("1", [{"url": "http://a.example", "word_count": 5}]),
            snap("2", [{"url": "http://a.example", "word_count": 6}]),
        ]
        scores = compute_health_scores(history)
        self.assertEqual(scores["http://a.example"]["score"], 100)
        self.assertEqual(scores["http://a.example"]["runs"], 2)

    def test_one_failure_out_of_two_scores_50(self):
        history = [
            snap("1", [{"url": "http://a.example", "error": "boom"}]),
            snap("2", [{"url": "http://a.example", "word_count": 6}]),
        ]
        scores = compute_health_scores(history)
        self.assertEqual(scores["http://a.example"]["score"], 50)
        self.assertEqual(scores["http://a.example"]["ok_runs"], 1)

    def test_skipped_counts_as_not_ok(self):
        history = [snap("1", [{"url": "http://a.example", "skipped": "non-html"}])]
        scores = compute_health_scores(history)
        self.assertEqual(scores["http://a.example"]["score"], 0)

    def test_lookback_limits_to_most_recent_runs(self):
        history = [snap(str(i), [{"url": "http://a.example", "error": "boom"}]) for i in range(5)]
        history.append(snap("5", [{"url": "http://a.example", "word_count": 1}]))
        scores = compute_health_scores(history, lookback=1)
        # only the last (successful) run counts
        self.assertEqual(scores["http://a.example"]["score"], 100)
        self.assertEqual(scores["http://a.example"]["runs"], 1)

    def test_unknown_site_not_in_result(self):
        history = [snap("1", [{"url": "http://a.example", "word_count": 5}])]
        scores = compute_health_scores(history)
        self.assertNotIn("http://never-seen.example", scores)

    def test_empty_history_returns_empty(self):
        self.assertEqual(compute_health_scores([]), {})


if __name__ == "__main__":
    unittest.main()
