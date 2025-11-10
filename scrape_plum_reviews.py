#!/usr/bin/env python3
"""
Plum Reviews Scraper
Scrapes all reviews from SmartMoneyPeople Plum app reviews page
Uses Selenium for better compatibility with modern websites
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import sys
import os

try:
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.firefox import GeckoDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

# Configuration
BASE_URL = "https://smartmoneypeople.com/plum-reviews/product/app"


def setup_driver(headless=True):
    """Setup Chrome driver with appropriate options"""
    chrome_options = Options()

    if headless:
        chrome_options.add_argument('--headless=new')

    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    # Try Chrome with webdriver-manager
    if WEBDRIVER_MANAGER_AVAILABLE:
        try:
            print("Attempting to use Chrome with webdriver-manager...")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            print("✓ Chrome driver setup successful")
            return driver
        except Exception as e:
            print(f"Chrome with webdriver-manager failed: {e}")

    # Try Chrome without webdriver-manager
    try:
        print("Attempting to use Chrome without webdriver-manager...")
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        print("✓ Chrome driver setup successful")
        return driver
    except Exception as e:
        print(f"Chrome driver failed: {e}")

    # Try Firefox as fallback
    print("\nTrying Firefox as fallback...")
    try:
        from selenium.webdriver.firefox.options import Options as FirefoxOptions
        firefox_options = FirefoxOptions()
        if headless:
            firefox_options.add_argument('--headless')

        if WEBDRIVER_MANAGER_AVAILABLE:
            try:
                service = Service(GeckoDriverManager().install())
                driver = webdriver.Firefox(service=service, options=firefox_options)
                print("✓ Firefox driver setup successful")
                return driver
            except Exception as e:
                print(f"Firefox with webdriver-manager failed: {e}")

        driver = webdriver.Firefox(options=firefox_options)
        print("✓ Firefox driver setup successful")
        return driver
    except Exception as e2:
        print(f"Firefox driver failed: {e2}")

    return None


def fetch_page_selenium(driver, url, wait_time=10):
    """Fetch a page using Selenium"""
    try:
        print(f"Fetching: {url}")
        driver.get(url)

        # Wait for page to load - look for review elements
        try:
            WebDriverWait(driver, wait_time).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except TimeoutException:
            print("Page load timeout, but continuing anyway...")

        # Additional wait for dynamic content
        time.sleep(3)

        # Scroll to load lazy-loaded content
        scroll_page(driver)

        return driver.page_source
    except Exception as e:
        print(f"Error fetching page: {e}")
        return None


def scroll_page(driver, scroll_pause_time=1.5):
    """Scroll through the page to load all lazy-loaded content"""
    # Get initial scroll height
    last_height = driver.execute_script("return document.body.scrollHeight")

    print("Scrolling through page to load all content...")
    scroll_attempts = 0
    max_scrolls = 20  # Prevent infinite scrolling

    while scroll_attempts < max_scrolls:
        # Scroll down to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        # Wait for page to load
        time.sleep(scroll_pause_time)

        # Calculate new scroll height and compare with last scroll height
        new_height = driver.execute_script("return document.body.scrollHeight")

        if new_height == last_height:
            # Try clicking "Load More" or "Show More" button if exists
            try:
                load_more_selectors = [
                    "//button[contains(text(), 'Load more')]",
                    "//button[contains(text(), 'Show more')]",
                    "//a[contains(text(), 'Load more')]",
                    "//a[contains(text(), 'Show more')]",
                    "//button[contains(@class, 'load-more')]",
                    "//a[contains(@class, 'load-more')]"
                ]

                button_clicked = False
                for selector in load_more_selectors:
                    try:
                        button = driver.find_element(By.XPATH, selector)
                        if button.is_displayed():
                            button.click()
                            print("Clicked 'Load More' button")
                            time.sleep(2)
                            button_clicked = True
                            break
                    except:
                        continue

                if not button_clicked:
                    break
            except:
                break

        last_height = new_height
        scroll_attempts += 1

    print(f"Finished scrolling (attempted {scroll_attempts} scrolls)")

    # Scroll back to top
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)


def extract_reviews_from_page(soup):
    """Extract all reviews from a page"""
    reviews = []

    # Find all review containers
    # Common patterns: div.review, article.review, div[class*="review"]
    review_containers = soup.find_all('div', class_=lambda x: x and 'review' in x.lower())

    # If that doesn't work, try other common patterns
    if not review_containers:
        review_containers = soup.find_all('article', class_=lambda x: x and 'review' in x.lower())

    if not review_containers:
        # Try finding by data attributes or other patterns
        review_containers = soup.find_all(attrs={"data-review": True})

    if not review_containers:
        # Last resort: find common review structures
        review_containers = soup.find_all('div', class_=lambda x: x and ('card' in str(x).lower() or 'item' in str(x).lower()))

    print(f"Found {len(review_containers)} potential review containers")

    for container in review_containers:
        review_data = {}

        # Extract rating (look for star ratings, numeric ratings, etc.)
        rating_elem = container.find(class_=lambda x: x and 'rating' in str(x).lower())
        if rating_elem:
            # Try to find numeric rating
            rating_text = rating_elem.get_text(strip=True)
            # Look for patterns like "5 stars", "4.5", etc.
            import re
            rating_match = re.search(r'(\d+(?:\.\d+)?)', rating_text)
            if rating_match:
                review_data['rating'] = float(rating_match.group(1))
            else:
                # Count star elements or look for aria-label
                stars = rating_elem.find_all(class_=lambda x: x and 'star' in str(x).lower())
                if stars:
                    review_data['rating'] = len([s for s in stars if 'filled' in str(s.get('class', [])).lower() or 'active' in str(s.get('class', [])).lower()])
                else:
                    aria_label = rating_elem.get('aria-label', '')
                    rating_match = re.search(r'(\d+(?:\.\d+)?)', aria_label)
                    if rating_match:
                        review_data['rating'] = float(rating_match.group(1))

        # Extract date
        date_elem = container.find(class_=lambda x: x and 'date' in str(x).lower())
        if date_elem:
            review_data['date'] = date_elem.get_text(strip=True)
        else:
            # Try time element
            time_elem = container.find('time')
            if time_elem:
                review_data['date'] = time_elem.get('datetime', time_elem.get_text(strip=True))

        # Extract reviewer name
        author_elem = container.find(class_=lambda x: x and ('author' in str(x).lower() or 'name' in str(x).lower()))
        if author_elem:
            review_data['reviewer_name'] = author_elem.get_text(strip=True)

        # Extract review title
        title_elem = container.find(['h2', 'h3', 'h4'], class_=lambda x: x and ('title' in str(x).lower() or 'heading' in str(x).lower()))
        if title_elem:
            review_data['review_title'] = title_elem.get_text(strip=True)

        # Extract review text/content
        content_elem = container.find(class_=lambda x: x and ('content' in str(x).lower() or 'text' in str(x).lower() or 'body' in str(x).lower()))
        if content_elem:
            review_data['review_text'] = content_elem.get_text(strip=True)
        else:
            # Try to get all paragraph text
            paragraphs = container.find_all('p')
            if paragraphs:
                review_data['review_text'] = ' '.join([p.get_text(strip=True) for p in paragraphs])

        # Extract helpful votes if available
        helpful_elem = container.find(class_=lambda x: x and 'helpful' in str(x).lower())
        if helpful_elem:
            review_data['helpful_votes'] = helpful_elem.get_text(strip=True)

        # Extract verification status
        verified_elem = container.find(class_=lambda x: x and 'verified' in str(x).lower())
        if verified_elem:
            review_data['verified'] = True
        else:
            review_data['verified'] = False

        # Only add if we have at least review text or rating
        if review_data.get('review_text') or review_data.get('rating'):
            reviews.append(review_data)

    return reviews


def get_pagination_urls(soup, base_url):
    """Find all pagination URLs"""
    pagination_urls = []

    # Find pagination elements
    pagination = soup.find(class_=lambda x: x and 'pagination' in str(x).lower())
    if pagination:
        # Find all page links
        page_links = pagination.find_all('a', href=True)
        for link in page_links:
            href = link['href']
            # Make absolute URL if relative
            if href.startswith('/'):
                href = 'https://smartmoneypeople.com' + href
            elif not href.startswith('http'):
                href = base_url + '/' + href

            if href not in pagination_urls and 'plum-reviews' in href:
                pagination_urls.append(href)

    # Also look for "next" button
    next_button = soup.find('a', class_=lambda x: x and 'next' in str(x).lower())
    if next_button and next_button.get('href'):
        href = next_button['href']
        if href.startswith('/'):
            href = 'https://smartmoneypeople.com' + href
        if href not in pagination_urls:
            pagination_urls.append(href)

    return pagination_urls


def scrape_all_reviews():
    """Main function to scrape all reviews"""
    all_reviews = []

    # Setup Selenium driver
    print("Setting up browser...")
    driver = setup_driver(headless=True)

    if not driver:
        print("Failed to setup browser driver. Please install Chrome/Chromium or Firefox.")
        print("\nFor Chrome/Chromium:")
        print("  sudo apt-get install chromium-browser chromium-chromedriver")
        print("\nFor Firefox:")
        print("  sudo apt-get install firefox geckodriver")
        return []

    try:
        visited_urls = set()
        urls_to_visit = [BASE_URL]

        while urls_to_visit:
            current_url = urls_to_visit.pop(0)

            # Skip if already visited
            if current_url in visited_urls:
                continue

            visited_urls.add(current_url)

            # Fetch page
            page_source = fetch_page_selenium(driver, current_url)
            if not page_source:
                print(f"Failed to fetch {current_url}")
                continue

            # Parse HTML
            soup = BeautifulSoup(page_source, 'html.parser')

            # Extract reviews
            print(f"Extracting reviews from: {current_url}")
            reviews = extract_reviews_from_page(soup)
            print(f"Extracted {len(reviews)} reviews from this page")
            all_reviews.extend(reviews)

            # Find pagination links
            pagination_urls = get_pagination_urls(soup, current_url)
            for url in pagination_urls:
                if url not in visited_urls:
                    urls_to_visit.append(url)

            # Be respectful - wait between requests
            if urls_to_visit:
                time.sleep(2)

    finally:
        # Clean up
        print("Closing browser...")
        driver.quit()

    return all_reviews


def save_to_excel(reviews, filename='plum_reviews.xlsx'):
    """Save reviews to Excel file"""
    if not reviews:
        print("No reviews to save!")
        return

    # Create DataFrame
    df = pd.DataFrame(reviews)

    # Add metadata columns
    df['scraped_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    df['source_url'] = BASE_URL

    # Reorder columns for better readability
    column_order = ['date', 'rating', 'reviewer_name', 'review_title', 'review_text',
                    'verified', 'helpful_votes', 'scraped_at', 'source_url']

    # Only include columns that exist
    existing_columns = [col for col in column_order if col in df.columns]
    other_columns = [col for col in df.columns if col not in column_order]
    final_columns = existing_columns + other_columns

    df = df[final_columns]

    # Save to Excel
    df.to_excel(filename, index=False, engine='openpyxl')
    print(f"\n✓ Saved {len(reviews)} reviews to {filename}")
    print(f"\nColumns in Excel file: {', '.join(df.columns)}")
    print(f"\nPreview of first review:")
    print(df.head(1).to_string())


def main():
    print("=" * 60)
    print("Plum Reviews Scraper")
    print("=" * 60)
    print(f"Target URL: {BASE_URL}")
    print()

    # Scrape all reviews
    reviews = scrape_all_reviews()

    if not reviews:
        print("\n⚠ No reviews were extracted!")
        print("The website structure might have changed or be different than expected.")
        print("You may need to inspect the page manually and adjust the selectors.")
        sys.exit(1)

    # Save to Excel
    save_to_excel(reviews)

    print(f"\n✓ Scraping completed successfully!")
    print(f"Total reviews collected: {len(reviews)}")


if __name__ == "__main__":
    main()
