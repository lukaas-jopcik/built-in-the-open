"""Stdlib-only HTTP GET with encoding detection, timeout, and redirect handling."""
import gzip
import re
import urllib.error
import urllib.request
import zlib

USER_AGENT = "barebrowse/0.1 (+stdlib urllib; educational agent demo)"

_CHARSET_RE = re.compile(rb'charset=["\']?([\w-]+)', re.I)


class FetchError(Exception):
    pass


def _decompress(raw, content_encoding):
    """Some servers/CDNs send Content-Encoding: gzip/deflate even without a
    matching Accept-Encoding request header -- decompress or the bytes come
    out as binary garbage (silently "fine" to urllib, unusable to us)."""
    encoding = (content_encoding or "").lower()
    if "gzip" in encoding or "x-gzip" in encoding:
        return gzip.decompress(raw)
    if "deflate" in encoding:
        try:
            return zlib.decompress(raw)
        except zlib.error:
            return zlib.decompress(raw, -zlib.MAX_WBITS)  # raw deflate, no zlib header
    return raw


def fetch(url, timeout=10):
    """GET url, return (final_url, html_text). Raises FetchError on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            final_url = resp.geturl()
            content_type = resp.headers.get("Content-Type", "")
            content_encoding = resp.headers.get("Content-Encoding", "")
    except urllib.error.HTTPError as e:
        raise FetchError(f"HTTP {e.code} for {url}") from e
    except urllib.error.URLError as e:
        raise FetchError(f"connection error for {url}: {e.reason}") from e
    except TimeoutError as e:
        raise FetchError(f"timeout fetching {url}") from e

    try:
        raw = _decompress(raw, content_encoding)
    except OSError as e:
        raise FetchError(f"failed to decompress ({content_encoding}) response from {url}: {e}") from e

    encoding = None
    m = _CHARSET_RE.search(content_type.encode())
    if m:
        encoding = m.group(1).decode()
    else:
        m2 = _CHARSET_RE.search(raw[:2048])
        if m2:
            encoding = m2.group(1).decode()
    if not encoding:
        encoding = "utf-8"

    try:
        text = raw.decode(encoding, errors="replace")
    except (LookupError, UnicodeDecodeError):
        text = raw.decode("utf-8", errors="replace")

    return final_url, text
