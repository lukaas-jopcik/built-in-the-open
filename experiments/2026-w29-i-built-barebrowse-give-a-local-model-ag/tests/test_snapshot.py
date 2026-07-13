"""Static-fixture tests for the snapshot engine (no network calls)."""
from barebrowse.snapshot import build_snapshot

SAMPLE_HTML = """
<html><head><title>Sample Page</title>
<script>var x = 1;</script>
<style>body{color:red}</style>
</head>
<body>
<header><nav><ul>
  <li><a href="/a">Home</a></li>
  <li><a href="/b">About</a></li>
</ul></nav></header>
<main>
  <h1>Welcome</h1>
  <p>This is <b>bold</b> text with a <a href="/c">link</a> inside.</p>
  <form action="/search">
    <input type="text" name="q" placeholder="Search here">
    <button type="submit">Go</button>
  </form>
  <table>
    <tr><th>Name</th><th>Score</th></tr>
    <tr><td>Ann</td><td>42</td></tr>
  </table>
</main>
</body></html>
"""


def test_no_traceback_and_nonempty():
    snap = build_snapshot(SAMPLE_HTML)
    rendered = snap.render()
    assert rendered.strip()


def test_scripts_and_styles_stripped():
    snap = build_snapshot(SAMPLE_HTML)
    rendered = snap.render()
    assert "var x" not in rendered
    assert "color:red" not in rendered


def test_refs_assigned_to_interactive_elements():
    snap = build_snapshot(SAMPLE_HTML)
    roles = {ref: info["role"] for ref, info in snap.ref_index.items()}
    assert set(roles.values()) >= {"link", "textbox", "button"}
    # 2 nav links + 1 in-paragraph link + 1 textbox + 1 button = 5 refs
    assert len(snap.ref_index) == 5


def test_nested_link_inside_paragraph_keeps_ref():
    snap = build_snapshot(SAMPLE_HTML)
    rendered = snap.render()
    link_lines = [l for l in rendered.splitlines() if l.strip().startswith("link[")]
    assert any('"link"' in l for l in link_lines)


def test_table_cell_text_preserved():
    snap = build_snapshot(SAMPLE_HTML)
    rendered = snap.render()
    assert "Ann" in rendered
    assert "42" in rendered


def test_structural_roles_dont_duplicate_child_text():
    snap = build_snapshot(SAMPLE_HTML)
    rendered = snap.render()
    # The <nav>/<ul> landmark lines themselves must stay bare ("navigation",
    # "list" with no quoted name) — the "Home"/"About" text belongs to their
    # listitem/link descendants, not duplicated onto the landmark line too.
    landmark_lines = [
        l for l in rendered.splitlines()
        if l.strip().split("[")[0].split(" ")[0] in ("navigation", "list", "banner")
    ]
    assert landmark_lines
    assert all('"' not in l for l in landmark_lines)


def test_title_captured():
    snap = build_snapshot(SAMPLE_HTML)
    assert snap.title == "Sample Page"


def test_token_count_reduces_vs_raw():
    snap = build_snapshot(SAMPLE_HTML)
    from barebrowse.tokens import estimate_tokens

    raw_tokens = estimate_tokens(SAMPLE_HTML)
    assert snap.token_count() < raw_tokens


def test_malformed_html_does_not_crash():
    malformed = "<div><p>Unclosed paragraph<div>Nested without closing p</div></div>"
    snap = build_snapshot(malformed)
    assert snap.render() is not None


EDGE_CASE_HTML = """
<html><head><title>Edge Cases</title></head>
<body>
<iframe src="https://ads.example.com/frame"><p>ad content that must not leak out</p></iframe>
<section aria-label="Highlights"><h2>Highlights</h2><p>landmark region text</p></section>
""" + "<div>" * 25 + """
  <nav aria-label="Breadcrumbs"><a href="/x">Deeply nested link</a></nav>
""" + "</div>" * 25 + """
<table>
  <tr><th>Col A</th><th>Col B</th></tr>
  <tr><td>1</td><td><a href="/row2">row link</a></td></tr>
</table>
</body></html>
"""


def test_iframe_subtree_dropped_entirely():
    snap = build_snapshot(EDGE_CASE_HTML)
    rendered = snap.render()
    assert "ad content that must not leak out" not in rendered


def test_aria_landmark_region_recognized():
    snap = build_snapshot(EDGE_CASE_HTML)
    rendered = snap.render()
    assert "region" in rendered
    assert "landmark region text" in rendered


def test_deeply_nested_divs_flattened_but_link_survives():
    snap = build_snapshot(EDGE_CASE_HTML)
    rendered = snap.render()
    roles = {ref: info["role"] for ref, info in snap.ref_index.items()}
    assert any(info["name"] == "Deeply nested link" for info in snap.ref_index.values())
    # 25 layers of bare <div> wrappers must not survive as their own nodes.
    assert "\ngeneric" not in rendered and rendered.count("div") == 0


def test_table_with_nested_link_stays_compact_and_lossless():
    snap = build_snapshot(EDGE_CASE_HTML)
    rendered = snap.render()
    assert "row link" in rendered
    from barebrowse.tokens import estimate_tokens

    # Compact relative to the raw markup even with iframe/landmark/deep-nesting noise.
    assert snap.token_count() < estimate_tokens(EDGE_CASE_HTML) * 0.5
