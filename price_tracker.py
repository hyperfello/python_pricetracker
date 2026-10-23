
import json
import re
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import requests

from bs4 import BeautifulSoup

CONFIG = json.loads(Path("products.json").read_text(encoding="utf-8"))
DB_PATH = "prices.db"


def parse_price(text):
    """Convert a displayed price such as 'KSh 150,000' to Decimal."""
    match = re.search(r"KSh\s*([\d,]+(?:\.\d{1,2})?)", text, re.I)
    if not match:
        return None

    try:
        price = Decimal(match.group(1).replace(",", ""))
        return price if price > 0 else None
    except Exception:
        return None


def extract_products(html):
    """Extract matching products from a saved Jumia category-page HTML file."""
    soup = BeautifulSoup(html, "html.parser")
    keyword = CONFIG["product_keyword"].casefold()
    products = []

    # Jumia listing cards commonly use the .prd class.
    # Inspect the saved page if its markup has changed.
    for card in soup.select(".prd"):
        title_element = card.select_one(".name")
        price_element = card.select_one(".prc")
        link = card.select_one("a[href]")

        if not title_element or not price_element or not link:
            continue

        title = title_element.get_text(" ", strip=True)

        if keyword not in title.casefold():
            continue

        price = parse_price(price_element.get_text(" ", strip=True))
        if price is None:
            continue

        href = link.get("href", "")
        if href.startswith("/"):
            href = "https://www.jumia.co.ke" + href

        if not href.startswith("https://www.jumia.co.ke/"):
            continue

        products.append({
            "title": title,
            "url": href,
            "price": price,
        })

    return products


def initialize_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_url TEXT NOT NULL,
                title TEXT NOT NULL,
                price TEXT NOT NULL,
                checked_at TEXT NOT NULL
            )
        """)


def record_price(product):
    now = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DB_PATH) as db:
        row = db.execute("""
            SELECT price FROM price_history
            WHERE product_url = ?
            ORDER BY id DESC LIMIT 1
        """, (product["url"],)).fetchone()

        previous = Decimal(row[0]) if row else None

        db.execute("""
            INSERT INTO price_history
                (product_url, title, price, checked_at)
            VALUES (?, ?, ?, ?)
        """, (
            product["url"],
            product["title"],
            str(product["price"]),
            now,
        ))

    current = product["price"]
    print(f"\n{product['title']}")
    print(f"Current price: KSh {current:,.2f}")

    if previous is not None:
        change = current - previous

        if change < 0:
            print(f"PRICE DROP: KSh {-change:,.2f}")
        elif change > 0:
            print(f"Price increased: KSh {change:,.2f}")
        else:
            print("Price unchanged.")

    target = Decimal(str(CONFIG["target_price_ksh"]))
    if current <= target:
        print(f"TARGET REACHED: KSh {target:,.2f} or less")
def fetch_page(url):
    """Fetch a webpage and return its HTML."""
    try:
        response = requests.get(
            url,
            timeout=15,
            headers={"User-Agent": "PriceTrackerLearningProject/1.0"}
        )
        response.raise_for_status()
        print("Webpage fetched successfully!")
        return response.text

    except requests.RequestException as error:
        print(f"Could not fetch webpage: {error}")
        return None

def main():
    initialize_db()

    # Use a page saved from your browser for the initial parser test.
    # Save the permitted, publicly accessible category page as jumia.html.
    html_path = Path("jumia.html")

    if not html_path.exists():
        print("No jumia.html found.")
        print("Save an accessible category-page HTML snapshot first.")
        return

    products = extract_products(
        html_path.read_text(encoding="utf-8")
    )

    if not products:
        print("No matching products or prices found.")
        print("Check the product availability and HTML selectors.")
        return

    for product in products:
        record_price(product)

if __name__ == "__main__":
    html = fetch_page("https://books.toscrape.com/")

    if html:
        soup = BeautifulSoup(html, "html.parser")

        for card in soup.select("article.product_pod")[:5]:
            title_element = card.select_one("h3 a")
            price_element = card.select_one(".price_color")

            if title_element and price_element:
                title = title_element.get("title", "")
                price = price_element.get_text(strip=True)

                print(f"Book: {title}")
                print(f"Price: {price}")
                print("-" * 30)
