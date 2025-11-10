#!/usr/bin/env python3
"""
Plum Reviews Scraper - Final Version
Scrapes all reviews from SmartMoneyPeople Plum app reviews page

USAGE:
    python scrape_plum_reviews_final.py

REQUIREMENTS:
    pip install playwright pandas openpyxl beautifulsoup4
    python -m playwright install chromium

If Playwright doesn't work, the script will attempt other methods.
"""

import sys
import time
import re
from datetime import datetime
from bs4 import BeautifulSoup
import pandas as pd

# Configuration
BASE_URL = "https://smartmoneypeople.com/plum-reviews/product/app"
OUTPUT_FILE = "plum_reviews.xlsx"


def extract_reviews_from_soup(soup):
    """
    Extract all reviews from parsed HTML
    This function uses multiple strategies to find reviews
    """
    reviews = []

    print("Analyzing page structure...")

    # Debug: Save HTML to file
    with open('debug_page.html', 'w', encoding='utf-8') as f:
        f.write(soup.prettify())
    print("✓ Saved page HTML to debug_page.html")

    # Strategy 1: Look for review containers by class/data attributes
    selectors_to_try = [
        ('div', {'class': re.compile(r'review', re.I)}),
        ('article', {'class': re.compile(r'review', re.I)}),
        ('div', {'data-testid': re.compile(r'review', re.I)}),
        ('div', {'class': re.compile(r'card', re.I)}),
        ('div', {'class': re.compile(r'item', re.I)}),
        ('article', {}),
        ('li', {'class': re.compile(r'review|comment|feedback', re.I)}),
    ]

    review_containers = []
    for tag, attrs in selectors_to_try:
        containers = soup.find_all(tag, attrs)
        if containers:
            print(f"Found {len(containers)} potential containers using {tag} {attrs}")
            review_containers = containers
            break

    if not review_containers:
        print("⚠ Could not find review containers with standard selectors")
        print("Please check debug_page.html and update the selectors")
        return []

    print(f"\nProcessing {len(review_containers)} containers...")

    for idx, container in enumerate(review_containers, 1):
        review_data = {'review_id': idx}

        # Extract rating
        rating_elem = container.find(attrs={'aria-label': re.compile(r'star|rating', re.I)})
        if not rating_elem:
            rating_elem = container.find(class_=re.compile(r'rating|star', re.I))

        if rating_elem:
            # Try multiple patterns to extract rating
            rating_text = rating_elem.get_text(strip=True)
            aria_label = rating_elem.get('aria-label', '')
            title = rating_elem.get('title', '')

            combined = f"{rating_text} {aria_label} {title}"

            # Pattern 1: "X out of 5" or "X/5" or "X of 5"
            match = re.search(r'(\d+(?:\.\d+)?)\s*(?:out of|/|of)\s*5', combined, re.I)
            if match:
                review_data['rating'] = float(match.group(1))
            else:
                # Pattern 2: Just a number
                match = re.search(r'(\d+(?:\.\d+)?)', combined)
                if match:
                    val = float(match.group(1))
                    if val <= 5:
                        review_data['rating'] = val

            # Pattern 3: Count star icons
            if 'rating' not in review_data:
                stars = container.find_all(class_=re.compile(r'star', re.I))
                filled = [s for s in stars if 'fill' in str(s.get('class', '')).lower()]
                if filled:
                    review_data['rating'] = len(filled)

        # Extract date
        time_elem = container.find('time')
        if time_elem:
            review_data['date'] = time_elem.get('datetime', time_elem.get_text(strip=True))
        else:
            date_elem = container.find(class_=re.compile(r'date|time|posted|published', re.I))
            if date_elem:
                review_data['date'] = date_elem.get_text(strip=True)

        # Extract reviewer name/author
        author_patterns = [
            container.find(class_=re.compile(r'author|reviewer|username|user-name', re.I)),
            container.find(attrs={'itemprop': 'author'}),
            container.find(class_=re.compile(r'name', re.I))
        ]
        for author_elem in author_patterns:
            if author_elem:
                text = author_elem.get_text(strip=True)
                if text and len(text) < 100:  # Sanity check
                    review_data['reviewer_name'] = text
                    break

        # Extract review title/heading
        title_elem = container.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        if title_elem:
            title_text = title_elem.get_text(strip=True)
            if title_text and len(title_text) < 200:  # Sanity check
                review_data['review_title'] = title_text

        # Extract review text/content
        content_patterns = [
            container.find(class_=re.compile(r'review-text|review-content|review-body|comment-text|content|body', re.I)),
            container.find(attrs={'itemprop': 'reviewBody'}),
            container.find(attrs={'itemprop': 'description'}),
        ]

        for content_elem in content_patterns:
            if content_elem:
                review_data['review_text'] = content_elem.get_text(strip=True)
                break

        # If no content found, try getting all paragraphs
        if 'review_text' not in review_data:
            paragraphs = container.find_all('p')
            if paragraphs:
                text = ' '.join([p.get_text(strip=True) for p in paragraphs])
                if text:
                    review_data['review_text'] = text

        # Extract helpful votes
        helpful_elem = container.find(class_=re.compile(r'helpful|useful|vote', re.I))
        if helpful_elem:
            helpful_text = helpful_elem.get_text(strip=True)
            match = re.search(r'(\d+)', helpful_text)
            if match:
                review_data['helpful_votes'] = int(match.group(1))

        # Extract verified status
        verified_elem = container.find(class_=re.compile(r'verified|confirmed', re.I))
        if not verified_elem:
            verified_elem = container.find(string=re.compile(r'verified', re.I))
        review_data['verified'] = bool(verified_elem)

        # Only add if we have substantive content
        has_content = any([
            review_data.get('review_text'),
            review_data.get('rating'),
            review_data.get('review_title')
        ])

        if has_content:
            reviews.append(review_data)
            if idx <= 3:  # Show first 3 for debugging
                print(f"\nReview {idx}:")
                for key, value in review_data.items():
                    if key == 'review_text':
                        print(f"  {key}: {str(value)[:60]}...")
                    else:
                        print(f"  {key}: {value}")

    return reviews


def method_playwright():
    """Method 1: Use Playwright (recommended)"""
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

        print("\n[Method 1] Using Playwright...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            ).new_page()

            print(f"Loading {BASE_URL}...")
            page.goto(BASE_URL, wait_until='networkidle', timeout=30000)
            time.sleep(3)

            # Scroll and load more content
            print("Loading all reviews...")
            for i in range(15):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)

                # Try to click load more
                try:
                    load_more = page.locator("button:has-text('Load'), button:has-text('Show')").first
                    if load_more.is_visible(timeout=500):
                        load_more.click()
                        time.sleep(2)
                except:
                    pass

            html = page.content()
            browser.close()

            soup = BeautifulSoup(html, 'html.parser')
            return extract_reviews_from_soup(soup)

    except ImportError:
        print("Playwright not installed. Install with: pip install playwright && python -m playwright install chromium")
        return None
    except Exception as e:
        print(f"Playwright failed: {e}")
        return None


def method_selenium():
    """Method 2: Use Selenium (fallback)"""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        print("\n[Method 2] Using Selenium...")
        options = Options()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')

        driver = webdriver.Chrome(options=options)
        driver.get(BASE_URL)
        time.sleep(5)

        # Scroll
        for i in range(10):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)

        html = driver.page_source
        driver.quit()

        soup = BeautifulSoup(html, 'html.parser')
        return extract_reviews_from_soup(soup)

    except ImportError:
        print("Selenium not installed. Install with: pip install selenium webdriver-manager")
        return None
    except Exception as e:
        print(f"Selenium failed: {e}")
        return None


def save_to_excel(reviews, filename=OUTPUT_FILE):
    """Save reviews to Excel"""
    if not reviews:
        print("\n❌ No reviews to save!")
        return False

    df = pd.DataFrame(reviews)
    df['scraped_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    df['source_url'] = BASE_URL

    # Reorder columns
    cols_order = ['review_id', 'date', 'rating', 'reviewer_name', 'review_title',
                  'review_text', 'verified', 'helpful_votes', 'scraped_at', 'source_url']
    cols_final = [c for c in cols_order if c in df.columns]
    cols_final += [c for c in df.columns if c not in cols_final]

    df = df[cols_final]

    # Save
    df.to_excel(filename, index=False, engine='openpyxl')

    print(f"\n{'='*60}")
    print(f"✅ SUCCESS! Saved {len(reviews)} reviews to {filename}")
    print(f"{'='*60}")
    print(f"\nColumns: {', '.join(df.columns.tolist())}")

    if 'rating' in df.columns:
        print(f"\n📊 Statistics:")
        print(f"  Total reviews: {len(reviews)}")
        print(f"  Average rating: {df['rating'].mean():.2f}/5.0")
        print(f"  Rating distribution:\n{df['rating'].value_counts().sort_index()}")

    if 'review_text' in df.columns:
        avg_length = df['review_text'].str.len().mean()
        print(f"  Average review length: {avg_length:.0f} characters")

    print(f"\n📝 Sample review:")
    for col in ['date', 'rating', 'reviewer_name', 'review_title']:
        if col in df.columns and len(df) > 0:
            print(f"  {col}: {df[col].iloc[0]}")
    if 'review_text' in df.columns and len(df) > 0:
        text = str(df['review_text'].iloc[0])
        print(f"  review_text: {text[:150]}...")

    return True


def main():
    print("="*60)
    print("PLUM REVIEWS SCRAPER")
    print("="*60)
    print(f"Target: {BASE_URL}")
    print(f"Output: {OUTPUT_FILE}")
    print()

    # Try different methods
    reviews = None

    # Try Playwright first (best method)
    reviews = method_playwright()

    # Try Selenium if Playwright failed
    if not reviews:
        reviews = method_selenium()

    # If all automated methods failed, provide manual instructions
    if not reviews:
        print("\n" + "="*60)
        print("❌ AUTOMATED METHODS FAILED")
        print("="*60)
        print("\nPLEASE TRY THESE OPTIONS:")
        print("\n1. Install Playwright (RECOMMENDED):")
        print("   pip install playwright pandas openpyxl beautifulsoup4")
        print("   python -m playwright install chromium")
        print("   python scrape_plum_reviews_final.py")
        print("\n2. Install Selenium:")
        print("   pip install selenium webdriver-manager pandas openpyxl beautifulsoup4")
        print("   python scrape_plum_reviews_final.py")
        print("\n3. Manual extraction:")
        print("   - Visit the URL in your browser")
        print("   - Right-click -> Save As -> Save complete webpage")
        print("   - Run: python extract_from_html.py <saved_file.html>")
        sys.exit(1)

    # Save results
    if save_to_excel(reviews):
        print(f"\n✅ Done! Open '{OUTPUT_FILE}' to view the reviews.")
    else:
        print("\n❌ Failed to save reviews")
        sys.exit(1)


if __name__ == "__main__":
    main()
