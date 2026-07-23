import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dag import topological_order, topological_waves


class TestDag(unittest.TestCase):
    def test_linear_order(self):
        steps = [
            {"id": "a", "deps": []},
            {"id": "b", "deps": ["a"]},
            {"id": "c", "deps": ["b"]},
        ]
        order = topological_order(steps)
        self.assertEqual(order, ["a", "b", "c"])

    def test_diamond_order(self):
        steps = [
            {"id": "a", "deps": []},
            {"id": "b", "deps": ["a"]},
            {"id": "c", "deps": ["a"]},
            {"id": "d", "deps": ["b", "c"]},
        ]
        order = topological_order(steps)
        self.assertEqual(order[0], "a")
        self.assertEqual(order[-1], "d")
        self.assertEqual(set(order[1:3]), {"b", "c"})

    def test_unknown_dep_raises(self):
        steps = [{"id": "a", "deps": ["ghost"]}]
        with self.assertRaises(ValueError):
            topological_order(steps)

    def test_cycle_raises(self):
        steps = [
            {"id": "a", "deps": ["b"]},
            {"id": "b", "deps": ["a"]},
        ]
        with self.assertRaises(ValueError):
            topological_order(steps)

    def test_duplicate_id_raises(self):
        steps = [{"id": "a", "deps": []}, {"id": "a", "deps": []}]
        with self.assertRaises(ValueError):
            topological_order(steps)


class TestTopologicalWaves(unittest.TestCase):
    def test_linear_chain_is_one_step_per_wave(self):
        steps = [
            {"id": "a", "deps": []},
            {"id": "b", "deps": ["a"]},
            {"id": "c", "deps": ["b"]},
        ]
        waves = topological_waves(steps)
        self.assertEqual(waves, [["a"], ["b"], ["c"]])

    def test_independent_steps_share_one_wave(self):
        steps = [
            {"id": "a", "deps": []},
            {"id": "b", "deps": []},
            {"id": "c", "deps": []},
        ]
        waves = topological_waves(steps)
        self.assertEqual(len(waves), 1)
        self.assertEqual(set(waves[0]), {"a", "b", "c"})

    def test_diamond_groups_siblings_into_middle_wave(self):
        steps = [
            {"id": "a", "deps": []},
            {"id": "b", "deps": ["a"]},
            {"id": "c", "deps": ["a"]},
            {"id": "d", "deps": ["b", "c"]},
        ]
        waves = topological_waves(steps)
        self.assertEqual(waves[0], ["a"])
        self.assertEqual(set(waves[1]), {"b", "c"})
        self.assertEqual(waves[2], ["d"])

    def test_every_step_appears_exactly_once(self):
        steps = [
            {"id": "a", "deps": []},
            {"id": "b", "deps": []},
            {"id": "c", "deps": ["a"]},
            {"id": "d", "deps": ["a", "b"]},
            {"id": "e", "deps": ["c", "d"]},
        ]
        waves = topological_waves(steps)
        flat = [s for wave in waves for s in wave]
        self.assertEqual(sorted(flat), ["a", "b", "c", "d", "e"])
        self.assertEqual(len(flat), len(set(flat)))

    def test_unknown_dep_raises(self):
        steps = [{"id": "a", "deps": ["ghost"]}]
        with self.assertRaises(ValueError):
            topological_waves(steps)

    def test_cycle_raises(self):
        steps = [
            {"id": "a", "deps": ["b"]},
            {"id": "b", "deps": ["a"]},
        ]
        with self.assertRaises(ValueError):
            topological_waves(steps)

    def test_duplicate_id_raises(self):
        steps = [{"id": "a", "deps": []}, {"id": "a", "deps": []}]
        with self.assertRaises(ValueError):
            topological_waves(steps)


if __name__ == "__main__":
    unittest.main()
