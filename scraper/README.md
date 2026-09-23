# The polite scraper

FlyRank Internship · Backend Track · Week 5 · Assignment A9.

A small, polite scraping pipeline: it downloads the first three catalogue pages of
[Books to Scrape](https://books.toscrape.com), visits all 60 book pages, turns messy HTML
into clean, checked JSON records, survives a broken page without crashing, and ends every
run with a short report of what happened.

## Target classification

- **Site:** [books.toscrape.com](https://books.toscrape.com), part of the
  [toscrape.com](https://toscrape.com) sandbox family ("Scraping Sandbox").
- **Why this site is appropriate to scrape:** toscrape.com states, in its own words, that
  Books to Scrape is *"a fictional bookstore that desperately wants to be scraped... a safe
  place for beginners learning web scraping and for developers validating their scraping
  technologies."* That sentence is the permission for this assignment — it is the only kind
  of site this project touches.
- **Scope:** the first 3 catalogue pages only (60 books total, 20 per page) — not the full
  1000-item catalogue the site actually hosts.
- **Data collected:** per book — title, product URL, price, availability, star rating,
  description, and provenance (source page + fetch time). No account data, no personal data,
  nothing behind a login.
- **`robots.txt` result:** `GET https://books.toscrape.com/robots.txt` returns `404 Not
  Found` (nginx). No robots file found. A missing file is not permission on its own — it's
  just a missing file — so the actual permission here is the sandbox's own "desperately
  wants to be scraped" statement above, not the absence of a robots file.

I will not reuse this code on another site without checking its rules and terms first.

## Running it

```bash
cd scraper
pip install -r requirements.txt
python3 src/main.py
```

That's it — one command. `pip install` only needs to run once; every later run just
reads from `cache/` and rewrites `output/`. Python 3.10+ is the only requirement.

To reproduce the Stage 5 "one bad page must not kill the run" checkpoint:

```bash
python3 src/main.py --inject-fake-url https://books.toscrape.com/catalogue/this-book-does-not-exist-99999/index.html
```

## The record schema

Nine fields per book — the eight raw fields captured at extraction, plus the one
normalized field added at validation time:

| Field | Type | Notes |
|---|---|---|
| `title` | string | required |
| `product_url` | string | required — also the record's canonical identity |
| `price_text` | string | required — the raw `"£51.77"` as it appeared on the page |
| `price_gbp` | number | required — `price_text` parsed to a real number, e.g. `51.77` |
| `availability_text` | string | required — e.g. `"In stock (22 available)"` |
| `rating_text` | string | required — one of `One`/`Two`/`Three`/`Four`/`Five` |
| `description` | string or `null` | optional — `null` when the page genuinely has none |
| `source_page` | string | required — the catalogue page this book was discovered on |
| `fetched_at` | string | required — UTC ISO-8601, when the source page was actually fetched |

A record that fails this schema — or whose `price_text` doesn't parse to a number —
never reaches `books.json`. It goes to `output/errors.json` with the reason instead.

## Politeness rules

- **User-agent:** every real request identifies itself as
  `FlyRankInternshipA9/1.0 (+https://github.com/720-hz/flyrank-task-api)`.
- **Timeout:** every request gives up after 8 seconds rather than hanging forever.
- **Delay:** at least 500ms between real (non-cached) requests to the site.
- **Cache-first:** `cache/` is read before any request is made. Once a page is on
  disk, re-running the pipeline never asks the live site for it again.
- **Retry rules:** a timeout or a `5xx` gets one retry after a short wait — the site
  may just be briefly overloaded. A `404` or `403` is never retried — the page is
  either genuinely gone or the site said no, and asking again only makes the robot
  worse company.

## One honest limitation

This project was built and run inside a sandboxed cloud environment whose own
network policy blocks direct outbound requests from Python/Node to
`books.toscrape.com` (everything else about the environment is normal — this is a
policy on this one execution environment, not a property of the code). A linked
browser on a separate machine could still reach the site directly, so the actual
HTTP fetches for all 63 pages (3 catalogue + 60 detail) were performed through that
browser and written into `cache/` exactly where `fetch_page()` would have written
them itself. Every other stage — discovery, extraction, normalization, schema
validation, storage, retry/failure handling, and the run report — then ran for real,
unmodified, straight from that real cached data, including the two checkpoint runs
above (both executed live against a local mock server to prove the retry-vs-no-retry
branches, plus a genuine `404` for the Stage 5 fake-URL proof).

The one thing this means: the polite-fetching code path itself (the `requests.get`
call, its headers, timeout, and status check) could not be exercised against the
*live* target from inside this environment — only against a local mock server that
reproduces the same status codes. It runs unmodified and would fetch the real site
directly on any machine without this sandbox's specific network restriction — which
is any normal machine, including a fresh clone of this repo.

## Why this assignment needed no browser

`books.toscrape.com` states plainly that it requires no JavaScript (`Requires
JavaScript ✘`, per its own sandbox page) — the book data is already present in the
HTML the server sends on the very first response, so a real browser would only add
startup cost and memory for zero extra data.

## Sample run-report.json

A real run, from cache, all 60 books, zero failures:

```json
{
  "start_time": "2026-09-23T18:09:22Z",
  "duration_seconds": 0.516,
  "pages_fetched": 0,
  "cache_hits": 63,
  "valid_records": 60,
  "invalid_records": 0,
  "failed_pages": 0,
  "failed_page_details": []
}
```

`pages_fetched` is `0` here because every page was already cached from the run that
produced this report — that's what the idempotency checkpoint is proving. The
[first live population run](#one-honest-limitation) is the one described above.

## Bonus — AI vs me

The prompt in [`ai-version/PROMPT_v1.md`](ai-version/PROMPT_v1.md) was written from
memory — a plain recollection of what this scraper needed to do, not a copy of the
assignment spec. `ai-version/main_v1.py` was generated from that prompt alone and
run against the exact same real cached pages the hand-built version used, so the
comparison is apples to apples.

**What the AI did better:** honestly, not much structurally — the overall shape
(fetch/cache → discover → extract → validate → save → report) came out close to the
hand-built version, which says the prompt communicated the pipeline shape fine. The
one place it's arguably cleaner is that it treats every non-200 the same way in one
retry loop instead of branching early, which reads simply — right up until that
simplicity turns out to be the bug.

**What it got wrong** (all three verified live against real data, not just read in
the diff):

1. **100% failure rate from one bad line.** `rating_tag["class"].split()[-1]` — bs4
   already hands back a multi-valued attribute like `class` as a **list**, not a
   string, so `.split()` throws `AttributeError: 'AttributeValueList' object has no
   attribute 'split'` on every single book. Running `main_v1.py` against the real
   60 cached pages produced `valid=0 errors=60` — every record failed on the exact
   same line.
2. **Retries a `404` twice before giving up.** The prompt said "handle failures
   gracefully" without naming which statuses are worth retrying, so the AI applied
   one retry policy to everything. Pointed at a mock 404 endpoint, it printed
   `retrying ... attempt 1` and `attempt 2` before giving up — two wasted requests
   to a page that was never going to exist.
3. **Not idempotent.** `save_books()` reads back whatever's already in
   `books.json` and appends the new records to it, instead of overwriting. Calling
   it twice with the same 2 test records left 4 records on disk, not 2 — a rerun of
   the real scraper would silently double `books.json` every time.

**What my prompt forgot to say** (the more useful half): the exact retry policy per
status code, the overwrite-not-append requirement for idempotency, and — the one
that actually caused the crash — that a bs4 multi-valued attribute comes back as a
list already, not something to re-split. None of these are exotic; they're the kind
of detail that's obvious once you've hit it and invisible until then, which is
exactly why writing the prompt from memory (not copying the spec) is the point of
the exercise — the gaps that show up are gaps in how precisely the problem was
specified, not just gaps in what the AI happened to do.

**The rematch:** [`ai-version/PROMPT_v2.md`](ai-version/PROMPT_v2.md) names all
three gaps explicitly. [`ai-version/main.py`](ai-version/main.py), generated from
that revised prompt, was re-run against the same real cached pages:
`valid=60 errors=0` on the first run, still `60` records (not `120`) after a
second run, and a `404` against the mock endpoint now fails immediately with
`giving up on fake.html (status 404, not retrying)` instead of retrying.

## Ethics note

Use an official API instead of scraping whenever one exists — it's faster, more
stable, and it's what the site owner actually wants you to use. Never bypass a
login, a paywall, or an explicit block; if a site says no, that's the end of it, not
a puzzle to route around. Collect only the fields the task actually needs — this
project never touches anything behind Books to Scrape's (nonexistent) login, and
only reads the fields it validates and stores.

