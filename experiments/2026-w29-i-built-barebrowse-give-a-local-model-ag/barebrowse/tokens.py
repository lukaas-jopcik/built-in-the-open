"""Shared token-count estimator so raw-HTML and snapshot text are compared apples-to-apples."""
import re

_TOKEN_RE = re.compile(r"\w+|[^\w\s]")


def estimate_tokens(text):
    """Rough token count: word runs and individual punctuation/symbol chars.

    Not a real BPE tokenizer, but stable and cheap, and applied identically to
    raw HTML and pruned snapshots so the *ratio* between them is meaningful.
    """
    if not text:
        return 0
    return len(_TOKEN_RE.findall(text))
