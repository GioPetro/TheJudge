# SmartMoneyPeople Reviews Scraper - Quick Start Guide

## Configuration

Edit the top of `scrape_plum_simple.py`:

```python
# ==================== CONFIGURATION ====================
MIN_REVIEW_YEAR = 2024  # Filter reviews from this year onwards (set to None to get all reviews)

# List of SmartMoneyPeople URLs to scrape
smp_pages = [
    "https://smartmoneypeople.com/plum-reviews/product/app",
    "https://smartmoneypeople.com/monzo-reviews",
    "https://smartmoneypeople.com/revolut-reviews",
]

# Output directory
base_path = 'C:/Users/yourname/reviews/'  # Change to your path
# ======================================================
```

## Usage

### Method 1: Automated (if site allows)
```bash
python scrape_plum_simple.py
```

### Method 2: Manual Download (recommended due to 403 blocks)
1. Open each URL in your browser
2. Scroll down to load ALL reviews
3. Right-click → **Save As** → **Webpage, Complete**
4. Run: `python scrape_plum_simple.py saved_page.html`

## Output

For each URL, you'll get:
- **plum_product_app_reviews.xlsx** - Filtered reviews in Excel format
- **monzo_reviews.xlsx** - etc.

Each file contains:
- review_id
- date
- rating (1-5 stars)
- reviewer_name
- review_title
- review_text
- verified (boolean)
- helpful_votes
- scraped_at
- source_url

## Examples

### Get all reviews from 2024 onwards:
```python
MIN_REVIEW_YEAR = 2024
```

### Get all reviews ever:
```python
MIN_REVIEW_YEAR = None
```

### Multiple products:
```python
smp_pages = [
    "https://smartmoneypeople.com/plum-reviews/product/app",
    "https://smartmoneypeople.com/monzo-reviews",
    "https://smartmoneypeople.com/revolut-reviews",
    "https://smartmoneypeople.com/starling-bank-reviews",
]
```

### Custom output path:
```python
base_path = 'C:/Users/gpetropoulos/OneDrive/Reviews/SmartMoneyPeople/'
```

## Features

✅ Fast (BS4 only, no browser overhead)
✅ Date filtering by year
✅ Multiple URLs in one run
✅ Auto-generated filenames
✅ Handles pagination automatically
✅ Detailed statistics output
✅ Works with saved HTML files

## Troubleshooting

**403 Forbidden Error?**
- Use Method 2 (manual download)
- The site blocks automated requests
- Saving the page manually bypasses this

**No reviews extracted?**
- Check `debug_page.html` to see what was loaded
- Website structure may have changed
- Try with a manually saved page

**Date filtering not working?**
- Check the date format on the page
- Add more date formats to `parse_review_date()` function
