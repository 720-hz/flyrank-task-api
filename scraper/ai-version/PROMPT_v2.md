Write a Python scraper for https://books.toscrape.com. It's a public sandbox site
built for practicing scraping, so it's fine to scrape.

Scope: the first 3 catalogue pages only (not the whole site — it has way more than
that). Each catalogue page links to about 20 books, so ~60 books total.

For every book, collect:
- title
- product_url (absolute, not the relative link on the page)
- price_text (the raw "£51.77" string)
- availability_text (the raw in-stock string)
- rating_text (the star rating, as a word like "Three")
- description (the paragraph under "Product Description" — some books might not
  have one)
- source_page (which catalogue page it came from)
- fetched_at (a timestamp)

Then clean it up:
- Turn price_text into a real number, price_gbp.
- Validate every record against a schema (use Pydantic) before saving it. Bad
  records shouldn't crash the whole thing — set them aside instead.
- Save the good records to books.json, **overwriting the file each run** — don't
  read back and append to whatever's already on disk. Running the script twice
  should leave the file with the same ~60 records, never double.

Be polite about it:
- Send a custom User-Agent so the site can tell who's requesting.
- Cache pages to disk so you're not hammering the site every time you re-run the
  script while developing.
- Don't go too fast — put a small delay between requests.
- Use a timeout so a hung request doesn't hang the whole script forever.
- **Only retry a timeout or a 5xx status, once.** A 404 or 403 should never be
  retried — the page is either genuinely gone or the site said no, and asking
  again wastes a request without changing the outcome.

Handle failures gracefully — if one book page is broken or missing, log it and
move on, don't let it kill the whole run. At the end, print/save a short report:
how many pages you fetched, how many came from cache, how many valid records, how
many failed.

One more thing: BeautifulSoup already returns a multi-valued HTML attribute (like
`class`) as a Python **list**, not a string — so pull the rating word out of that
list directly (e.g. by filtering out the base "star-rating" class), don't call
string methods like `.split()` on it.

Use Python, requests + BeautifulSoup, one script is fine.
