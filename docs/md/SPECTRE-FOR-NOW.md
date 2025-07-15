# S.P.E.C.T.R.E. FOR NOW

This document details the current implementation and immediate goals for the S.P.E.C.T.R.E. module within the SHADOW AI MVP, as outlined for the Notamedia Hackathon 2025. While the full S.P.E.C.T.R.E. module involves complex news scraping with TOR/proxy rotation, the MVP focuses on a simplified approach to enable F.L.A.R.E. functionality.

## Core Functionality (MVP)

Even though the full S.P.E.C.T.R.E. module involves complex news scraping with TOR/proxy rotation, the MVP focuses on a simplified approach to enable F.L.A.R.E. functionality. The S.P.E.C.T.R.E. module, in its current MVP form, is designed to perform the following key tasks:

### 1. JS-Rendered Page Support

**What it does:**
- Spins up a headless browser (Playwright) that loads the page exactly like Chrome, including all JavaScript.
- Waits until network activity quiets down (`networkidle`) so dynamically injected articles are fully available.

**Why it matters:**
- Many news sites (e.g., BBC, Reuters, NYT) only render their article HTML client-side. Static requests miss that content.

**Implementation Details (from `src/spectre/spectre.py`):**
- Uses `playwright.chromium.launch(headless=self.headless)` to launch a browser instance.
- Navigates to URLs using `page.goto(url, wait_until='domcontentloaded', timeout=90000)`.
- Includes a `page.wait_for_timeout(5000)` to allow extra time for dynamic content.

### 2. Soft/Overlay Paywall Bypass

**What it does:**
- Automatically scrolls the page to trigger lazy loads.
- Injects JavaScript to remove paywall overlays, modal dialogs, or CSS blurs that hide content.

**Why it matters:**
- Soft paywalls use front-end tricks to hide text—but the text is already in the DOM. Stripping the trappings reveals the full article.

**Implementation Details (from `src/spectre/spectre.py`):**
- Executes JavaScript on the page: `await page.evaluate('() => { window.scrollTo(0, document.body.scrollHeight); document.querySelectorAll('[class*="paywall"], .overlay, [style*="blur"]').forEach(e => e.remove()); }')`

### 3. Cookie-Based Login Injection (Hard Paywalls)

**What it does:**
- Loads exported Chrome cookies (JSON) into the Playwright context before navigation.
- Allows access to paywalled articles on sites that require a valid session (e.g., WSJ, FT, Economist).

**Why it matters:**
- These sites won’t even send full HTML until they see a login cookie. This method skips login automation.

**Implementation Details (from `src/spectre/spectre.py`):**
- Checks for `cookies_path` and if it exists, loads cookies:
  ```python
  if cookies_path and Path(cookies_path).exists():
      with open(cookies_path, 'r') as f:
          cookies = json.load(f)
      await context.add_cookies(cookies)
  ```

### 4. Clean Article Extraction & Optional Raw HTML Save

**What it does:**
- **Raw Save:** Writes the fully rendered HTML (`page.content()`) to a file for archive or debugging.
- **Clean Extract:** Parses that HTML with BeautifulSoup to isolate only the article text—no navbars, ads, footers.

**Why it matters:**
- Provides both a snapshot of the exact frontend the user would see and a stripped-down clean version for ingestion into databases or LLMs.

**Implementation Details (from `src/spectre/spectre.py`):**
- Retrieves HTML content: `html = await page.content()`
- Uses `BeautifulSoup` for parsing: `soup = BeautifulSoup(html, 'html.parser')`
- Extracts content from common article containers: `container = soup.find('article') or soup.find('main') or soup.find('div', class_=['article-body', 'content']) or soup.body`
- Joins paragraphs to form content: `content = "\n\n".join(p.get_text(strip=True) for p in paragraphs)`
- Saves raw HTML to `BASE_DATA_DIR / now.strftime(DATE_FORMAT_DIR) / "HTML"` with a sanitized filename.

### 5. Real-Time Change Detection on a Whitelist and Historical Data Check

**What it does:**
- Maintains a JSON “whitelist” of sites.
- On each run, fetches either the site’s RSS feed or its homepage/category page and identifies the top article’s URL (or hashes the page’s headline list).
- Compares against the last-seen URL/hash (stored locally). If it’s new, triggers the full scrape; if not, skips it.
- Checks for missing historical data directories and creates them if needed.

**Why it matters:**
- Avoids wasting cycles or risking bans by re-scraping unchanged pages. Only scrapes when actual new content appears.
- Ensures data integrity and a complete historical record.

**Implementation Details (from `src/spectre/spectre.py`):**
- `load_whitelist()` and `load_cache()` functions manage site whitelist and content hashes.
- `check_for_updates()` method compares current content hash with cached hash.
- `check_and_create_missing_dates()` ensures the correct directory structure for historical data from `20120101` to the current date.

### 6. Structured JSON Output with Metadata

**What it does:**
- Packages the scraped article into a JSON object with various fields.
- Saves data to multiple formats: TXT, CSV, JSON, and SQLite.

**Why it matters:**
- Downstream systems (summarizers, alert bots, dashboards) need structured data, not raw HTML dumps.
- Multiple formats ensure data redundancy and flexibility for different uses.

**Implementation Details (from `src/spectre/spectre.py`):**
- `_extract_data()` method constructs a dictionary with fields like `TimeOfRelease`, `title`, `url`, `domain`, `content`, `summary`, `scraper_version`, etc.
- `save_data()` function handles saving the extracted data to:
    - **TXT:** Each record as a line with `||` as a separator.
    - **CSV:** Standard CSV format with header.
    - **JSON:** JSON array of article objects.
    - **SQLITE3:** `daily_articles` table with `id INTEGER PRIMARY KEY AUTOINCREMENT` and other fields.

## Filesystem Structure & Format Rules

S.P.E.C.T.R.E. tracks daily news data from Jan 2012 to today, in UTC+0, saving in 4 formats for redundancy: `.db` (SQLite), `.csv`, `.json`, and `.txt`.

### Date-Based Directory Layout

Under the root directory: `root\data\news_logs\`

Each level follows this naming pattern:

```
root\data\news_logs\
├── YYYY\
│   ├── YYYYMM\
│   │   ├── YYYYMMDD\
│   │   │   ├── SQLITE3\
│   │   │   │   └── YYYYMMDD.db
│   │   │   ├── CSV\
│   │   │   │   └── YYYYMMDD.csv
│   │   │   ├── JSON\
│   │   │   │   └── YYYYMMDD.json
│   │   │   └── TXT\
│   │   │       └── YYYYMMDD.txt
```

**Notes:**
- Year folders = `YYYY`
- Month folders = `YYYYMM`
- Day folders = `YYYYMMDD`
- Timezone = Always saved in **UTC+0**
- For each day, the **same content is saved in all 4 formats**, in their respective subfolders.

### File Content Schema

All 4 formats (TXT, JSON, CSV, DB) must include these fields:

```
TimeOfRelease (UTC+0)
title
url
domain
scraped_at
published_at
author
content
summary
paywall_type
tags
language
word_count
category
scraper_version
```

**Additional rule for `.db`:**
- Includes an `id INTEGER PRIMARY KEY AUTOINCREMENT` column.

### Formatting Specifics Per File Type

#### 1. `TXT` File:
- Stored as a **multi-record log**
- Each record is a line:
  ```
  TimeOfRelease || title || url || domain || scraped_at || published_at || author || content || summary || paywall_type || tags || language || word_count || category || scraper_version
  ```
- Fields are separated by `||`
- Unicode-safe, plain text

#### 2. `CSV` File:
- Standard comma-separated values with UTF-8 encoding
- Header included
- Multiline `content` and `summary` fields properly quoted

#### 3. `JSON` File:
- JSON array of article objects:
```json
[
  {
    "TimeOfRelease": "2025-07-14T16:30:00Z",
    "title": "...",
    "url": "...",
    ...
  },
  {
    ...
  }
]
```

#### 4. `SQLITE3` File:
- Table name: `daily_articles`
- Schema:
```sql
CREATE TABLE daily_articles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  TimeOfRelease TEXT,
  title TEXT,
  url TEXT,
  domain TEXT,
  scraped_at TEXT,
  published_at TEXT,
  author TEXT,
  content TEXT,
  summary TEXT,
  paywall_type TEXT,
  tags TEXT,
  language TEXT,
  word_count INTEGER,
  category TEXT,
  scraper_version TEXT
);
```

### Missing Data Check

The script must:
1. **Iterate from `20120101` → current UTC date**
2. **Check which days are missing any folder or any file inside those folders**
3. Log or recreate missing structure as needed.

### Example Filename:

For July 14, 2025 (UTC):

```
root\data\news_logs\2025\202507\20250714\
├── SQLITE3\20250714.db
├── CSV\20250714.csv
├── TXT\20250714.txt
├── JSON\20250714.json
```