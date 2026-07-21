#!/usr/bin/env python3
"""Minimal MCP-flavored JSON-RPC 2.0 server over stdio.

Implements just enough of the Model Context Protocol tool-call surface
(initialize / tools/list / tools/call) to expose `remember` and `recall`
as MCP tools, using stdlib json/sys only -- no MCP SDK dependency. Reads
one JSON-RPC request per line from stdin and writes one JSON-RPC response
per line to stdout so it can be driven by `printf ... | python3
mcp_server.py` or wired into a real MCP client's stdio transport.
"""

import json
import sys

import memory_core

PROTOCOL_VERSION = "2024-11-05"

TOOLS = [
    {
        "name": "remember",
        "description": "Persist a fact to long-term memory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["text"],
        },
    },
    {
        "name": "recall",
        "description": (
            "Retrieve facts relevant to a query, ranked by adaptive "
            "recency-decay + keyword-overlap score."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "k": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
]


def _error(id_, code, message):
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def _result(id_, result):
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def handle_request(req):
    if not isinstance(req, dict):
        return _error(None, -32600, "Invalid Request")

    id_ = req.get("id")
    method = req.get("method")

    if method == "initialize":
        return _result(
            id_,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "adaptive-recall-bench", "version": "0.1.0"},
            },
        )

    if method == "tools/list":
        return _result(id_, {"tools": TOOLS})

    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            if name == "remember":
                text = arguments["text"]
                tags = arguments.get("tags") or []
                row_id = memory_core.remember(text, tags=tags)
                payload = {"id": row_id, "text": text}
            elif name == "recall":
                query = arguments["query"]
                k = arguments.get("k", 5)
                payload = memory_core.adaptive_recall(query, k=k)
            else:
                return _error(id_, -32601, f"Unknown tool: {name}")
        except KeyError as exc:
            return _error(id_, -32602, f"Missing required argument: {exc}")
        except Exception as exc:  # tool crashed -- report, don't propagate
            return _error(id_, -32000, f"Tool execution error: {exc}")

        return _result(
            id_,
            {
                "content": [{"type": "text", "text": json.dumps(payload)}],
                "isError": False,
            },
        )

    return _error(id_, -32601, f"Method not found: {method}")


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            print(json.dumps(_error(None, -32700, f"Parse error: {exc}")), flush=True)
            continue

        if isinstance(req, list):
            print(json.dumps([handle_request(r) for r in req]), flush=True)
            continue

        print(json.dumps(handle_request(req)), flush=True)


if __name__ == "__main__":
    main()
