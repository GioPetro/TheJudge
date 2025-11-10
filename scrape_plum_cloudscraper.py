#!/usr/bin/env python3
"""
Plum Reviews Scraper - CloudScraper Version
Uses cloudscraper to bypass Cloudflare and anti-bot protections
Still fast and uses only BeautifulSoup4 for parsing
"""

import requests
try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False

from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import re
import sys

# Configuration
BASE_URL = "https://smartmoneypeople.com/plum-reviews/product/app"
OUTPUT_FILE = "plum_reviews.xlsx"


def create_scraper():
    """Create a scraper with anti-bot bypass"""
    if CLOUDSCRAPER_AVAILABLE:
        print("Using cloudscraper (can bypass Cloudflare)")
        return cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
    else:
        print("⚠ cloudscraper not installed, using regular requests")
        print("Install it with: pip install cloudscraper")
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        return session


def fetch_page(url, scraper):
    """Fetch a page"""
    try:
        print(f"\nFetching: {url}")
        response = scraper.get(url, timeout=30)
        response.raise_for_status()
        print(f"✓ Success! Got {len(response.text)} bytes")
        return response.text
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            print(f"❌ 403 Forbidden - Site is blocking requests")
            return None
        else:
            print(f"❌ HTTP Error: {e}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def extract_reviews(soup):
    """Extract all reviews using BeautifulSoup"""
    reviews = []

    print("\nAnalyzing HTML structure...")

    # Debug save
    with open('debug_page.html', 'w', encoding='utf-8') as f:
        f.write(soup.prettify())
    print("✓ Saved to debug_page.html")

    # Try multiple selector strategies
    strategies = [
        ('div[class*=review]', lambda: soup.find_all('div', class_=re.compile(r'review', re.I))),
        ('article[class*=review]', lambda: soup.find_all('article', class_=re.compile(r'review', re.I))),
        ('article tags', lambda: soup.find_all('article')),
        ('div[class*=card]', lambda: soup.find_all('div', class_=re.compile(r'card', re.I))),
        ('data-testid', lambda: soup.find_all(attrs={"data-testid": re.compile(r'review', re.I)})),
        ('li items', lambda: soup.find_all('li', class_=re.compile(r'review|comment', re.I))),
    ]

    containers = []
    for name, func in strategies:
        containers = func()
        if containers:
            print(f"✓ Found {len(containers)} containers using: {name}")
            break

    if not containers:
        print("❌ No review containers found")
        return []

    print(f"\nExtracting from {len(containers)} containers...")

    for idx, container in enumerate(containers, 1):
        review = {'review_id': idx}

        # Rating
        rating_elem = container.find(attrs={'aria-label': re.compile(r'star|rating', re.I)})
        if not rating_elem:
            rating_elem = container.find(class_=re.compile(r'rating|star', re.I))

        if rating_elem:
            text = ' '.join([
                rating_elem.get_text(strip=True),
                rating_elem.get('aria-label', ''),
                rating_elem.get('title', '')
            ])
            match = re.search(r'(\d+(?:\.\d+)?)\s*(?:out of|/|of)?\s*5', text, re.I)
            if match:
                review['rating'] = float(match.group(1))

        # Date
        time_elem = container.find('time')
        if time_elem:
            review['date'] = time_elem.get('datetime', time_elem.get_text(strip=True))
        else:
            date_elem = container.find(class_=re.compile(r'date', re.I))
            if date_elem:
                review['date'] = date_elem.get_text(strip=True)

        # Author
        author = container.find(class_=re.compile(r'author|reviewer', re.I))
        if author:
            review['reviewer_name'] = author.get_text(strip=True)

        # Title
        title = container.find(['h1', 'h2', 'h3', 'h4', 'h5'])
        if title:
            review['review_title'] = title.get_text(strip=True)

        # Review text
        text_elem = container.find(class_=re.compile(r'review-text|review-body|content', re.I))
        if text_elem:
            review['review_text'] = text_elem.get_text(strip=True)
        else:
            # Fallback to paragraphs
            paragraphs = container.find_all('p')
            if paragraphs:
                review['review_text'] = ' '.join(p.get_text(strip=True) for p in paragraphs)

        # Verified
        verified = container.find(class_=re.compile(r'verified', re.I))
        review['verified'] = bool(verified)

        # Only add if has content
        if any([review.get('review_text'), review.get('rating')]):
            reviews.append(review)
            if idx <= 2:
                print(f"  Review {idx}: {review.get('rating', '?')}★ - {review.get('review_text', '')[:50]}...")

    return reviews


def scrape():
    """Main scraping function"""
    scraper = create_scraper()

    html = fetch_page(BASE_URL, scraper)
    if not html:
        return None

    soup = BeautifulSoup(html, 'html.parser')
    reviews = extract_reviews(soup)

    print(f"\n✓ Extracted {len(reviews)} reviews total")
    return reviews


def save_excel(reviews, filename=OUTPUT_FILE):
    """Save to Excel"""
    if not reviews:
        return False

    df = pd.DataFrame(reviews)
    df['scraped_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    df['source_url'] = BASE_URL

    df.to_excel(filename, index=False, engine='openpyxl')

    print(f"\n{'='*60}")
    print(f"✅ Saved {len(reviews)} reviews to {filename}")
    print(f"{'='*60}")

    if 'rating' in df.columns:
        print(f"\n📊 Stats:")
        print(f"  Reviews: {len(reviews)}")
        ratings = df['rating'].dropna()
        if len(ratings) > 0:
            print(f"  Avg rating: {ratings.mean():.2f}/5")
            print(f"  Distribution:\n{df['rating'].value_counts().sort_index()}")

    return True


def load_from_file(filepath):
    """Load from saved HTML file"""
    print(f"Loading from: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    return extract_reviews(soup)


def main():
    print("="*60)
    print("PLUM REVIEWS SCRAPER")
    print("="*60)
    print(f"Source: {BASE_URL}")
    print(f"Output: {OUTPUT_FILE}\n")

    # Check if user provided HTML file
    if len(sys.argv) > 1:
        reviews = load_from_file(sys.argv[1])
    else:
        reviews = scrape()

    if not reviews:
        print("\n" + "="*60)
        print("FAILED - Website is blocking requests")
        print("="*60)
        print("\nSOLUTION 1: Install cloudscraper")
        print("  pip install cloudscraper")
        print("  python scrape_plum_cloudscraper.py")
        print("\nSOLUTION 2: Manual download")
        print(f"  1. Open {BASE_URL} in browser")
        print("  2. Scroll to load ALL reviews")
        print("  3. Right-click → Save As → Complete webpage")
        print("  4. python scrape_plum_cloudscraper.py saved_file.html")
        sys.exit(1)

    if save_excel(reviews):
        print(f"\n✅ Done! Check '{OUTPUT_FILE}'")


if __name__ == "__main__":
    main()
