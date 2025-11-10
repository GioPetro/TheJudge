# Plum Reviews Scraper

Scrapes all reviews from SmartMoneyPeople's Plum app review page and exports them to Excel.

## Quick Start

```bash
# Install dependencies
pip install playwright pandas openpyxl beautifulsoup4

# Install browser
python -m playwright install chromium

# Run scraper
python scrape_plum_reviews_final.py
```

## Output

The script creates `plum_reviews.xlsx` with the following columns:

- **review_id**: Unique identifier for each review
- **date**: When the review was posted
- **rating**: Star rating (1-5)
- **reviewer_name**: Name of the reviewer
- **review_title**: Title/heading of the review
- **review_text**: Full review content
- **verified**: Whether the review is verified
- **helpful_votes**: Number of helpful votes
- **scraped_at**: Timestamp of when data was scraped
- **source_url**: URL of the source page

## Installation Options

### Option 1: Playwright (Recommended)

Playwright is the most reliable method as it handles JavaScript and dynamic content.

```bash
pip install playwright pandas openpyxl beautifulsoup4 lxml
python -m playwright install chromium
python scrape_plum_reviews_final.py
```

### Option 2: Selenium

If Playwright doesn't work, try Selenium:

```bash
pip install selenium webdriver-manager pandas openpyxl beautifulsoup4 lxml
python scrape_plum_reviews_final.py
```

### Option 3: Run Locally

If you're in a restricted environment, you can:

1. Download all scripts to your local machine
2. Install dependencies there
3. Run the scraper locally

## Files

- `scrape_plum_reviews_final.py` - Main scraper script (recommended)
- `scrape_plum_reviews_playwright.py` - Playwright-only version
- `scrape_plum_reviews.py` - Selenium-only version
- `requirements_scraper.txt` - Python dependencies

## Troubleshooting

### Browser Installation Issues

If you get browser download errors:

```bash
# For Playwright
python -m playwright install --with-deps chromium

# For Selenium on Ubuntu/Debian
sudo apt-get install chromium-browser chromium-chromedriver

# For Selenium on Mac
brew install chromium chromedriver
```

### 403 Forbidden Errors

The website has bot protection. The scripts use:
- Realistic user agents
- Browser automation (Playwright/Selenium)
- Proper scrolling and wait times

If you still get blocked:
1. Try running from a different network
2. Add delays between requests
3. Use the manual method below

### Manual Method

If automated scraping fails:

1. Open the page in your browser
2. Scroll to load all reviews
3. Right-click → "Save As" → Save complete webpage
4. Use the saved HTML file with BeautifulSoup to extract data

```python
from bs4 import BeautifulSoup

with open('saved_page.html', 'r') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')
    # Extract reviews using extract_reviews_from_soup() function
```

## Features

- ✅ Scrapes ALL reviews (handles pagination and lazy loading)
- ✅ Extracts comprehensive data (rating, date, text, author, etc.)
- ✅ Exports to Excel format
- ✅ Multiple extraction strategies for robustness
- ✅ Detailed logging and debugging output
- ✅ Saves debug HTML for troubleshooting
- ✅ Handles dynamic content loading
- ✅ Automatic scrolling to load lazy-loaded content
- ✅ Clicks "Load More" buttons automatically

## Example Output

```
==============================================================
PLUM REVIEWS SCRAPER
==============================================================
Target: https://smartmoneypeople.com/plum-reviews/product/app
Output: plum_reviews.xlsx

[Method 1] Using Playwright...
Loading https://smartmoneypeople.com/plum-reviews/product/app...
Loading all reviews...
✓ Saved page HTML to debug_page.html
Found 156 potential containers using div class
Processing 156 containers...

============================================================
✅ SUCCESS! Saved 156 reviews to plum_reviews.xlsx
============================================================

📊 Statistics:
  Total reviews: 156
  Average rating: 4.3/5.0
  Rating distribution:
    5.0    89
    4.0    32
    3.0    18
    2.0     9
    1.0     8
```

## Legal & Ethical Considerations

- This scraper is for educational and analytical purposes
- Always respect the website's robots.txt file
- Add delays between requests to avoid overloading servers
- Consider using the website's API if available
- Review the website's Terms of Service before scraping

## Support

If you encounter issues:

1. Check `debug_page.html` to see what was loaded
2. Verify the website structure hasn't changed
3. Try different installation options above
4. Run with increased verbosity/logging

## Dependencies

```txt
playwright>=4.15.0
selenium>=4.15.0
webdriver-manager>=4.0.0
beautifulsoup4>=4.12.0
pandas>=2.0.0
openpyxl>=3.1.0
lxml>=4.9.0
```
