"""Zero-dependency page fetch + metrics extraction (stdlib only)."""
import gzip
import urllib.request
import urllib.error
import zlib
from html.parser import HTMLParser

USER_AGENT = "minicrawl/0.1 (+stdlib-only dashboard demo)"


class _MetricsExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self._in_title = False
        self.links = []
        self.images = []
        self._text_parts = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        elif tag == "img" and attrs.get("src"):
            self.images.append(attrs["src"])
        elif tag in ("script", "style"):
            self._skip_depth += 1

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag in ("script", "style") and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._skip_depth == 0:
            self._text_parts.append(data)

    @property
    def text(self):
        return " ".join(self._text_parts)


def fetch(url, timeout=10):
    """GET url, parse HTML, return a metrics dict. Raises on network/HTTP error."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        status = resp.status
        content_type = resp.headers.get("Content-Type", "")
        content_encoding = (resp.headers.get("Content-Encoding") or "").lower()

    # Some CDNs (e.g. python.org's fastly/varnish front end) send a gzipped body
    # even when the request sent no Accept-Encoding header, so always check for it.
    if content_encoding == "gzip":
        raw = gzip.decompress(raw)
    elif content_encoding == "deflate":
        raw = zlib.decompress(raw)

    if "html" not in content_type and content_type:
        return {
            "url": url,
            "status": status,
            "skipped": f"non-html content-type: {content_type}",
        }

    html_text = raw.decode("utf-8", errors="replace")
    parser = _MetricsExtractor()
    parser.feed(html_text)
    words = parser.text.split()

    return {
        "url": url,
        "status": status,
        "title": parser.title.strip(),
        "word_count": len(words),
        "link_count": len(parser.links),
        "image_count": len(parser.images),
        "links": sorted(set(parser.links)),
        "bytes": len(raw),
    }
