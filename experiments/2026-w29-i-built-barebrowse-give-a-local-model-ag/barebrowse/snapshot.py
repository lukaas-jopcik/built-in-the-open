"""HTML -> pruned ARIA-role-style text snapshot, using only stdlib html.parser.

The core trade: throw away layout wrappers (div/span/tbody/...), scripts,
styles, and boilerplate, keep only elements with an implicit ARIA role (or an
explicit role="..."), and assign stable `ref` ids to anything interactive
(links, buttons, form fields) so a downstream agent can act on them by ref
without ever touching real DOM/CSS selectors.
"""
from html.parser import HTMLParser

from barebrowse.tokens import estimate_tokens

VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}

# Tags we drop entirely, including their subtree (no text, no children kept).
DROP_SUBTREE = {"script", "style", "noscript", "template", "svg", "head", "iframe"}

# Implicit ARIA roles for tags whose role doesn't depend on attributes.
TAG_ROLE = {
    "a": "link",
    "button": "button",
    "nav": "navigation",
    "main": "main",
    "header": "banner",
    "footer": "contentinfo",
    "aside": "complementary",
    "form": "form",
    "h1": "heading", "h2": "heading", "h3": "heading",
    "h4": "heading", "h5": "heading", "h6": "heading",
    "ul": "list", "ol": "list",
    "li": "listitem",
    "table": "table",
    "tr": "row",
    "td": "cell",
    "th": "columnheader",
    "article": "article",
    "textarea": "textbox",
    "select": "combobox",
    "img": "img",
    "p": "paragraph",
    "label": "label",
}

INPUT_TYPE_ROLE = {
    "submit": "button",
    "button": "button",
    "reset": "button",
    "image": "button",
    "file": "button",
    "checkbox": "checkbox",
    "radio": "radio",
    "hidden": None,  # dropped entirely
}

INTERACTIVE_ROLES = {"link", "button", "textbox", "checkbox", "radio", "combobox"}

MAX_NAME_LEN = 300


class _ElementNode:
    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag, attrs):
        self.tag = tag
        self.attrs = attrs
        self.children = []  # list of _ElementNode or str


class _TreeBuilder(HTMLParser):
    """Builds a raw DOM-ish tree, tolerating malformed/mismatched tags."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _ElementNode("#root", {})
        self._stack = [self.root]
        self.title = None

    def handle_starttag(self, tag, attrs_list):
        attrs = {k: (v or "") for k, v in attrs_list}
        node = _ElementNode(tag, attrs)
        self._stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self._stack.append(node)

    def handle_startendtag(self, tag, attrs_list):
        attrs = {k: (v or "") for k, v in attrs_list}
        node = _ElementNode(tag, attrs)
        self._stack[-1].children.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag:
                del self._stack[i:]
                return
        # unmatched end tag; ignore (malformed HTML tolerance)

    def handle_data(self, data):
        if data:
            self._stack[-1].children.append(data)

    def error(self, message):  # pragma: no cover - py3.10+ HTMLParser never calls this
        pass


class RoleNode:
    """A node in the pruned accessibility-style tree."""

    __slots__ = ("role", "name", "ref", "children", "level")

    def __init__(self, role, name="", ref=None, level=1):
        self.role = role
        self.name = name
        self.ref = ref
        self.children = []
        self.level = level

    def render(self, indent=0):
        pad = "  " * indent
        head = self.role
        if self.ref:
            head += f"[{self.ref}]"
        name = _clean_text(self.name)
        if name:
            head += f' "{name}"'
        lines = [pad + head]
        for child in self.children:
            lines.append(child.render(indent + 1))
        return "\n".join(lines)

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()


def _clean_text(text):
    if not text:
        return ""
    text = " ".join(text.split())
    if len(text) > MAX_NAME_LEN:
        text = text[: MAX_NAME_LEN - 1].rstrip() + "…"
    return text


def _direct_text(elem):
    """Concatenate direct string children (not text of nested elements)."""
    parts = [c for c in elem.children if isinstance(c, str)]
    return " ".join(" ".join(p.split()) for p in parts if p.strip())


def _all_text(elem):
    parts = []
    for c in elem.children:
        if isinstance(c, str):
            if c.strip():
                parts.append(" ".join(c.split()))
        else:
            parts.append(_all_text(c))
    return " ".join(p for p in parts if p)


def _role_for(elem):
    tag = elem.tag
    if tag == "a":
        return "link" if elem.attrs.get("href") else None
    if tag == "input":
        itype = (elem.attrs.get("type") or "text").lower()
        if itype in INPUT_TYPE_ROLE:
            return INPUT_TYPE_ROLE[itype]
        return "textbox"
    if tag == "section":
        return "region" if (elem.attrs.get("aria-label") or elem.attrs.get("id")) else None
    explicit = elem.attrs.get("role")
    if explicit:
        return explicit
    return TAG_ROLE.get(tag)


# Landmark/structural roles whose children already carry the real text; taking
# _all_text here would duplicate every nested link/button's name into the parent.
_STRUCTURAL_ROLES = {
    "navigation", "banner", "contentinfo", "complementary", "main",
    "article", "region", "form", "list", "search",
}


def _name_for(elem, role):
    aria_label = elem.attrs.get("aria-label")
    if aria_label:
        return aria_label
    if role == "img":
        return elem.attrs.get("alt", "")
    if role in ("textbox", "checkbox", "radio", "combobox"):
        placeholder = elem.attrs.get("placeholder")
        value = elem.attrs.get("value")
        name = elem.attrs.get("name")
        return placeholder or value or name or ""
    if role in _STRUCTURAL_ROLES:
        return _direct_text(elem)
    return _all_text(elem)


class Snapshot:
    """A pruned role-tree plus a ref -> element-metadata index for the Browser."""

    def __init__(self, roots, ref_index, title=""):
        self.roots = roots
        self.ref_index = ref_index  # ref -> dict(role, name, tag, attrs)
        self.title = title

    def render(self):
        lines = []
        if self.title:
            lines.append(f'document "{self.title}"')
        for root in self.roots:
            lines.append(root.render(0))
        return "\n".join(lines)

    def token_count(self):
        return estimate_tokens(self.render())

    def find_ref(self, ref):
        return self.ref_index.get(ref)


def build_snapshot(html_text, base_url=None):
    builder = _TreeBuilder()
    builder.feed(html_text)
    builder.close()

    ref_index = {}
    counter = [0]

    def next_ref():
        counter[0] += 1
        return f"e{counter[0]}"

    def convert(elem, level, form_ctx):
        """Return list of RoleNode produced from this element (0, 1)."""
        if isinstance(elem, str):
            return []
        if elem.tag in DROP_SUBTREE:
            return []
        if elem.tag == "title":
            return []  # handled separately for document title

        role = _role_for(elem)

        if elem.tag == "form":
            form_ctx = {
                "action": elem.attrs.get("action", ""),
                "method": (elem.attrs.get("method") or "get").lower(),
                "fields": [],
            }

        if role is None:
            # Non-semantic wrapper: flatten, splice children up to parent level.
            out = []
            for child in elem.children:
                out.extend(convert(child, level, form_ctx))
            return out

        name = _name_for(elem, role)
        node = RoleNode(role, name, level=level)

        if role in INTERACTIVE_ROLES:
            ref = next_ref()
            node.ref = ref
            entry = {
                "role": role,
                "name": _clean_text(name),
                "tag": elem.tag,
                "attrs": dict(elem.attrs),
                "form": form_ctx,
            }
            ref_index[ref] = entry
            if form_ctx is not None and role in ("textbox", "checkbox", "radio", "combobox"):
                form_ctx["fields"].append(ref)
            if form_ctx is not None and role == "button":
                form_ctx.setdefault("submit_refs", []).append(ref)

        # True leaves: their whole accessible name is text, never descend further
        # (avoids e.g. a <button><span>Search</span></button> spawning a child node).
        if role in ("link", "button", "img", "textbox", "checkbox", "radio", "combobox"):
            return [node]

        # Text-container roles (heading/paragraph/label) keep their full text as
        # `name` but still descend, so a link/button nested inside keeps its ref.
        for child in elem.children:
            node.children.extend(convert(child, level + 1, form_ctx))

        # Drop empty structural nodes (no text, no children, no ref).
        if not node.children and not node.name and not node.ref:
            return []
        return [node]

    roots = []
    for child in builder.root.children:
        roots.extend(convert(child, 1, None))

    title = _find_title(builder.root)
    return Snapshot(roots, ref_index, title=title)


def _find_title(root):
    def walk(elem):
        if isinstance(elem, str):
            return None
        if elem.tag == "title":
            return _all_text(elem).strip()
        for c in elem.children:
            found = walk(c)
            if found:
                return found
        return None

    return walk(root) or ""


def snapshot_url(url, timeout=10):
    from barebrowse.fetch import fetch

    final_url, html_text = fetch(url, timeout=timeout)
    return build_snapshot(html_text, base_url=final_url), final_url, html_text
