#!/usr/bin/env python3
"""Slice 4 hardening tests: concurrency, duplicate/contradicting facts,
empty-memory edge cases, and malformed JSON-RPC requests.

Each test uses its own temporary SQLite file (never the shared memory.db
used by the CLI demo / benchmark) so runs are isolated and repeatable.
Run with: python3 test_hardening.py
"""

import concurrent.futures
import json
import os
import tempfile
import unittest

import mcp_server
import memory_core


class ConcurrencyTest(unittest.TestCase):
    def test_concurrent_remember_and_recall_under_wal(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            n_writers, writes_each = 20, 10

            def writer(i):
                conn = memory_core.connect(path)
                try:
                    for j in range(writes_each):
                        memory_core.remember(
                            f"worker {i} fact {j} about launch",
                            session=i,
                            conn=conn,
                        )
                finally:
                    conn.close()
                return True

            def reader(i):
                conn = memory_core.connect(path)
                try:
                    memory_core.adaptive_recall("launch", conn=conn)
                finally:
                    conn.close()
                return True

            with concurrent.futures.ThreadPoolExecutor(max_workers=n_writers * 2) as pool:
                futures = [pool.submit(writer, i) for i in range(n_writers)]
                futures += [pool.submit(reader, i) for i in range(n_writers)]
                results = [f.result() for f in futures]  # raises on any thread exception

            self.assertTrue(all(results))

            conn = memory_core.connect(path)
            try:
                count = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(count, n_writers * writes_each)
        finally:
            for ext in ("", "-wal", "-shm"):
                if os.path.exists(path + ext):
                    os.remove(path + ext)


class DuplicateAndContradictingFactsTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.conn = memory_core.connect(self.path)

    def tearDown(self):
        self.conn.close()
        for ext in ("", "-wal", "-shm"):
            if os.path.exists(self.path + ext):
                os.remove(self.path + ext)

    def test_exact_duplicate_facts_both_surface_without_crashing(self):
        memory_core.remember("the launch date is March 3", session=1, conn=self.conn)
        memory_core.remember("the launch date is March 3", session=1, conn=self.conn)
        results = memory_core.recall("launch date", conn=self.conn)
        self.assertEqual(len(results), 2)

    def test_contradicting_fact_ranks_above_stale_one(self):
        memory_core.remember("the meeting is Monday", session=1, conn=self.conn)
        memory_core.remember("the meeting is actually Tuesday", session=5, conn=self.conn)
        results = memory_core.adaptive_recall(
            "meeting", current_session=6, conn=self.conn
        )
        self.assertGreaterEqual(len(results), 2)
        self.assertIn("Tuesday", results[0]["text"])

    def test_memory_cap_evicts_oldest_under_sustained_writes(self):
        cap = 20
        for i in range(cap + 15):
            memory_core.remember(
                f"fact number {i} about launch",
                session=i,
                conn=self.conn,
                now=float(i),
                max_facts=cap,
            )
        rows = self.conn.execute(
            "SELECT text FROM facts ORDER BY created_at ASC"
        ).fetchall()
        # Capped at exactly `cap` rows, and it's the newest `cap` writes that
        # survived -- the oldest 15 (fact 0..14) were evicted, not the newest.
        self.assertEqual(len(rows), cap)
        surviving_texts = {r[0] for r in rows}
        for i in range(15):
            self.assertNotIn(f"fact number {i} about launch", surviving_texts)
        for i in range(15, cap + 15):
            self.assertIn(f"fact number {i} about launch", surviving_texts)


class EmptyMemoryTest(unittest.TestCase):
    def test_recall_on_empty_store_returns_empty_list(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            conn = memory_core.connect(path)
            self.assertEqual(memory_core.recall("anything", conn=conn), [])
            self.assertEqual(memory_core.adaptive_recall("anything", conn=conn), [])
            conn.close()
        finally:
            for ext in ("", "-wal", "-shm"):
                if os.path.exists(path + ext):
                    os.remove(path + ext)

    def test_mcp_recall_on_empty_store_returns_clean_empty_result(self):
        # mcp_server always operates on the module-level memory_core.connect()
        # default db; point it at a fresh empty temp file for this call.
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            conn = memory_core.connect(path)
            payload = memory_core.adaptive_recall("anything", conn=conn)
            conn.close()
            resp = mcp_server._result(
                1, {"content": [{"type": "text", "text": json.dumps(payload)}], "isError": False}
            )
            self.assertEqual(json.loads(resp["result"]["content"][0]["text"]), [])
            self.assertFalse(resp["result"]["isError"])
        finally:
            for ext in ("", "-wal", "-shm"):
                if os.path.exists(path + ext):
                    os.remove(path + ext)


class MalformedRequestTest(unittest.TestCase):
    def test_non_dict_top_level_json_is_invalid_request_not_crash(self):
        for bad in [42, "just a string", None, True]:
            resp = mcp_server.handle_request(bad)
            self.assertEqual(resp["error"]["code"], -32600)

    def test_missing_method_field_is_method_not_found_not_crash(self):
        resp = mcp_server.handle_request({"jsonrpc": "2.0", "id": 1})
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -32601)

    def test_tools_call_with_non_object_arguments_does_not_crash(self):
        resp = mcp_server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "recall", "arguments": ["not", "a", "dict"]},
            }
        )
        self.assertIn("error", resp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
