"""
The polite scraper — FlyRank Internship, Week 5, Assignment A9.

Pipeline: fetch -> extract -> normalize -> validate -> store -> report.
Target: https://books.toscrape.com (see ../README.md for the target
classification and robots.txt result).
"""

import os
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://books.toscrape.com/"

# The assignment's scope is the first 3 catalogue pages only, out of the
# site's real ~50 — not "however many pages the site happens to have."
MAX_CATALOGUE_PAGES = 3
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")

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
    (list_of_catalogue_page_urls, list_of_unique_absolute_book_urls).
    """
    page_urls = []
    book_urls = []
    seen_books = set()

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

        next_link = soup.select_one("li.next a")
        page_url = urljoin(page_url, next_link["href"]) if next_link else None
        page_number += 1

    return page_urls, book_urls


def main():
    catalogue_pages, book_urls = discover_catalogue_pages()
    print(
        f"catalogue_pages={len(catalogue_pages)} "
        f"discovered={len(book_urls)} unique_urls={len(set(book_urls))}"
    )


if __name__ == "__main__":
    main()
