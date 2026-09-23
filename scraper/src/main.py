"""
The polite scraper — FlyRank Internship, Week 5, Assignment A9.

Pipeline: fetch -> extract -> normalize -> validate -> store -> report.
Target: https://books.toscrape.com (see ../README.md for the target
classification and robots.txt result).
"""

import argparse
import datetime
import json
import os
import re
import sys
import time
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, ValidationError

BASE_URL = "https://books.toscrape.com/"

# The assignment's scope is the first 3 catalogue pages only, out of the
# site's real ~50 — not "however many pages the site happens to have."
MAX_CATALOGUE_PAGES = 3
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT_DIR, "cache")
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")

# An honest user-agent that names the bot and links back to the repo — a site
# owner who sees it in their logs can find out who's requesting their pages.
USER_AGENT = "FlyRankInternshipA9/1.0 (+https://github.com/720-hz/flyrank-task-api)"

REQUEST_TIMEOUT_SECONDS = 8
REQUEST_DELAY_SECONDS = 0.5  # politeness delay between real (non-cached) requests


def cache_path_for(cache_name: str) -> str:
    return os.path.join(CACHE_DIR, cache_name)


class FetchError(Exception):
    """One page's fetch failed for good — after a retry where a retry was
    warranted. Callers catch this per-page so one bad page never takes the
    whole run down."""

    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


def fetch_page(url: str, cache_name: str, stats: Optional[dict] = None, retries_left: int = 1) -> str:
    """
    Fetch a page's HTML, politely, with a cache-first read.

    - Reads from cache/<cache_name> if it already exists (development never
      re-asks the live site for something it already has on disk).
    - Otherwise makes one real HTTP GET with an identifying user-agent and a
      timeout, checks the status code, saves the raw HTML to cache, and
      waits REQUEST_DELAY_SECONDS before returning (so the *next* real
      request — not this one — respects the politeness delay).
    - A timeout or a 5xx is worth one retry after a short wait — the site
      may just be briefly overloaded. A 404 or 403 is not retried: the page
      either doesn't exist or the site said no, and asking again changes
      nothing except being a worse guest.
    - Raises FetchError on final failure — never crashes the caller.
    """
    path = cache_path_for(cache_name)

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
        print(f"CACHE HIT {cache_name} ({len(html)} bytes)")
        if stats is not None:
            stats["cache_hits"] += 1
        return html

    os.makedirs(CACHE_DIR, exist_ok=True)

    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.RequestException as exc:
        if retries_left > 0:
            print(f"RETRY {cache_name} after request error: {exc}")
            time.sleep(REQUEST_DELAY_SECONDS)
            return fetch_page(url, cache_name, stats=stats, retries_left=retries_left - 1)
        raise FetchError(f"{cache_name}: request failed after retry: {exc}")

    if response.status_code == 200:
        html = response.text
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"FETCH {cache_name} ({len(html)} bytes, status 200)")
        if stats is not None:
            stats["pages_fetched"] += 1
        time.sleep(REQUEST_DELAY_SECONDS)
        return html

    if response.status_code in (404, 403):
        # Not retryable: the page is genuinely gone, or the site declined —
        # retrying either one is how a polite robot becomes a pest.
        print(f"FAIL {cache_name}: status {response.status_code} (not retrying)")
        raise FetchError(f"{cache_name}: status {response.status_code}", status=response.status_code)

    if response.status_code >= 500 and retries_left > 0:
        print(f"RETRY {cache_name} after status {response.status_code}")
        time.sleep(REQUEST_DELAY_SECONDS)
        return fetch_page(url, cache_name, stats=stats, retries_left=retries_left - 1)

    print(f"FAIL {cache_name}: status {response.status_code}")
    raise FetchError(f"{cache_name}: status {response.status_code}", status=response.status_code)


def discover_catalogue_pages(stats: Optional[dict] = None):
    """
    Walk the catalogue from page 1, following the site's own "next" link —
    never a hardcoded page-2.html/page-3.html guess — and stop once
    MAX_CATALOGUE_PAGES have been visited (this assignment's scope is the
    first 3 pages, not the site's real ~50). Returns
    (list_of_catalogue_page_urls, list_of_unique_absolute_book_urls,
    dict_of_book_url_to_its_source_catalogue_page).
    """
    page_urls = []
    book_urls = []
    seen_books = set()
    source_page_by_book_url = {}

    page_url = BASE_URL
    page_number = 1

    while page_url and page_number <= MAX_CATALOGUE_PAGES:
        cache_name = f"catalogue-page-{page_number}.html"
        html = fetch_page(page_url, cache_name, stats=stats)
        page_urls.append(page_url)
        soup = BeautifulSoup(html, "html.parser")

        # The product area only — each book is an <article class="product_pod">
        # with its title link inside an <h3>. Aiming here (not "every <a> on
        # the page") avoids picking up nav/footer links by accident.
        for article in soup.select("article.product_pod"):
            link = article.select_one("h3 a")
            if link is None or not link.get("href"):
                continue
            absolute_url = urljoin(page_url, link["href"])
            if absolute_url not in seen_books:
                seen_books.add(absolute_url)
                book_urls.append(absolute_url)
                source_page_by_book_url[absolute_url] = page_url

        next_link = soup.select_one("li.next a")
        page_url = urljoin(page_url, next_link["href"]) if next_link else None
        page_number += 1

    return page_urls, book_urls, source_page_by_book_url


def detail_cache_name(book_url: str) -> str:
    # https://books.toscrape.com/catalogue/<slug>/index.html -> detail-<slug>.html
    slug = book_url.rstrip("/").split("/")[-2]
    return f"detail-{slug}.html"


def fetched_at_for(cache_name: str) -> str:
    """
    Provenance timestamp: when this page's cached copy was actually written
    to disk, as UTC ISO-8601. That is the real fetch time for this record —
    not "now," which would drift every time the pipeline re-runs from cache.
    """
    path = cache_path_for(cache_name)
    mtime = os.path.getmtime(path)
    return (
        datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def extract_record(book_url: str, source_page: str, stats: Optional[dict] = None) -> dict:
    """
    Pull the 8 raw fields from one book's detail page. Selectors are aimed
    at the product area (article.product_page / div.product_main), not "the
    first thing on the page that looks like a price" — a page that later
    grows a second price elsewhere shouldn't silently break this.

    Raises FetchError (propagated from fetch_page) if the page can't be
    fetched at all — the caller is responsible for catching that per-book,
    so one broken page doesn't take the other 59 down with it.
    """
    cache_name = detail_cache_name(book_url)
    html = fetch_page(book_url, cache_name, stats=stats)
    soup = BeautifulSoup(html, "html.parser")

    product = soup.select_one("article.product_page")

    title = product.select_one(".product_main h1").get_text(strip=True)
    price_text = product.select_one(".product_main .price_color").get_text(strip=True)
    availability_text = product.select_one(
        ".product_main .availability"
    ).get_text(strip=True)

    rating_tag = product.select_one(".product_main .star-rating")
    rating_classes = rating_tag.get("class", []) if rating_tag else []
    # classes are ["star-rating", "<Rating>"] — the rating word is whichever
    # class isn't the literal "star-rating" marker.
    rating_text = next((c for c in rating_classes if c != "star-rating"), None)

    description_header = product.select_one("#product_description")
    description_tag = (
        description_header.find_next_sibling("p") if description_header else None
    )
    # Some books genuinely have no description section at all — store null,
    # never invent text that was never on the page.
    description = description_tag.get_text(strip=True) if description_tag else None

    return {
        "title": title,
        "product_url": book_url,
        "price_text": price_text,
        "availability_text": availability_text,
        "rating_text": rating_text,
        "description": description,
        "source_page": source_page,
        "fetched_at": fetched_at_for(cache_name),
    }


PRICE_PATTERN = re.compile(r"£\s*([0-9]+(?:\.[0-9]+)?)")


def parse_price_gbp(price_text: str) -> float:
    """"£51.77" -> 51.77. Raises ValueError on anything that isn't a plain
    GBP amount — that failure is caught by the caller and turned into an
    errors.json entry, not a crash."""
    match = PRICE_PATTERN.search(price_text)
    if not match:
        raise ValueError(f"unparseable price_text: {price_text!r}")
    return float(match.group(1))


class BookRecord(BaseModel):
    """
    The shape of a finished, storable record. product_url doubles as the
    record's canonical identity (see store_records). Every field but
    description is required; description is the one field the source pages
    are allowed to genuinely not have.
    """

    title: str = Field(min_length=1)
    product_url: str = Field(min_length=1)
    price_text: str = Field(min_length=1)
    price_gbp: float = Field(gt=0)
    availability_text: str = Field(min_length=1)
    rating_text: str = Field(min_length=1)
    description: Optional[str] = None
    source_page: str = Field(min_length=1)
    fetched_at: str = Field(min_length=1)


def normalize_and_validate(raw_records: list) -> tuple:
    """
    Turn each raw record into its clean, schema-checked form. A record that
    fails — a bad price, a missing field — goes to the errors list with the
    reason attached; it never reaches the valid list. Returns
    (valid_records, error_entries).
    """
    valid_records = []
    error_entries = []

    for raw in raw_records:
        try:
            price_gbp = parse_price_gbp(raw["price_text"])
            candidate = {**raw, "price_gbp": price_gbp}
            record = BookRecord.model_validate(candidate)
            valid_records.append(record.model_dump())
        except (ValueError, ValidationError) as exc:
            error_entries.append(
                {
                    "product_url": raw.get("product_url"),
                    "reason": str(exc),
                }
            )

    return valid_records, error_entries


def store_records(valid_records: list) -> list:
    """
    Write the good records to output/books.json, keyed by canonical URL so a
    record appearing twice counts once. This function always writes the full
    current set (never appends), which is what makes a rerun idempotent —
    60 records in, 60 records out, never 120.
    """
    by_canonical_url = {}
    for record in valid_records:
        by_canonical_url[record["product_url"]] = record

    unique_records = list(by_canonical_url.values())

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    books_path = os.path.join(OUTPUT_DIR, "books.json")
    with open(books_path, "w", encoding="utf-8") as f:
        json.dump(unique_records, f, indent=2, ensure_ascii=False)

    return unique_records


def store_errors(error_entries: list):
    errors_path = os.path.join(OUTPUT_DIR, "errors.json")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(errors_path, "w", encoding="utf-8") as f:
        json.dump(error_entries, f, indent=2, ensure_ascii=False)


def store_run_report(report: dict):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    report_path = os.path.join(OUTPUT_DIR, "run-report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def run(extra_book_urls: Optional[list] = None) -> dict:
    """
    Run the full pipeline once: fetch -> extract -> normalize -> validate ->
    store -> report. extra_book_urls exists only so Stage 5's checkpoint can
    inject one deliberately-broken URL on purpose (see --inject-fake-url) —
    the default run never adds anything that wasn't discovered for real.
    """
    start = datetime.datetime.now(tz=datetime.timezone.utc)
    stats = {"pages_fetched": 0, "cache_hits": 0}

    catalogue_pages, book_urls, source_page_by_book_url = discover_catalogue_pages(stats=stats)
    print(
        f"catalogue_pages={len(catalogue_pages)} "
        f"discovered={len(book_urls)} unique_urls={len(set(book_urls))}"
    )

    if extra_book_urls:
        for fake_url in extra_book_urls:
            book_urls.append(fake_url)
            source_page_by_book_url[fake_url] = "manual-test-injection"

    raw_records = []
    failed_pages = []
    for book_url in book_urls:
        try:
            record = extract_record(book_url, source_page_by_book_url[book_url], stats=stats)
            raw_records.append(record)
        except FetchError as exc:
            # Handled per-page, on purpose: one broken page is logged and
            # skipped here, not left to crash the other 59.
            print(f"SKIP {book_url}: {exc}")
            failed_pages.append({"url": book_url, "reason": str(exc)})
    print(f"detail_pages={len(raw_records)} failed_pages={len(failed_pages)}")

    valid_records, error_entries = normalize_and_validate(raw_records)
    stored_records = store_records(valid_records)
    store_errors(error_entries)

    all_gbp_numeric = all(isinstance(r["price_gbp"], float) for r in stored_records)
    all_https = all(r["product_url"].startswith("https://") for r in stored_records)
    print(
        f"books.json={len(stored_records)} errors.json={len(error_entries)} "
        f"all_price_gbp_numeric={all_gbp_numeric} all_urls_https={all_https}"
    )

    finished = datetime.datetime.now(tz=datetime.timezone.utc)
    report = {
        "start_time": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_seconds": round((finished - start).total_seconds(), 3),
        "pages_fetched": stats["pages_fetched"],
        "cache_hits": stats["cache_hits"],
        "valid_records": len(stored_records),
        "invalid_records": len(error_entries),
        "failed_pages": len(failed_pages),
        "failed_page_details": failed_pages,
    }
    store_run_report(report)
    print(
        f"run_report: pages_fetched={report['pages_fetched']} "
        f"cache_hits={report['cache_hits']} valid_records={report['valid_records']} "
        f"invalid_records={report['invalid_records']} failed_pages={report['failed_pages']} "
        f"duration_seconds={report['duration_seconds']}"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description="The polite scraper (books.toscrape.com)")
    parser.add_argument(
        "--inject-fake-url",
        dest="inject_fake_url",
        default=None,
        help=(
            "Stage 5 proof only: add one made-up book URL to the run on "
            "purpose, to show a broken page is logged and skipped instead "
            "of crashing the run."
        ),
    )
    args = parser.parse_args()

    extra = [args.inject_fake_url] if args.inject_fake_url else None
    run(extra_book_urls=extra)


if __name__ == "__main__":
    main()
