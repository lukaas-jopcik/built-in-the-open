# barebrowse

A stdlib-only Python tool that turns any web page into a pruned, ARIA-role-style
text snapshot — no Playwright, no headless Chrome — then drives an autonomous
agent (local Ollama model, or a deterministic rule-based fallback) through a
real multi-step task using only that snapshot text.

## Pipeline

```
snapshot.py   HTML -> pruned ARIA-role tree (stdlib html.parser only)
browser.py    Browser: goto/click/type/submit, navigates purely by snapshot refs
agent.py      snapshot -> policy (ollama or rule-based) -> Browser action -> repeat
bench.py      raw-HTML vs. snapshot token counts across a fixed page list
render_report.py   run_log.jsonl (+ bench_results.json) -> standalone report.html
```

```
python3 -m barebrowse snapshot https://example.com
python3 barebrowse/bench.py --pages pages.txt --out bench_results.json
python3 barebrowse/agent.py --task task.json --runs 10 --out run_log.jsonl
python3 barebrowse/render_report.py run_log.jsonl bench_results.json -o report.html
```

## Snapshot text format

Each line is `role[ref] "accessible name"`, indented by nesting depth:

```
document "Search"
navigation
  link[e1] "Home"
form
  textbox[e2] "query"
  button[e3] "Search"
```

- `role` is the implicit ARIA role (`link`, `button`, `textbox`, `heading`,
  `navigation`, `list`, `table`, ...), mapped from the HTML tag or an explicit
  `role="..."` attribute.
- `[ref]` (e.g. `e2`) only appears on interactive elements (links, buttons,
  form fields) — it's the stable id `Browser.click/type` act on.
- Non-semantic wrappers (`div`, `span`, layout `<table>` soup), `<script>`,
  `<style>`, and `<iframe>` subtrees are dropped entirely.

## Browser API

```python
from barebrowse.browser import Browser

b = Browser(timeout=10)
snap = b.goto("https://example.com")     # -> Snapshot (see format above)
snap = b.click(ref)                       # link -> navigates; button in a form -> submits it
b.type(ref, "hello")                      # stages a value for the field's next submit()
snap = b.submit(ref)                      # GET-submits the enclosing form (POST forms raise BrowserError)
```

`snap.render()` gives the text above; `snap.ref_index` maps each `ref` to its
`role`/`name`/`tag`/`attrs`/`form` metadata. Unknown refs or wrong-role calls
(e.g. `type()` on a link) raise `BrowserError` instead of failing silently.

## Pointing agent.py at a new task/site

`agent.py`'s rule-based fallback is generic over a task file — no code
changes needed, just a new JSON (see `task.json` for the working example):

```json
{
  "start_url": "https://example.com/",
  "query": "what to search for",
  "target_substring": "text that identifies the right search result link",
  "extract_regex": "regex with one capture group for the fact to pull out",
  "max_steps": 6
}
```

Then run:

```
python3 barebrowse/agent.py --task your_task.json --runs 10 --out run_log.jsonl
```

The rule-based policy: types `query` into the first textbox it finds on
`start_url`, clicks the first submit button, looks for a result link
containing `target_substring`, follows it, then applies `extract_regex`
against the destination page's snapshot text to produce the final answer.

If a local Ollama server is reachable at `http://localhost:11434`
(`ollama pull llama3.2 && ollama serve`), pass `--policy auto` (or `ollama`)
to drive the same task off free-form model output instead — same task file,
no code changes.

## Tests

```
python3 -m pytest tests/ -q
```

Every module has a no-external-network test (local stdlib `http.server`
fixtures) except the live end-to-end run against real Wikipedia, which is a
manual step in the test plan, not part of `pytest`.
