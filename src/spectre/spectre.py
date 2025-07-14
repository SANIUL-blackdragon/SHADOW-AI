
import asyncio
import json
import os
import hashlib
from datetime import datetime, timezone, date, timedelta
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import sqlite3

# --- Configuration ---
BASE_DATA_DIR = Path("D:/LAPTOP/TO_EARN/AI/SHADOW-AI/data/news_logs")
WHITELIST_PATH = Path(__file__).parent / "whitelist.json"
CACHE_PATH = Path(__file__).parent / "cache.json"
DATE_FORMAT_DIR = "%Y/%Y%m/%Y%m%d"
DATE_FORMAT_FILE = "%Y%m%d"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
SCRAPER_VERSION = "1.1.0" # Updated version

# --- Main Scraper Class ---
class Spectre:
    def __init__(self, headless=True):
        self.headless = headless
        self.playwright = None
        self.browser = None

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def scrape_article(self, url: str, cookies_path: str = None):
        context = await self.browser.new_context(user_agent=USER_AGENT)
        if cookies_path and Path(cookies_path).exists():
            with open(cookies_path, 'r') as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)

        page = await context.new_page()
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=90000)
            await page.wait_for_timeout(5000) # Give some extra time for dynamic content
            await page.evaluate('() => { window.scrollTo(0, document.body.scrollHeight); document.querySelectorAll(\'[class*="paywall"], .overlay, [style*="blur"]\').forEach(e => e.remove()); }')
            
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            article_data = self._extract_data(soup, url)
            # Save raw HTML separately, not in the main data dict
            self._save_raw_html(html, article_data['title'])
            
            return article_data
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None
        finally:
            await context.close()

    def _extract_data(self, soup: BeautifulSoup, url: str) -> dict:
        container = soup.find('article') or soup.find('main') or soup.find('div', class_=['article-body', 'content']) or soup.body
        title = (container.find('h1').get_text(strip=True) if container.find('h1') else "No Title Found").strip()
        paragraphs = container.find_all('p')
        content = "\n\n".join(p.get_text(strip=True) for p in paragraphs)
        now_utc = datetime.now(timezone.utc)

        return {
            "TimeOfRelease": now_utc.isoformat(),
            "title": title,
            "url": url,
            "domain": url.split('//')[-1].split('/')[0],
            "scraped_at": now_utc.isoformat(),
            "published_at": None,
            "author": None,
            "content": content,
            "summary": (content[:200] + "...") if content else "",
            "paywall_type": "soft", # Placeholder
            "tags": None,
            "language": "en",
            "word_count": len(content.split()),
            "category": None,
            "scraper_version": SCRAPER_VERSION
        }
        
    def _save_raw_html(self, html: str, title: str):
        """Saves the raw HTML of a scraped page."""
        now = datetime.now(timezone.utc)
        dir_path = BASE_DATA_DIR / now.strftime(DATE_FORMAT_DIR) / "HTML"
        dir_path.mkdir(parents=True, exist_ok=True)
        
        # Sanitize title for filename
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_')).rstrip()
        filename = f"{now.strftime(DATE_FORMAT_FILE)}_{safe_title[:50]}.html"
        
        with open(dir_path / filename, "w", encoding="utf-8") as f:
            f.write(html)

    async def check_for_updates(self, site: dict):
        """Checks if a site has new content."""
        page = await self.browser.new_page()
        try:
            await page.goto(site['url'], wait_until='load', timeout=30000)
            
            # Try to get a more specific set of headlines/links for hashing
            # For Reuters, look for links within specific article containers
            if "reuters.com" in site['url']:
                headlines_elements = await page.query_selector_all('div.media-story-card a[href*="/markets/"]')
                headlines = " ".join([await el.inner_text() for el in headlines_elements])
                primary_link_element = await page.query_selector('div.media-story-card a[href*="/markets/"]')
                primary_link = await primary_link_element.get_attribute('href') if primary_link_element else None
            else: # Generic approach for other sites
                headlines = await page.eval_on_selector_all('h1, h2, h3, a[href*="article"], a[href*="news"]', 'elements => elements.map(e => e.innerText).join(" ").slice(0, 500)')
                primary_link = await page.evaluate("""() => {
                    const links = Array.from(document.querySelectorAll('a'));
                    for (const link of links) {
                        if (link.href && (link.href.includes('/article/') || link.href.includes('/news/')) && !link.href.includes('#')) {
                            return link.href;
                        }
                    }
                    return null;
                }""")

            content_hash = hashlib.sha256(headlines.encode()).hexdigest()
            
            cache = load_cache()
            print(f"Current cache for {site['name']}: {cache.get(site['name'])}")
            print(f"New content hash: {content_hash}")

            if cache.get(site['name']) == content_hash:
                print(f"No changes detected for: {site['name']}")
                return None, False # No new content
            
            print(f"Change detected for {site['name']}. Primary link found: {primary_link}")
            if primary_link:
                cache[site['name']] = content_hash
                save_cache(cache)
                return primary_link, True # New content found
            print(f"No primary link found for {site['name']} despite content change.")
            if primary_link:
                cache[site['name']] = content_hash
                save_cache(cache)
                return primary_link, True # New content found
            return None, False

        except Exception as e:
            print(f"Failed to check for updates at {site['url']}: {e}")
            return None, False
        finally:
            await page.close()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

# --- Filesystem and Data Handling ---
def get_storage_paths(base_dir: Path, date: datetime):
    dir_path = base_dir / date.strftime(DATE_FORMAT_DIR)
    # No need to mkdir here, save_data will do it
    file_base_name = date.strftime(DATE_FORMAT_FILE)
    return {
        "sqlite": dir_path / "SQLITE3" / f"{file_base_name}.db",
        "csv": dir_path / "CSV" / f"{file_base_name}.csv",
        "json": dir_path / "JSON" / f"{file_base_name}.json",
        "txt": dir_path / "TXT" / f"{file_base_name}.txt",
    }

def save_data(data: dict, paths: dict):
    """Saves the scraped data to all specified formats."""
    # Ensure subdirectories exist
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    # --- Save to TXT ---
    txt_line = " || ".join(str(data.get(k, '')) for k in get_schema_fields() if k != 'id')
    with open(paths['txt'], 'a', encoding='utf-8') as f:
        f.write(txt_line + "\n")

    # --- Save to CSV ---
    df = pd.DataFrame([data])
    # Reorder DF to match schema
    df = df[get_schema_fields(exclude_id=True)]
    df.to_csv(paths['csv'], mode='a', header=not paths['csv'].exists(), index=False)

    # --- Save to JSON ---
    json_data = []
    if paths['json'].exists() and paths['json'].stat().st_size > 0:
        with open(paths['json'], 'r', encoding='utf-8') as f:
            try:
                json_data = json.load(f)
            except json.JSONDecodeError:
                pass
    json_data.append(data)
    with open(paths['json'], 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2)

    # --- Save to SQLite ---
    conn = sqlite3.connect(paths['sqlite'])
    # Create table if it doesn't exist
    create_sqlite_table(conn)
    # Remove raw_html if present, it's not part of the schema
    data.pop('raw_html', None)
    df = pd.DataFrame([data])
    df = df[get_schema_fields(exclude_id=True)]
    df.to_sql('daily_articles', conn, if_exists='append', index=False)
    conn.close()

def create_sqlite_table(conn):
    """Creates the daily_articles table with the correct schema if it doesn't exist."""
    schema = get_schema_fields()
    # SQL types mapping
    type_map = {'word_count': 'INTEGER'}
    # Build CREATE TABLE statement
    fields = ", ".join([f"{field} {type_map.get(field, 'TEXT')}" for field in schema])
    fields = fields.replace("id TEXT", "id INTEGER PRIMARY KEY AUTOINCREMENT")
    
    query = f"CREATE TABLE IF NOT EXISTS daily_articles ({fields});"
    conn.execute(query)
    conn.commit()

def get_schema_fields(exclude_id=False):
    fields = [
        "id", "TimeOfRelease", "title", "url", "domain", "scraped_at",
        "published_at", "author", "content", "summary", "paywall_type",
        "tags", "language", "word_count", "category", "scraper_version"
    ]
    return fields[1:] if exclude_id else fields

def check_and_create_missing_dates(base_dir: Path, start_date_str: str = "20120101"):
    """Checks for missing data and creates the directory structure."""
    print("Checking for missing historical data directories...")
    start_date = datetime.strptime(start_date_str, "%Y%m%d").date()
    end_date = date.today()
    
    current_date = start_date
    while current_date <= end_date:
        dt_obj = datetime.combine(current_date, datetime.min.time())
        paths = get_storage_paths(base_dir, dt_obj)
        # Check one path, assume others are similar
        if not list(paths.values())[0].parent.parent.exists():
             print(f"Creating missing directory structure for {current_date.strftime('%Y-%m-%d')}")
             # Create all subdirectories
             for p in paths.values():
                 p.parent.mkdir(parents=True, exist_ok=True)
        current_date += timedelta(days=1)
    print("Directory check complete.")

def load_whitelist():
    if not WHITELIST_PATH.exists():
        return []
    with open(WHITELIST_PATH, 'r') as f:
        return json.load(f)

def load_cache():
    if not CACHE_PATH.exists():
        return {}
    with open(CACHE_PATH, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_cache(data):
    with open(CACHE_PATH, 'w') as f:
        json.dump(data, f, indent=2)

# --- Main Execution ---
async def main():
    check_and_create_missing_dates(BASE_DATA_DIR)
    
    whitelist = load_whitelist()
    if not whitelist:
        print("Whitelist is empty. Exiting.")
        return

    async with Spectre(headless=True) as spectre:
        for site in whitelist:
            print(f"\n--- Checking site: {site['name']} ---")
            article_url, has_changed = await spectre.check_for_updates(site)
            
            if has_changed and article_url:
                print(f"New content found at: {article_url}")
                article_data = await spectre.scrape_article(article_url)
                if article_data:
                    now = datetime.now(timezone.utc)
                    storage_paths = get_storage_paths(BASE_DATA_DIR, now)
                    save_data(article_data, storage_paths)
                    print(f"Successfully scraped and saved: {article_data['title']}")
            elif has_changed:
                print("Change detected, but could not find a primary article link.")

if __name__ == "__main__":
    asyncio.run(main())
