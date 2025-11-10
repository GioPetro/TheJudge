#!/usr/bin/env python3
"""
SmartMoneyPeople Reviews Scraper - Simple & Fast
Uses only requests + BeautifulSoup4 for maximum speed

USAGE:
    1. Configure URLs and settings in the CONFIGURATION section below
    2. Run: python scrape_plum_simple.py
    3. Or with saved HTML: python scrape_plum_simple.py saved_page.html

REQUIREMENTS:
    pip install requests beautifulsoup4 pandas openpyxl lxml
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import re
import sys
import os

# ==================== CONFIGURATION ====================
MIN_REVIEW_YEAR = 2024  # Filter reviews from this year onwards (set to None to get all reviews)

# List of SmartMoneyPeople URLs to scrape
smp_pages = [
    "https://smartmoneypeople.com/plum-reviews/product/app",
    # Add more URLs here, e.g.:
    # "https://smartmoneypeople.com/monzo-reviews",
    # "https://smartmoneypeople.com/revolut-reviews",
]

# Auto-generate clean names from URLs
smp_names = [
    re.sub(r'^https?://(www\.)?smartmoneypeople\.com/', '', url)
       .replace('/', '_')
       .replace('-reviews', '')
       .replace('-', '_')
    for url in smp_pages
]

# Output directory
base_path = './'  # Change to your preferred path, e.g., 'C:/Users/yourname/reviews/'
os.makedirs(base_path, exist_ok=True)

# ======================================================

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


def parse_review_date(date_string):
    """Parse review date string to datetime object"""
    if not date_string:
        return None

    try:
        # Try common date formats
        for fmt in [
            '%Y-%m-%d',
            '%d/%m/%Y',
            '%m/%d/%Y',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%d %B %Y',
            '%B %d, %Y',
        ]:
            try:
                return datetime.strptime(date_string.strip(), fmt)
            except ValueError:
                continue

        # Try parsing relative dates like "2 days ago"
        if 'ago' in date_string.lower():
            return datetime.now()  # Approximate

        # Extract year if possible
        year_match = re.search(r'20\d{2}', date_string)
        if year_match:
            year = int(year_match.group())
            return datetime(year, 1, 1)

    except Exception as e:
        print(f"  Warning: Could not parse date '{date_string}': {e}")

    return None


def filter_by_year(review):
    """Check if review meets the year filter criteria"""
    if MIN_REVIEW_YEAR is None:
        return True

    date_str = review.get('date')
    if not date_str:
        return True  # Include reviews without dates

    parsed_date = parse_review_date(date_str)
    if parsed_date:
        return parsed_date.year >= MIN_REVIEW_YEAR

    return True  # Include if can't parse


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
            # Apply date filter
            if filter_by_year(review):
                reviews.append(review)

                # Show first few for debugging
                if len(reviews) <= 3:
                    print(f"\n  Review {len(reviews)}:")
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


def scrape_reviews(base_url):
    """Main scraping function"""
    all_reviews = []
    session = requests.Session()

    visited_urls = set()
    urls_to_visit = [base_url]

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


def save_to_excel(reviews, filename, source_url):
    """Save reviews to Excel"""
    if not reviews:
        print("\n❌ No reviews to save!")
        return False

    df = pd.DataFrame(reviews)
    df['scraped_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    df['source_url'] = source_url

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

    # Date filter info
    if MIN_REVIEW_YEAR:
        print(f"📅 Date filter: Reviews from {MIN_REVIEW_YEAR} onwards")

    print(f"\nColumns: {', '.join(df.columns.tolist())}")

    if 'rating' in df.columns:
        print(f"\n📊 Statistics:")
        print(f"  Total reviews: {len(reviews)}")
        ratings = df['rating'].dropna()
        if len(ratings) > 0:
            print(f"  Average rating: {ratings.mean():.2f}/5.0")
            print(f"  Rating distribution:")
            for rating, count in df['rating'].value_counts().sort_index().items():
                print(f"    {'★' * int(rating)}: {count} reviews")

    # Date range
    if 'date' in df.columns:
        dates_parsed = df['date'].apply(parse_review_date).dropna()
        if len(dates_parsed) > 0:
            print(f"\n📅 Date range:")
            print(f"  Oldest: {dates_parsed.min().strftime('%Y-%m-%d')}")
            print(f"  Newest: {dates_parsed.max().strftime('%Y-%m-%d')}")

    if 'review_text' in df.columns:
        lengths = df['review_text'].str.len()
        print(f"\n📏 Avg review length: {lengths.mean():.0f} characters")

    print(f"\n📝 Sample review:")
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
    print("="*70)
    print("SMARTMONEYPEOPLE REVIEWS SCRAPER (Fast - BS4 Only)")
    print("="*70)
    print(f"Date filter: Reviews from {MIN_REVIEW_YEAR or 'ALL YEARS'} onwards")
    print(f"URLs to scrape: {len(smp_pages)}")
    print(f"Output directory: {base_path}")
    print("="*70 + "\n")

    # Check if user provided an HTML file
    if len(sys.argv) > 1:
        html_file = sys.argv[1]
        print(f"Using local HTML file: {html_file}\n")
        reviews = load_from_file(html_file)

        # Save with generic name
        output_file = os.path.join(base_path, 'reviews_from_file.xlsx')
        if save_to_excel(reviews, output_file, 'local_file'):
            print(f"\n✅ Done! Saved to '{output_file}'")
        sys.exit(0)

    # Scrape all configured URLs
    all_results = []

    for idx, (url, name) in enumerate(zip(smp_pages, smp_names), 1):
        print(f"\n{'='*70}")
        print(f"[{idx}/{len(smp_pages)}] Processing: {name}")
        print(f"URL: {url}")
        print("="*70)

        # Scrape reviews
        reviews = scrape_reviews(url)

        if not reviews:
            print(f"\n⚠ No reviews extracted from {name}!")
            print("\nIf you got a 403 error, the site is blocking bots.")
            print("\nManual workaround:")
            print(f"1. Open URL in browser: {url}")
            print("2. Scroll to load all reviews")
            print("3. Right-click → Save As → Complete webpage")
            print(f"4. Run: python scrape_plum_simple.py <saved_file.html>")
            continue

        # Save to Excel
        output_file = os.path.join(base_path, f'{name}_reviews.xlsx')
        if save_to_excel(reviews, output_file, url):
            all_results.append({
                'name': name,
                'url': url,
                'reviews': len(reviews),
                'file': output_file
            })

        # Be respectful between different sites
        if idx < len(smp_pages):
            print("\nWaiting 5 seconds before next URL...")
            time.sleep(5)

    # Summary
    print("\n" + "="*70)
    print("SCRAPING SUMMARY")
    print("="*70)

    if not all_results:
        print("❌ No reviews were successfully scraped from any URL")
        sys.exit(1)

    for result in all_results:
        print(f"✅ {result['name']}: {result['reviews']} reviews → {result['file']}")

    print(f"\n📊 Total: {sum(r['reviews'] for r in all_results)} reviews from {len(all_results)} sources")
    print("="*70)


if __name__ == "__main__":
    main()
