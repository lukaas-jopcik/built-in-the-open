[← all experiments](../../)

# MiniCrawl

*Fetched 5 real websites, counted 2,162 words and 274 links, and rebuilt a live dashboard — in 0.667 seconds, for $0.*

## The wave

Scraping-as-a-service APIs like Firecrawl are becoming the default way agents touch the web, but every call costs money and a key. We wanted to know how far a zero-dependency, stdlib-only Python script could get toward the same job — fetch, extract, diff, visualize — without an API, a browser, or a bill.

## The build

- `crawl.py`: fetches a seed list of URLs with `urllib.request`, parses HTML with stdlib `html.parser`, snapshots results to JSON.
- `lib/diff.py`: compares consecutive snapshots per site — added/removed links, word-count delta, title changes.
- `lib/dashboard.py`: renders a single self-contained `dashboard.html` with count-up stat cards, green/red diff rows, per-site health badges, and a "biggest mover" callout.
- `lib/health.py`: scores each site's reliability over its last N runs.
- Tested against 5 real public sites (not fixtures only): `example.com`, `info.cern.ch`, `httpbin.org/html`, `iana.org`, `python.org`.
- 24 automated tests (fetcher, diff, dashboard, health, end-to-end subprocess run).
- Caught one real bug along the way: python.org serves gzip-encoded HTML, which the first version didn't decode.

## The numbers

- **24/24** tests passing in **1.226s**.
- **5/5** real sites fetched successfully in **0.667s** wall-clock.
- **2,162** total words and **274** total links aggregated across the 5 tracked sites.
- **0** changes detected on a same-day re-run (correctly found no drift).
- **75%** health score surfaced for `httpbin.org` — a real historical fetch failure, not synthetic.
- Caveat: all 5 test sites are simple, cooperative, non-JS pages — no JS rendering, no crawling past the seed URL, no proxy/anti-bot handling.
- Caveat: no rate limiting or `robots.txt` respect, and no confirmed brotli-decoding support (untested gap, only gzip/deflate were exercised).
- Caveat: no quantified head-to-head comparison against a real Firecrawl run exists.

## Run it

```
git clone <this-repo> && cd minicrawl
python3 crawl.py
open dashboard.html
python3 -m unittest discover -s tests -v
```

## Verdict

Worked. It fetches, diffs, and dashboards real sites correctly, for free, in under a second. It is not a Firecrawl replacement — no JavaScript rendering, no multi-page crawling, no politeness controls — and we're saying that plainly rather than burying it.

## Post

_link added when the LinkedIn post is live_

---

**Cost:** $5.91 across 14 Claude run(s) — see `cost.json`.

<sub>Part of [built in the open](../../) — real experiments, real numbers · by [Lukáš Jopčík](https://www.linkedin.com/in/luk%C3%A1%C5%A1-jop%C4%8D%C3%ADk-087064223/)</sub>
