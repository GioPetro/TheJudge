#!/usr/bin/env python3
"""
Plum Reviews Scraper - Playwright Version
Scrapes all reviews from SmartMoneyPeople Plum app reviews page
Uses Playwright which automatically manages browser installations
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import sys
import re

# Configuration
BASE_URL = "https://smartmoneypeople.com/plum-reviews/product/app"


def extract_reviews_from_soup(soup):
    """Extract all reviews from parsed HTML"""
    reviews = []

    print("Looking for review containers...")

    # Try multiple selector strategies
    review_containers = []

    # Strategy 1: Look for common review class patterns
    review_containers = soup.find_all('div', class_=lambda x: x and 'review' in str(x).lower())
    print(f"Strategy 1 (review class): Found {len(review_containers)} containers")

    # Strategy 2: Look for article tags
    if not review_containers:
        review_containers = soup.find_all('article')
        print(f"Strategy 2 (article tags): Found {len(review_containers)} containers")

    # Strategy 3: Look for specific data attributes
    if not review_containers:
        review_containers = soup.find_all(attrs={"data-testid": re.compile(r'review', re.I)})
        print(f"Strategy 3 (data-testid): Found {len(review_containers)} containers")

    # Strategy 4: Look for common card/item patterns
    if not review_containers:
        review_containers = soup.find_all('div', class_=lambda x: x and any(
            term in str(x).lower() for term in ['card', 'item', 'comment', 'feedback']
        ))
        print(f"Strategy 4 (card/item): Found {len(review_containers)} containers")

    for idx, container in enumerate(review_containers):
        review_data = {}

        # Extract rating
        rating_elem = container.find(class_=lambda x: x and 'rating' in str(x).lower())
        if not rating_elem:
            rating_elem = container.find(class_=lambda x: x and 'star' in str(x).lower())

        if rating_elem:
            # Try to extract numeric rating
            rating_text = rating_elem.get_text(strip=True)
            aria_label = rating_elem.get('aria-label', '') + ' ' + str(rating_elem.get('title', ''))
            combined_text = rating_text + ' ' + aria_label

            rating_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:out of|/|\s+)?\s*5', combined_text, re.I)
            if rating_match:
                review_data['rating'] = float(rating_match.group(1))
            else:
                # Count filled stars
                stars = container.find_all(class_=lambda x: x and 'star' in str(x).lower())
                filled_stars = [s for s in stars if 'fill' in str(s.get('class', [])).lower() or
                               'active' in str(s.get('class', [])).lower()]
                if filled_stars:
                    review_data['rating'] = len(filled_stars)

        # Extract date
        date_elem = container.find('time')
        if date_elem:
            review_data['date'] = date_elem.get('datetime', date_elem.get_text(strip=True))
        else:
            date_elem = container.find(class_=lambda x: x and 'date' in str(x).lower())
            if date_elem:
                review_data['date'] = date_elem.get_text(strip=True)

        # Extract reviewer name
        author_elem = container.find(class_=lambda x: x and ('author' in str(x).lower() or
                                                              'name' in str(x).lower() or
                                                              'user' in str(x).lower()))
        if author_elem:
            review_data['reviewer_name'] = author_elem.get_text(strip=True)

        # Extract review title
        title_elem = container.find(['h1', 'h2', 'h3', 'h4', 'h5'])
        if title_elem:
            review_data['review_title'] = title_elem.get_text(strip=True)

        # Extract review text
        content_elem = container.find(class_=lambda x: x and ('content' in str(x).lower() or
                                                               'text' in str(x).lower() or
                                                               'body' in str(x).lower() or
                                                               'comment' in str(x).lower()))
        if content_elem:
            review_data['review_text'] = content_elem.get_text(strip=True)
        else:
            # Get all paragraph text
            paragraphs = container.find_all('p')
            if paragraphs:
                review_data['review_text'] = ' '.join([p.get_text(strip=True) for p in paragraphs])

        # Extract helpful votes
        helpful_elem = container.find(class_=lambda x: x and 'helpful' in str(x).lower())
        if helpful_elem:
            helpful_text = helpful_elem.get_text(strip=True)
            helpful_match = re.search(r'(\d+)', helpful_text)
            if helpful_match:
                review_data['helpful_votes'] = int(helpful_match.group(1))

        # Extract verification status
        verified_elem = container.find(class_=lambda x: x and 'verified' in str(x).lower())
        review_data['verified'] = bool(verified_elem)

        # Only add if we have meaningful content
        if review_data.get('review_text') or review_data.get('rating') or review_data.get('review_title'):
            # Add container HTML for debugging if needed
            # review_data['_debug_html'] = str(container)[:200]
            reviews.append(review_data)

    return reviews


def scrape_with_playwright():
    """Scrape reviews using Playwright"""
    all_reviews = []

    print("Starting Playwright browser...")
    with sync_playwright() as p:
        # Launch browser
        try:
            browser = p.chromium.launch(headless=True)
            print("✓ Chromium browser launched")
        except Exception as e:
            print(f"Chromium launch failed: {e}")
            print("Trying Firefox...")
            try:
                browser = p.firefox.launch(headless=True)
                print("✓ Firefox browser launched")
            except Exception as e2:
                print(f"Firefox launch failed: {e2}")
                print("\nPlease install browsers: python -m playwright install")
                return []

        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )

        page = context.new_page()

        try:
            print(f"\nNavigating to: {BASE_URL}")
            page.goto(BASE_URL, wait_until='networkidle', timeout=30000)
            print("✓ Page loaded")

            # Wait for content to load
            time.sleep(3)

            # Scroll to load lazy content
            print("Scrolling to load all content...")
            previous_height = page.evaluate("document.body.scrollHeight")
            scroll_attempts = 0
            max_scrolls = 20

            while scroll_attempts < max_scrolls:
                # Scroll to bottom
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.5)

                # Check if we need to click "Load More"
                try:
                    load_more_button = page.locator("button:has-text('Load more'), button:has-text('Show more'), a:has-text('Load more')").first
                    if load_more_button.is_visible(timeout=1000):
                        print("Clicking 'Load More' button...")
                        load_more_button.click()
                        time.sleep(2)
                except:
                    pass

                # Check if height changed
                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == previous_height:
                    break

                previous_height = new_height
                scroll_attempts += 1

            print(f"Finished scrolling ({scroll_attempts} attempts)")

            # Get page content
            html_content = page.content()

            # Parse with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # Save HTML for debugging
            with open('page_source.html', 'w', encoding='utf-8') as f:
                f.write(soup.prettify())
            print("✓ Saved page source to page_source.html for debugging")

            # Extract reviews
            print("\nExtracting reviews...")
            all_reviews = extract_reviews_from_soup(soup)
            print(f"✓ Extracted {len(all_reviews)} reviews")

        except PlaywrightTimeout as e:
            print(f"Timeout error: {e}")
        except Exception as e:
            print(f"Error during scraping: {e}")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()

    return all_reviews


def save_to_excel(reviews, filename='plum_reviews.xlsx'):
    """Save reviews to Excel file"""
    if not reviews:
        print("\n⚠ No reviews to save!")
        return

    # Create DataFrame
    df = pd.DataFrame(reviews)

    # Add metadata
    df['scraped_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    df['source_url'] = BASE_URL

    # Reorder columns
    column_order = ['date', 'rating', 'reviewer_name', 'review_title', 'review_text',
                    'verified', 'helpful_votes', 'scraped_at', 'source_url']
    existing_columns = [col for col in column_order if col in df.columns]
    other_columns = [col for col in df.columns if col not in column_order]
    final_columns = existing_columns + other_columns

    df = df[final_columns]

    # Save to Excel
    df.to_excel(filename, index=False, engine='openpyxl')

    print(f"\n{'='*60}")
    print(f"✓ SUCCESS! Saved {len(reviews)} reviews to {filename}")
    print(f"{'='*60}")
    print(f"\nColumns: {', '.join(df.columns)}")

    # Show summary statistics
    if 'rating' in df.columns:
        print(f"\nRating distribution:")
        print(df['rating'].value_counts().sort_index())
        print(f"Average rating: {df['rating'].mean():.2f}")

    print(f"\nFirst review preview:")
    for col in ['date', 'rating', 'reviewer_name', 'review_title']:
        if col in df.columns:
            print(f"  {col}: {df[col].iloc[0]}")
    if 'review_text' in df.columns:
        text = str(df['review_text'].iloc[0])
        print(f"  review_text: {text[:100]}...")


def main():
    print("=" * 60)
    print("Plum Reviews Scraper (Playwright)")
    print("=" * 60)
    print(f"Target: {BASE_URL}\n")

    # Scrape reviews
    reviews = scrape_with_playwright()

    if not reviews:
        print("\n⚠ No reviews extracted!")
        print("\nTroubleshooting:")
        print("1. Check page_source.html to see what was loaded")
        print("2. The website structure might be different than expected")
        print("3. Try installing playwright browsers: python -m playwright install")
        sys.exit(1)

    # Save to Excel
    save_to_excel(reviews)


if __name__ == "__main__":
    main()
