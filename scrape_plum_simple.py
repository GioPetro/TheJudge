#!/usr/bin/env python3
"""
Plum Reviews Scraper - Simple & Fast
Uses only requests + BeautifulSoup4 for maximum speed
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import re
import sys

# Configuration
BASE_URL = "https://smartmoneypeople.com/plum-reviews/product/app"
OUTPUT_FILE = "plum_reviews.xlsx"

# Headers to mimic a real browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Cache-Control': 'max-age=0',
}


def fetch_page(url, session):
    """Fetch a page with requests"""
    try:
        print(f"Fetching: {url}")
        response = session.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        print(f"✓ Got response: {response.status_code}")
        return response.text
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            print(f"\n⚠ 403 Forbidden - Website is blocking automated requests")
            print("\nWORKAROUND:")
            print("1. Open this URL in your browser: {url}")
            print("2. Right-click → Save As → Save complete webpage")
            print("3. Run: python scrape_plum_simple.py <saved_file.html>")
            return None
        else:
            print(f"HTTP Error: {e}")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def extract_reviews(soup):
    """Extract all reviews from the page using BeautifulSoup"""
    reviews = []

    print("\nAnalyzing page structure...")

    # Save HTML for debugging
    with open('debug_page.html', 'w', encoding='utf-8') as f:
        f.write(soup.prettify())
    print("✓ Saved page HTML to debug_page.html")

    # Try multiple selector strategies
    strategies = [
        ('div with review class', lambda: soup.find_all('div', class_=re.compile(r'review', re.I))),
        ('article with review class', lambda: soup.find_all('article', class_=re.compile(r'review', re.I))),
        ('any article tags', lambda: soup.find_all('article')),
        ('div with card class', lambda: soup.find_all('div', class_=re.compile(r'card', re.I))),
        ('review data attribute', lambda: soup.find_all(attrs={"data-testid": re.compile(r'review', re.I)})),
        ('list items with review', lambda: soup.find_all('li', class_=re.compile(r'review|comment|feedback', re.I))),
    ]

    review_containers = []
    for strategy_name, strategy_func in strategies:
        containers = strategy_func()
        if containers:
            print(f"✓ Found {len(containers)} containers using: {strategy_name}")
            review_containers = containers
            break

    if not review_containers:
        print("❌ Could not find review containers")
        print("Check debug_page.html to inspect the HTML structure")
        return []

    print(f"\nExtracting data from {len(review_containers)} containers...")

    for idx, container in enumerate(review_containers, 1):
        review = {'review_id': idx}

        # Extract rating
        rating_elem = container.find(attrs={'aria-label': re.compile(r'star|rating', re.I)})
        if not rating_elem:
            rating_elem = container.find(class_=re.compile(r'rating|star', re.I))

        if rating_elem:
            rating_text = ' '.join([
                rating_elem.get_text(strip=True),
                rating_elem.get('aria-label', ''),
                rating_elem.get('title', '')
            ])

            # Extract numeric rating
            match = re.search(r'(\d+(?:\.\d+)?)\s*(?:out of|/|of)?\s*5', rating_text, re.I)
            if match:
                review['rating'] = float(match.group(1))
            else:
                # Count filled stars
                stars = container.find_all(class_=re.compile(r'star', re.I))
                filled = [s for s in stars if 'fill' in ' '.join(s.get('class', [])).lower()]
                if filled:
                    review['rating'] = len(filled)

        # Extract date
        time_elem = container.find('time')
        if time_elem:
            review['date'] = time_elem.get('datetime', time_elem.get_text(strip=True))
        else:
            date_elem = container.find(class_=re.compile(r'date|time', re.I))
            if date_elem:
                review['date'] = date_elem.get_text(strip=True)

        # Extract reviewer name
        for pattern in [
            container.find(class_=re.compile(r'author|reviewer|username', re.I)),
            container.find(attrs={'itemprop': 'author'}),
            container.find(class_=re.compile(r'name', re.I))
        ]:
            if pattern:
                text = pattern.get_text(strip=True)
                if text and len(text) < 100:
                    review['reviewer_name'] = text
                    break

        # Extract review title
        title_elem = container.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        if title_elem:
            title = title_elem.get_text(strip=True)
            if title and len(title) < 200:
                review['review_title'] = title

        # Extract review text
        for pattern in [
            container.find(class_=re.compile(r'review-text|review-content|review-body|comment-text', re.I)),
            container.find(attrs={'itemprop': 'reviewBody'}),
            container.find(class_=re.compile(r'content|body', re.I))
        ]:
            if pattern:
                review['review_text'] = pattern.get_text(strip=True)
                break

        # Fallback: get all paragraphs
        if 'review_text' not in review:
            paragraphs = container.find_all('p')
            if paragraphs:
                text = ' '.join(p.get_text(strip=True) for p in paragraphs)
                if text:
                    review['review_text'] = text

        # Extract helpful votes
        helpful_elem = container.find(class_=re.compile(r'helpful|useful|vote', re.I))
        if helpful_elem:
            match = re.search(r'(\d+)', helpful_elem.get_text(strip=True))
            if match:
                review['helpful_votes'] = int(match.group(1))

        # Extract verified status
        verified = container.find(class_=re.compile(r'verified|confirmed', re.I))
        if not verified:
            verified = container.find(string=re.compile(r'verified', re.I))
        review['verified'] = bool(verified)

        # Only add if has meaningful content
        if any([review.get('review_text'), review.get('rating'), review.get('review_title')]):
            reviews.append(review)

            # Show first few for debugging
            if idx <= 3:
                print(f"\n  Review {idx}:")
                for key, val in review.items():
                    if key == 'review_text':
                        print(f"    {key}: {str(val)[:60]}...")
                    else:
                        print(f"    {key}: {val}")

    return reviews


def find_pagination(soup, current_url):
    """Find pagination links"""
    pagination_urls = []

    # Look for pagination
    pagination = soup.find(class_=re.compile(r'pagination', re.I))
    if pagination:
        links = pagination.find_all('a', href=True)
        for link in links:
            href = link['href']
            if href.startswith('/'):
                href = 'https://smartmoneypeople.com' + href
            elif not href.startswith('http'):
                continue

            if 'plum-reviews' in href and href not in pagination_urls:
                pagination_urls.append(href)

    # Look for "next" link
    next_link = soup.find('a', class_=re.compile(r'next', re.I), href=True)
    if next_link:
        href = next_link['href']
        if href.startswith('/'):
            href = 'https://smartmoneypeople.com' + href
        if href not in pagination_urls:
            pagination_urls.append(href)

    return pagination_urls


def scrape_reviews():
    """Main scraping function"""
    all_reviews = []
    session = requests.Session()

    visited_urls = set()
    urls_to_visit = [BASE_URL]

    while urls_to_visit:
        url = urls_to_visit.pop(0)

        if url in visited_urls:
            continue

        visited_urls.add(url)

        # Fetch page
        html = fetch_page(url, session)
        if not html:
            break

        # Parse with BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        # Extract reviews
        reviews = extract_reviews(soup)
        print(f"✓ Extracted {len(reviews)} reviews from this page")
        all_reviews.extend(reviews)

        # Find more pages
        pagination_urls = find_pagination(soup, url)
        if pagination_urls:
            print(f"Found {len(pagination_urls)} more pages")
            for new_url in pagination_urls:
                if new_url not in visited_urls:
                    urls_to_visit.append(new_url)

        # Be respectful - wait between requests
        if urls_to_visit:
            print("Waiting 2 seconds...")
            time.sleep(2)

    return all_reviews


def save_to_excel(reviews, filename=OUTPUT_FILE):
    """Save reviews to Excel"""
    if not reviews:
        print("\n❌ No reviews to save!")
        return False

    df = pd.DataFrame(reviews)
    df['scraped_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    df['source_url'] = BASE_URL

    # Reorder columns
    cols = ['review_id', 'date', 'rating', 'reviewer_name', 'review_title',
            'review_text', 'verified', 'helpful_votes', 'scraped_at', 'source_url']
    cols = [c for c in cols if c in df.columns]
    cols += [c for c in df.columns if c not in cols]
    df = df[cols]

    # Save
    df.to_excel(filename, index=False, engine='openpyxl')

    print(f"\n{'='*60}")
    print(f"✅ SUCCESS! Saved {len(reviews)} reviews to {filename}")
    print(f"{'='*60}")
    print(f"\nColumns: {', '.join(df.columns.tolist())}")

    if 'rating' in df.columns:
        print(f"\n📊 Statistics:")
        print(f"  Total reviews: {len(reviews)}")
        ratings = df['rating'].dropna()
        if len(ratings) > 0:
            print(f"  Average rating: {ratings.mean():.2f}/5.0")
            print(f"  Rating counts:\n{df['rating'].value_counts().sort_index()}")

    if 'review_text' in df.columns:
        lengths = df['review_text'].str.len()
        print(f"  Avg review length: {lengths.mean():.0f} characters")

    print(f"\n📝 First review:")
    for col in ['date', 'rating', 'reviewer_name', 'review_title']:
        if col in df.columns and len(df) > 0:
            print(f"  {col}: {df[col].iloc[0]}")
    if 'review_text' in df.columns and len(df) > 0:
        text = str(df['review_text'].iloc[0])
        print(f"  text: {text[:100]}...")

    return True


def load_from_file(filepath):
    """Load HTML from a saved file"""
    print(f"Loading HTML from: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()
    soup = BeautifulSoup(html, 'html.parser')
    return extract_reviews(soup)


def main():
    print("="*60)
    print("PLUM REVIEWS SCRAPER (Fast - BS4 Only)")
    print("="*60)
    print(f"Target: {BASE_URL}")
    print(f"Output: {OUTPUT_FILE}\n")

    # Check if user provided an HTML file
    if len(sys.argv) > 1:
        html_file = sys.argv[1]
        print(f"Using local HTML file: {html_file}\n")
        reviews = load_from_file(html_file)
    else:
        # Scrape from web
        reviews = scrape_reviews()

    if not reviews:
        print("\n❌ No reviews extracted!")
        print("\nIf you got a 403 error, the site is blocking bots.")
        print("\nManual workaround:")
        print("1. Open URL in browser: " + BASE_URL)
        print("2. Scroll to load all reviews")
        print("3. Right-click → Save As → Complete webpage")
        print("4. Run: python scrape_plum_simple.py <saved_file.html>")
        sys.exit(1)

    # Save to Excel
    if save_to_excel(reviews):
        print(f"\n✅ Done! Open '{OUTPUT_FILE}' to view reviews.")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
