[← all experiments](../../)

# Trimming Claude Code's Hidden Token Tax

*A single config flag cut headless input tokens from 48,854 to 40,089 — an 18% reduction, with zero logic changes.*

## The wave

Autonomous agents live and die by cost per call, and headless Claude Code calls are the backbone of that loop. Nobody audits the fixed overhead baked into every single request until it's burning budget at scale. We measured it instead of assuming it.

## The build

- Ran a minimal headless Claude Code call (`-p "PONG"`) and captured the reported input token count.
- Reran the identical call with `--strict-mcp-config` and an empty `mcpServers` config.
- Compared input token counts directly from the JSON output of each run — no estimation, just the numbers the CLI reports.

## The numbers

- Baseline headless call: **48,854** input tokens for a simple PONG response
- With `--strict-mcp-config` + empty `mcpServers`: **40,089** input tokens
- Reduction: **18%**
- MCP servers and settings alone account for **3.4x** token overhead
- Caveat: single test case (PONG), single flag combination — not swept across prompt sizes or MCP server counts

## Run it

```
claude -p "PONG" --output-format json

claude -p "PONG" --strict-mcp-config --mcp-config '{"mcpServers":{}}' --output-format json
```

Compare the `usage.input_tokens` field in each JSON response.

## Verdict

Win. One flag, no code changes, 18% fewer input tokens on every headless call.

## Post

_link added when the LinkedIn post is live_

---

**Cost:** $13.29 across 23 Claude run(s) — see `cost.json`.

<sub>Part of [built in the open](../../) — real experiments, real numbers · by [Lukáš Jopčík](https://www.linkedin.com/in/luk%C3%A1%C5%A1-jop%C4%8D%C3%ADk-087064223/)</sub>
