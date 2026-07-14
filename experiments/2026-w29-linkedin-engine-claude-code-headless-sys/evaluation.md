## Verdict: win

## Numbers
- MCP servers and settings add 3.4x token overhead to headless calls
- Baseline headless claude call uses 48,854 input tokens for simple PONG response
- Adding --strict-mcp-config and empty mcpServers reduces to 40,089 tokens (18% reduction)

## Source
linkedin-engine — Claude Code headless system-prompt overhead benchmarked — real work already shipped (claude-mem obs-24285); the numbers above are from the work log, not estimates.
