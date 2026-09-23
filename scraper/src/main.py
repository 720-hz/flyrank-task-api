"""
The polite scraper — FlyRank Internship, Week 5, Assignment A9.

Pipeline: fetch -> extract -> normalize -> validate -> store -> report.
Target: https://books.toscrape.com (see ../README.md for the target
classification and robots.txt result).
"""

import datetime
import json
import os
import re
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


def fetch_page(url: str, cache_name: str) -> str:
    """
    Fetch a page's HTML, politely, with a cache-first read.

    - Reads from cache/<cache_name> if it already exists (development never
      re-asks the live site for something it already has on disk).
    - Otherwise makes one real HTTP GET with an identifying user-agent and a
      timeout, checks the status code, saves the raw HTML to cache, and
      waits REQUEST_DELAY_SECONDS before returning (so the *next* real
      request — not this one — respects the politeness delay).
    - Raises for any non-200 status: a failed fetch is not HTML to parse.
    """
    path = cache_path_for(cache_name)

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
        print(f"CACHE HIT {cache_name} ({len(html)} bytes)")
        return html

    os.makedirs(CACHE_DIR, exist_ok=True)
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    if response.status_code != 200:
        raise RuntimeError(f"FETCH FAILED {url} -> status {response.status_code}")

    html = response.text
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"FETCH {cache_name} ({len(html)} bytes, status {response.status_code})")
    time.sleep(REQUEST_DELAY_SECONDS)
    return html


def discover_catalogue_pages():
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
        html = fetch_page(page_url, cache_name)
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


def extract_record(book_url: str, source_page: str) -> dict:
    """
    Pull the 8 raw fields from one book's detail page. Selectors are aimed
    at the product area (article.product_page / div.product_main), not "the
    first thing on the page that looks like a price" — a page that later
    grows a second price elsewhere shouldn't silently break this.
    """
    cache_name = detail_cache_name(book_url)
    html = fetch_page(book_url, cache_name)
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


def main():
    catalogue_pages, book_urls, source_page_by_book_url = discover_catalogue_pages()
    print(
        f"catalogue_pages={len(catalogue_pages)} "
        f"discovered={len(book_urls)} unique_urls={len(set(book_urls))}"
    )

    raw_records = []
    for book_url in book_urls:
        record = extract_record(book_url, source_page_by_book_url[book_url])
        raw_records.append(record)
    print(f"detail_pages={len(raw_records)}")

    valid_records, error_entries = normalize_and_validate(raw_records)
    stored_records = store_records(valid_records)
    store_errors(error_entries)

    all_gbp_numeric = all(isinstance(r["price_gbp"], float) for r in stored_records)
    all_https = all(r["product_url"].startswith("https://") for r in stored_records)
    print(
        f"books.json={len(stored_records)} errors.json={len(error_entries)} "
        f"all_price_gbp_numeric={all_gbp_numeric} all_urls_https={all_https}"
    )


if __name__ == "__main__":
    main()
