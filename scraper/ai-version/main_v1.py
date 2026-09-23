"""
AI-generated scraper for books.toscrape.com — generated from PROMPT_v1.md only,
quarantined here per the bonus "AI vs me" exercise. Do not import from ../src/.
"""

import datetime
import json
import os
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, ValidationError

BASE_URL = "https://books.toscrape.com/"
MAX_PAGES = 3
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
USER_AGENT = "BooksScraperBot/1.0"
TIMEOUT = 10
DELAY = 0.5


def fetch(url, cache_name):
    path = os.path.join(CACHE_DIR, cache_name)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            print(f"CACHE HIT {cache_name}")
            return f.read()

    os.makedirs(CACHE_DIR, exist_ok=True)
    for attempt in range(2):
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        # Retry on any non-200 — the prompt just said "handle failures
        # gracefully," so any failure looked like something worth a retry.
        if resp.status_code == 200:
            with open(path, "w", encoding="utf-8") as f:
                f.write(resp.text)
            print(f"FETCH {cache_name} status={resp.status_code}")
            time.sleep(DELAY)
            return resp.text
        print(f"retrying {cache_name} (status {resp.status_code}, attempt {attempt + 1})")
        time.sleep(DELAY)

    print(f"giving up on {cache_name}")
    return None


def discover_books():
    book_urls = []
    page_url = BASE_URL
    for page_num in range(1, MAX_PAGES + 1):
        html = fetch(page_url, f"catalogue-page-{page_num}.html")
        if html is None:
            break
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select("article.product_pod h3 a"):
            book_urls.append(urljoin(page_url, a["href"]))
        next_a = soup.select_one("li.next a")
        if not next_a:
            break
        page_url = urljoin(page_url, next_a["href"])
    return book_urls


def extract(url):
    slug = url.rstrip("/").split("/")[-2]
    html = fetch(url, f"detail-{slug}.html")
    if html is None:
        return None
    soup = BeautifulSoup(html, "html.parser")

    title = soup.find("h1").get_text(strip=True)
    price_text = soup.select_one(".price_color").get_text(strip=True)
    availability_text = soup.select_one(".availability").get_text(strip=True)

    rating_tag = soup.select_one(".star-rating")
    # bs4 already gives back a *list* of classes for a multi-valued
    # attribute — calling .split() on that list is a plain string method
    # being called on the wrong type, and blows up with an AttributeError.
    rating_text = rating_tag["class"].split()[-1]

    desc_header = soup.select_one("#product_description")
    desc_tag = desc_header.find_next_sibling("p") if desc_header else None
    description = desc_tag.get_text(strip=True) if desc_tag else None

    return {
        "title": title,
        "product_url": url,
        "price_text": price_text,
        "availability_text": availability_text,
        "rating_text": rating_text,
        "description": description,
        "source_page": BASE_URL,
        "fetched_at": datetime.datetime.utcnow().isoformat() + "Z",
    }


class BookRecord(BaseModel):
    title: str
    product_url: str
    price_text: str
    price_gbp: float
    availability_text: str
    rating_text: str
    description: str | None = None
    source_page: str
    fetched_at: str


def parse_price(price_text):
    m = re.search(r"£([0-9.]+)", price_text)
    return float(m.group(1)) if m else None


def save_books(records):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, "books.json")
    # Appends to whatever is already on disk from a previous run, rather
    # than replacing it — so a second run doubles the file instead of
    # reproducing the same 60 records.
    existing = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            existing = json.load(f)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing + records, f, indent=2)


def main():
    book_urls = discover_books()
    print(f"found {len(book_urls)} books")

    valid = []
    errors = []
    for url in book_urls:
        try:
            raw = extract(url)
            if raw is None:
                errors.append({"url": url, "reason": "fetch failed"})
                continue
            price_gbp = parse_price(raw["price_text"])
            record = BookRecord(**{**raw, "price_gbp": price_gbp})
            valid.append(record.model_dump())
        except (ValidationError, AttributeError, TypeError) as exc:
            errors.append({"url": url, "reason": str(exc)})

    save_books(valid)
    print(f"valid={len(valid)} errors={len(errors)}")
    for e in errors[:5]:
        print("ERROR:", e)


if __name__ == "__main__":
    main()
