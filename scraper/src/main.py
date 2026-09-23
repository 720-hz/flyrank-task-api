"""
The polite scraper — FlyRank Internship, Week 5, Assignment A9.

Pipeline: fetch -> extract -> normalize -> validate -> store -> report.
Target: https://books.toscrape.com (see ../README.md for the target
classification and robots.txt result).
"""

import os
import time

import requests

BASE_URL = "https://books.toscrape.com/"
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


def main():
    fetch_page(BASE_URL, "catalogue-page-1.html")


if __name__ == "__main__":
    main()
