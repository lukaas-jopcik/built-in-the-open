"""A `Browser` object that drives snapshot-derived refs instead of a real DOM.

No JS execution, no real browser: `goto` fetches HTML and builds a pruned
snapshot (barebrowse.snapshot), `click`/`type`/`submit` act purely on the
`ref` ids exposed in that snapshot's text. Network is GET-only by design
(matches the fetch layer) — forms whose method="post" are refused rather
than silently downgraded, since we can't actually perform the POST.
"""
import urllib.parse

from barebrowse.fetch import FetchError, fetch
from barebrowse.snapshot import build_snapshot


class BrowserError(Exception):
    pass


class Browser:
    def __init__(self, timeout=10):
        self.timeout = timeout
        self.url = None
        self.html = None
        self.snapshot = None
        self._values = {}  # ref -> text typed via type(), reset on each goto()

    def goto(self, url):
        if self.url:
            url = urllib.parse.urljoin(self.url, url)
        try:
            final_url, html_text = fetch(url, timeout=self.timeout)
        except FetchError as e:
            raise BrowserError(str(e)) from e
        self.url = final_url
        self.html = html_text
        self.snapshot = build_snapshot(html_text, base_url=final_url)
        self._values = {}
        return self.snapshot

    def _require_ref(self, ref):
        if self.snapshot is None:
            raise BrowserError("no page loaded yet; call goto() first")
        entry = self.snapshot.find_ref(ref)
        if entry is None:
            raise BrowserError(f"unknown ref {ref!r} (not in current snapshot)")
        return entry

    def click(self, ref):
        """Follow a link, or press a submit button (which submits its form)."""
        entry = self._require_ref(ref)
        role = entry["role"]
        if role == "link":
            href = entry["attrs"].get("href")
            if not href:
                raise BrowserError(f"ref {ref!r} is a link with no href")
            return self.goto(href)
        if role == "button":
            if entry["form"] is not None:
                return self.submit(ref)
            raise BrowserError(
                f"ref {ref!r} is a button with no enclosing form and no JS "
                "execution is supported (static-HTML trade-off)"
            )
        raise BrowserError(f"ref {ref!r} has role {role!r}, not clickable")

    def type(self, ref, text):
        """Set the value of a textbox/checkbox/radio/combobox ref for the next submit()."""
        entry = self._require_ref(ref)
        if entry["role"] not in ("textbox", "checkbox", "radio", "combobox"):
            raise BrowserError(f"ref {ref!r} has role {entry['role']!r}, cannot type into it")
        self._values[ref] = text
        return entry

    def submit(self, ref):
        """Submit the form containing `ref` (a field or its submit button)."""
        entry = self._require_ref(ref)
        form_ctx = entry["form"]
        if form_ctx is None:
            raise BrowserError(f"ref {ref!r} is not inside a <form>")
        if form_ctx["method"] != "get":
            raise BrowserError(
                f"form method={form_ctx['method']!r} not supported "
                "(barebrowse only performs GET requests)"
            )

        params = []
        for field_ref in form_ctx["fields"]:
            field = self.snapshot.find_ref(field_ref)
            attrs = field["attrs"]
            name = attrs.get("name")
            if not name:
                continue
            if field["role"] in ("checkbox", "radio"):
                if field_ref in self._values:
                    checked = bool(self._values[field_ref])
                else:
                    checked = "checked" in attrs
                if not checked:
                    continue
                value = attrs.get("value", "on")
            else:
                value = self._values.get(field_ref, attrs.get("value", ""))
            params.append((name, value))

        action = form_ctx["action"] or self.url
        target = urllib.parse.urljoin(self.url, action)
        query = urllib.parse.urlencode(params)
        if query:
            sep = "&" if urllib.parse.urlparse(target).query else "?"
            target = f"{target}{sep}{query}"
        return self.goto(target)
