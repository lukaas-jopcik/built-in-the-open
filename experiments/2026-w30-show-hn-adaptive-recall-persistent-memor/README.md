# Adaptive Recall Bench

A minimal, stdlib-only, SQLite-backed persistent-memory server that speaks
MCP-flavored JSON-RPC 2.0 over stdio, plus a reproducible benchmark proving
it beats a stateless (no-memory) agent at recalling facts across sessions.

See [`prd.md`](prd.md) for the full spec, and [`build-log.md`](build-log.md)
for how each slice was built and tested. This README covers day-2 usage:
wiring `mcp_server.py` into a real MCP client.

## What's here

| File | Purpose |
|---|---|
| `memory_core.py` | stdlib SQLite fact store: `remember()` / `recall()` / `adaptive_recall()`. Also a CLI. |
| `mcp_server.py` | MCP tool-call surface (`initialize`, `tools/list`, `tools/call`) over stdio, no MCP SDK dependency. |
| `benchmark.py` | 50-conversation deterministic benchmark, writes `results.json` + `dashboard.html`. |
| `sweep.py` | parameter-sensitivity sweep over recency half-life / keyword weight, writes `sweep_dashboard.html`. |
| `memory_graph.py` | renders the fact&rarr;query recall graph, writes `memory_graph.html`. |
| `test_hardening.py` | concurrency, contradiction, eviction, and malformed-input tests. |

## Quick start

```bash
python3 memory_core.py remember "demo fact"
python3 memory_core.py recall "demo"
python3 mcp_server.py < sample_request.json
python3 benchmark.py --sessions 50 --seed 42
open dashboard.html   # or: python3 -m http.server 8000, then visit /dashboard.html
```

## Wiring `mcp_server.py` into a real MCP client

`mcp_server.py` implements the MCP stdio transport and the three methods a
tool-calling client needs (`initialize`, `tools/list`, `tools/call`). Point
any MCP-compatible client at it by running it as a subprocess with `python3`.

**Claude Desktop** — add to `claude_desktop_config.json` (macOS:
`~/Library/Application Support/Claude/claude_desktop_config.json`; Windows:
`%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "adaptive-recall": {
      "command": "python3",
      "args": ["/absolute/path/to/mcp_server.py"]
    }
  }
}
```

**Claude Code** — add the same shape under `mcpServers` in your Claude Code
MCP settings (project `.mcp.json`, or via `claude mcp add`):

```json
{
  "mcpServers": {
    "adaptive-recall": {
      "command": "python3",
      "args": ["/absolute/path/to/mcp_server.py"]
    }
  }
}
```

Use an **absolute path** to `mcp_server.py` — the client launches the
process from its own working directory, not this repo. `memory_core.py`
resolves `memory.db` relative to its own file location (this repo directory),
not the caller's working directory, so memory persists to the same file
across restarts regardless of what directory the MCP client launches from.

After restarting the client, `remember` and `recall` should show up as
available tools. `remember` takes `{"text": "...", "tags": ["..."]}`, and
`recall` takes `{"query": "...", "k": 5}` and returns facts ranked by the
same recency+keyword blend the benchmark measures.

### What's simplified vs. the full MCP spec

This is deliberately a "just enough" MCP surface, per `prd.md`'s stated
scope (see "Out of scope") — not a full protocol implementation:

- No `notifications/*`, `resources/*`, or `prompts/*` methods — only
  `initialize` / `tools/list` / `tools/call`.
- No capability negotiation beyond a static `{"tools": {}}` block.
- One JSON-RPC request per newline on stdin (batch arrays are also
  supported); no support for the SSE/HTTP transport variants of MCP, stdio
  only.

If a client needs more than tool-calling, it's worth swapping in the
official MCP Python SDK — this implementation's value is being a from-scratch,
zero-dependency reference for what the wire protocol actually looks like.

## Other artifacts

- `dashboard.html` — the wow-shot split-screen benchmark report.
- `sweep_dashboard.html` — parameter-sensitivity sweep (recency half-life x
  keyword weight).
- `memory_graph.html` — force-directed fact&rarr;query recall graph, a second
  visual angle on the same benchmark run.

All three are standalone `file://`-openable HTML, cross-linked to each other,
and regenerate from `results.json` / `sweep_results.json` — re-run
`benchmark.py`, `sweep.py`, or `memory_graph.py` after changing
`memory_core.py`'s ranking to refresh all three at once.
