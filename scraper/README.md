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

