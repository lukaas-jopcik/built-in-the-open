import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dsl import load_sky, SkyError


class TestDsl(unittest.TestCase):
    def _write(self, obj):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".sky", delete=False)
        json.dump(obj, f)
        f.close()
        return f.name

    def test_valid_minimal(self):
        path = self._write({"steps": [{"id": "a", "tool": "fetch", "args": {}}]})
        sky = load_sky(path)
        self.assertEqual(sky["steps"][0]["deps"], [])
        self.assertEqual(sky["output"], "report.json")
        os.unlink(path)

    def test_missing_steps_raises(self):
        path = self._write({})
        with self.assertRaises(SkyError):
            load_sky(path)
        os.unlink(path)

    def test_missing_tool_raises(self):
        path = self._write({"steps": [{"id": "a"}]})
        with self.assertRaises(SkyError):
            load_sky(path)
        os.unlink(path)

    def test_duplicate_id_raises(self):
        path = self._write({"steps": [
            {"id": "a", "tool": "fetch"},
            {"id": "a", "tool": "fetch"},
        ]})
        with self.assertRaises(SkyError):
            load_sky(path)
        os.unlink(path)

    def test_invalid_json_raises(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".sky", delete=False)
        f.write("{not json")
        f.close()
        with self.assertRaises(SkyError):
            load_sky(f.name)
        os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
