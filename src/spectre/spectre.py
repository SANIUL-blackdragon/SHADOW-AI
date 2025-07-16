import asyncio
import json
import os
import hashlib
import re
import random
from datetime import datetime, timezone, date, timedelta
from pathlib import Path
import pandas as pd
import feedparser #type: ignore
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, BrowserContext, Page
import sqlite3
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, urljoin

# --- Configuration ---
BASE_DATA_DIR = Path("D:/LAPTOP/TO_EARN/AI/SHADOW-AI/data/news_logs")
WHITELIST_PATH = Path(__file__).parent / "whitelist.json"
CACHE_PATH = Path(__file__).parent / "cache.json"
DATE_FORMAT_DIR = "%Y/%Y%m/%Y%m%d"
DATE_FORMAT_FILE = "%Y%m%d"
SCRAPER_VERSION = "2.0.2"

# List of user agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:99.0) Gecko/20100101 Firefox/99.0",
]

# Content quality constants
MIN_CONTENT_LENGTH = 100
MIN_WORD_COUNT = 20
MAX_CACHE_SIZE = 1000

# Prompt configurations for handling various website prompts
PROMPT_CONFIGS = [
    # BBC-specific terms and privacy banner
    {
        'prompt_locator': 'text="We’ve updated our terms"',
        'action_locator': 'button, a >> text="Continue"'
    },
    {
        'prompt_locator': 'text="terms and privacy policy"',
        'action_locator': 'button, a >> text="Continue"'
    },
    # General terms and privacy updates
    {
        'prompt_locator': 'text="updated our terms"',
        'action_locator': 'button, a >> text="Continue" || text="Accept" || text=" Agree"'
    },
    {
        'prompt_locator': 'text="terms and conditions"',
        'action_locator': 'button, a >> text="Accept" || text="I Agree"'
    },
    {
        'prompt_locator': 'text="privacy policy"',
        'action_locator': 'button, a >> text=" Agree" || text="OK"'
    },
    # Cookie consents
    {
        'prompt_locator': 'text="use cookies"',
        'action_locator': 'button, a >> text="Accept" || text="Accept All"'
    },
    {
        'prompt_locator': 'text="cookie policy"',
        'action_locator': 'button, a >> text="I agree" || text="OK"'
    },
    {
        'prompt_locator': 'text="cookie"',
        'action_locator': 'button, a >> text="OK" || text="Accept"'
    },
    {
        'prompt_locator': 'text="accept cookies"',
        'action_locator': 'button, a >> text="Accept All" || text="Accept"'
    },
    {
        'prompt_locator': 'text="manage cookies"',
        'action_locator': 'button, a >> text="Save" || text="Accept"'
    },
    # Newsletter sign-ups
    {
        'prompt_locator': 'text="newsletter"',
        'action_locator': 'button, a >> text="Close" || text="Dismiss"'
    },
    {
        'prompt_locator': 'text="subscribe"',
        'action_locator': 'button, a >> text="No thanks" || text="Dismiss"'
    },
    {
        'prompt_locator': 'text="sign up"',
        'action_locator': 'button, a >> text="Dismiss" || text="No Thanks"'
    },
    # Age verification
    {
        'prompt_locator': 'text="over 18"',
        'action_locator': 'button, a >> text="Yes" || text="Enter"'
    },
    {
        'prompt_locator': 'text="age verification"',
        'action_locator': 'button, a >> text="Enter" || text="Confirm"'
    },
    {
        'prompt_locator': 'text="are you 21"',
        'action_locator': 'button, a >> text="Confirm" || text="Yes"'
    },
    # Other common prompts
    {
        'prompt_locator': 'text="welcome"',
        'action_locator': 'button, a >> text="Dismiss" || text="Close"'
    },
    {
        'prompt_locator': 'text="notification"',
        'action_locator': 'button, a >> text="Allow" || text="Deny"'
    },
    {
        'prompt_locator': 'text="pop-up"',
        'action_locator': 'button, a >> text="Got it" || text="Close"'
    },
    {
        'prompt_locator': 'text="survey"',
        'action_locator': 'button, a >> text="Not now" || text="Dismiss"'
    },
]

# --- Simplified Scraper Class ---
class Spectre:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.scraped_urls = set()
        
    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--no-sandbox',
                '--disable-dev-shm-usage'
            ]
        )

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def handle_prompts(self, page: Page):
        """Handle known prompts like terms acceptance, cookie banners, etc."""
        for _ in range(2):  # Try twice to catch delayed prompts
            for config in PROMPT_CONFIGS:
                try:
                    prompt = page.locator(config['prompt_locator'])
                    if await prompt.count() > 0:
                        action_button = page.locator(config['action_locator'])
                        if await action_button.count() > 0:
                            await action_button.click()
                            await page.wait_for_timeout(2000)
                            print(f"Handled prompt: {config['prompt_locator']}")
                except Exception as e:
                    print(f"Error handling prompt {config['prompt_locator']}: {e}")
            await page.wait_for_timeout(1000)

    async def scrape_article(self, url: str, cookies_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Scrape full article content from a URL."""
        if not self.browser:
            return None
            
        url_hash = hashlib.md5(url.encode()).hexdigest()
        if url_hash in self.scraped_urls:
            print(f"Duplicate URL detected, skipping: {url}")
            return None
        
        user_agent = random.choice(USER_AGENTS)
        context: BrowserContext = await self.browser.new_context(
            user_agent=user_agent,
            viewport={'width': 1920, 'height': 1080}
        )
        
        if cookies_path and Path(cookies_path).exists():
            with open(cookies_path, 'r') as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)

        page: Page = await context.new_page()
        
        try:
            print(f"Loading page: {url}")
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_timeout(5000)
            await self.handle_prompts(page)
            html_source = await page.content()
            screenshot_path = BASE_DATA_DIR / "debug" / f"{url_hash}.png"
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(screenshot_path))
            print(f"Saved screenshot for debugging: {screenshot_path}")
            self._save_page_source(html_source, url)
            print("Extracting all visible text from rendered page...")
            all_text = await page.evaluate("""() => {
                const scripts = document.querySelectorAll('script, style, noscript');
                scripts.forEach(el => el.remove());
                return document.body ? document.body.innerText : '';
            }""")
            title = await self._extract_title_from_page(page)
            cleaned_text = self._clean_extracted_text(all_text)
            article_data = self._create_article_data(
                title=title,
                content=cleaned_text,
                url=url,
                html_source=html_source
            )
            if not self._validate_content_quality(article_data):
                print(f"Content quality validation failed for {url}")
                return None
            self.scraped_urls.add(url_hash)
            print(f"Successfully scraped: {title[:100]}...")
            return article_data
            
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None
        finally:
            await context.close()

    async def _extract_title_from_page(self, page: Page) -> str:
        try:
            title = await page.evaluate("""() => {
                const h1 = document.querySelector('h1');
                if (h1 && h1.textContent.trim()) return h1.textContent.trim();
                const titleTag = document.querySelector('title');
                if (titleTag && titleTag.textContent.trim()) return titleTag.textContent.trim();
                const ogTitle = document.querySelector('meta[property="og:title"]');
                if (ogTitle && ogTitle.getAttribute('content')) return ogTitle.getAttribute('content');
                const metaTitle = document.querySelector('meta[name="title"]');
                if (metaTitle && metaTitle.getAttribute('content')) return metaTitle.getAttribute('content');
                return 'No Title Found';
            }""")
            return title[:200] if title else "No Title Found"
        except Exception as e:
            print(f"Error extracting title: {e}")
            return "No Title Found"

    def _clean_extracted_text(self, raw_text: str) -> str:
        if not raw_text:
            return ""
        lines = raw_text.split('\n')
        cleaned_lines = [re.sub(r'\s+', ' ', line.strip()) for line in lines if len(line.strip()) > 10]
        return '\n\n'.join(cleaned_lines)

    def _create_article_data(self, title: str, content: str, url: str, html_source: Optional[str] = None) -> Dict[str, Any]:
        now_utc = datetime.now(timezone.utc)
        return {
            "title": title,
            "content": content,
            "summary": self._generate_summary(content),
            "published_at": None,
            "author": None,
            "url": url,
            "domain": urlparse(url).netloc,
            "scraped_at": now_utc.isoformat(),
            "word_count": len(content.split()) if content else 0,
            "scraper_version": SCRAPER_VERSION,
            "language": self._detect_language(content),
            "category": self._classify_content(content),
            "paywall_detected": False,
            "tags": None,
            "TimeOfRelease": now_utc.isoformat(),
            "paywall_type": "none"
        }

    def _generate_summary(self, content: str) -> str:
        if not content:
            return ""
        sentences = content.split('.')
        summary = '. '.join(sentences[:3]) + '.' if len(sentences) > 3 else content
        return summary[:300] + "..." if len(summary) > 300 else summary

    def _detect_language(self, content: str) -> str:
        if not content:
            return "unknown"
        common_english_words = ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']
        content_lower = content.lower()
        english_word_count = sum(1 for word in common_english_words if word in content_lower)
        return "en" if english_word_count > 3 else "unknown"

    def _classify_content(self, content: str) -> Optional[str]:
        if not content:
            return None
        content_lower = content.lower()
        categories = {
            'technology': ['technology', 'tech', 'software', 'computer', 'digital', 'ai', 'artificial intelligence'],
            'business': ['business', 'economy', 'market', 'finance', 'stock', 'investment', 'company'],
            'politics': ['politics', 'government', 'election', 'policy', 'political', 'parliament'],
            'sports': ['sports', 'football', 'basketball', 'tennis', 'soccer', 'game', 'match'],
            'health': ['health', 'medical', 'doctor', 'hospital', 'medicine', 'treatment', 'disease']
        }
        for category, keywords in categories.items():
            if any(keyword in content_lower for keyword in keywords):
                return category
        return None

    def _validate_content_quality(self, article_data: Dict[str, Any]) -> bool:
        content = article_data.get('content', '')
        if len(content) < MIN_CONTENT_LENGTH or article_data.get('word_count', 0) < MIN_WORD_COUNT:
            return False
        title = article_data.get('title', '')
        if not title or title == "No Title Found" or len(title) < 10:
            return False
        return True

    def _save_page_source(self, html_source: str, url: str):
        now = datetime.now(timezone.utc)
        dir_path = BASE_DATA_DIR / now.strftime(DATE_FORMAT_DIR) / "HTML"
        dir_path.mkdir(parents=True, exist_ok=True)
        domain = urlparse(url).netloc
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        filename = f"{now.strftime(DATE_FORMAT_FILE)}_{domain}_{url_hash}.html"
        with open(dir_path / filename, "w", encoding="utf-8") as f:
            metadata_header = f"""<!--
URL: {url}
Scraped: {now.isoformat()}
Scraper Version: {SCRAPER_VERSION}
Source: Raw page source (view-source: equivalent)
-->
"""
            f.write(metadata_header + html_source)

    async def get_latest_article(self, site: Dict[str, Any]) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Get the latest article data or URL based on site type."""
        if not self.browser:
            return None, None
        
        if site['type'] == 'rss_full':
            try:
                print(f"Checking RSS feed (full content): {site['name']}")
                feed = feedparser.parse(site['url'])
                if not feed.entries:
                    print(f"No entries found in RSS feed: {site['name']}")
                    return None, None
                latest_entry = feed.entries[0]
                article_url = latest_entry.get('link')
                if not article_url:
                    print(f"No valid link found in RSS feed: {site['name']}")
                    return None, None
                cache = load_cache()
                cache_key = f"{site['name']}_latest_url"
                if cache.get(cache_key) == article_url:
                    print(f"No changes detected for: {site['name']}")
                    return None, None
                title = latest_entry.get('title', 'No Title Found')
                content = latest_entry.get('content', [{}])[0].get('value', latest_entry.get('description', ''))
                soup = BeautifulSoup(content, 'html.parser')
                cleaned_text = soup.get_text(separator='\n')
                article_data = self._create_article_data(
                    title=title,
                    content=cleaned_text,
                    url=article_url,
                    html_source=None
                )
                if self._validate_content_quality(article_data):
                    cache[cache_key] = article_url
                    save_cache(cache)
                    return article_data, None
                else:
                    print(f"Content quality validation failed for RSS article: {article_url}")
                    return None, None
            except Exception as e:
                print(f"Failed to check RSS feed {site['url']}: {e}")
                return None, None
        
        elif site['type'] == 'rss':
            try:
                print(f"Checking RSS feed: {site['name']}")
                feed = feedparser.parse(site['url'])
                if not feed.entries:
                    print(f"No entries found in RSS feed: {site['name']}")
                    return None, None
                latest_entry = feed.entries[0]
                article_url = latest_entry.get('link')
                if not article_url:
                    print(f"No valid link found in RSS feed: {site['name']}")
                    return None, None
                cache = load_cache()
                cache_key = f"{site['name']}_latest_url"
                if cache.get(cache_key) == article_url:
                    print(f"No changes detected for: {site['name']}")
                    return None, None
                cache[cache_key] = article_url
                save_cache(cache)
                return None, article_url
            except Exception as e:
                print(f"Failed to check RSS feed {site['url']}: {e}")
                return None, None
        
        else:  # homepage or topic
            user_agent = random.choice(USER_AGENTS)
            context = await self.browser.new_context(user_agent=user_agent)
            page = await context.new_page()
            try:
                print(f"Checking for updates: {site['name']}")
                await page.goto(site['url'], wait_until='domcontentloaded', timeout=60000)
                await page.wait_for_timeout(3000)
                await self.handle_prompts(page)
                page_content = await page.content()
                content_hash = hashlib.sha256(page_content.encode()).hexdigest()
                cache = load_cache()
                if cache.get(site['name']) == content_hash:
                    print(f"No changes detected for: {site['name']}")
                    return None, None
                if "bbc.com" in site['url']:
                    primary_link = await page.evaluate("""() => {
                        const links = Array.from(document.querySelectorAll('a[href]'));
                        for (const link of links) {
                            const href = link.getAttribute('href');
                            if (href && href.includes('/news/articles/') && !href.includes('#') && !href.includes('javascript:')) {
                                return href;
                            }
                        }
                        return null;
                    }""")
                else:
                    primary_link = await page.evaluate("""() => {
                        const links = Array.from(document.querySelectorAll('a[href]'));
                        for (const link of links) {
                            const href = link.getAttribute('href');
                            if (href && (
                                href.includes('/article/') || 
                                href.includes('/news/') || 
                                href.includes('/story/') ||
                                href.includes('/post/')
                            ) && !href.includes('#') && !href.includes('javascript:')) {
                                return href;
                            }
                        }
                        return null;
                    }""")
                if primary_link:
                    if not primary_link.startswith('http'):
                        primary_link = urljoin(site['url'], primary_link)
                    cache[site['name']] = content_hash
                    save_cache(cache)
                    return None, primary_link
                return None, None
            except Exception as e:
                print(f"Failed to check for updates at {site['url']}: {e}")
                return None, None
            finally:
                await context.close()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

# --- Filesystem and Data Handling Functions ---
def get_storage_paths(base_dir: Path, date: datetime) -> Dict[str, Path]:
    dir_path = base_dir / date.strftime(DATE_FORMAT_DIR)
    file_base_name = date.strftime(DATE_FORMAT_FILE)
    return {
        "sqlite": dir_path / "SQLITE3" / f"{file_base_name}.db",
        "csv": dir_path / "CSV" / f"{file_base_name}.csv",
        "json": dir_path / "JSON" / f"{file_base_name}.json",
        "txt": dir_path / "TXT" / f"{file_base_name}.txt",
    }

def save_data(data: Dict[str, Any], paths: Dict[str, Path]):
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    try:
        save_to_txt(data, paths['txt'])
        save_to_csv(data, paths['csv'])
        save_to_json(data, paths['json'])
        save_to_sqlite(data, paths['sqlite'])
        print(f"Successfully saved data to all formats")
    except Exception as e:
        print(f"Error saving data: {e}")

def validate_data_before_saving(data: Dict[str, Any]) -> bool:
    required_fields = ['title', 'content', 'url', 'scraped_at']
    for field in required_fields:
        if field not in data or not data[field]:
            return False
    if len(data.get('content', '')) < MIN_CONTENT_LENGTH or data.get('word_count', 0) < MIN_WORD_COUNT:
        return False
    return True

def save_to_txt(data: Dict[str, Any], path: Path):
    fields = get_schema_fields(exclude_id=True)
    txt_line = " || ".join(str(data.get(k, '')) for k in fields)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(txt_line + "\n")

def save_to_csv(data: Dict[str, Any], path: Path):
    df = pd.DataFrame([data])
    df = df[get_schema_fields(exclude_id=True)]
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str)
    df.to_csv(path, mode='a', header=not path.exists(), index=False, encoding='utf-8')

def save_to_json(data: Dict[str, Any], path: Path):
    json_data = []
    if path.exists() and path.stat().st_size > 0:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
        except json.JSONDecodeError:
            json_data = []
    json_data.append(data)
    if len(json_data) > MAX_CACHE_SIZE:
        json_data = json_data[-MAX_CACHE_SIZE:]
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

def save_to_sqlite(data: Dict[str, Any], path: Path):
    conn = sqlite3.connect(path)
    try:
        create_sqlite_table(conn)
        clean_data = {k: v for k, v in data.items() if k in get_schema_fields(exclude_id=True)}
        df = pd.DataFrame([clean_data])
        df.to_sql('daily_articles', conn, if_exists='append', index=False)
        conn.commit()
    except Exception as e:
        print(f"Error saving to SQLite: {e}")
        conn.rollback()
    finally:
        conn.close()

def create_sqlite_table(conn):
    schema = get_schema_fields()
    field_types = {
        'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
        'word_count': 'INTEGER',
        'scraped_at': 'TEXT',
        'published_at': 'TEXT',
        'TimeOfRelease': 'TEXT',
        'paywall_detected': 'BOOLEAN'
    }
    fields = [f"{field} {field_types.get(field, 'TEXT')}" for field in schema]
    fields_str = ", ".join(fields)
    conn.execute(f"CREATE TABLE IF NOT EXISTS daily_articles ({fields_str});")
    conn.commit()

def get_schema_fields(exclude_id: bool = False) -> List[str]:
    fields = [
        "id", "TimeOfRelease", "title", "url", "domain", "scraped_at",
        "published_at", "author", "content", "summary", "paywall_type",
        "tags", "language", "word_count", "category", "scraper_version",
        "paywall_detected"
    ]
    return fields[1:] if exclude_id else fields

def check_and_create_missing_dates(base_dir: Path, start_date_str: str = "20120101"):
    print("Checking for missing historical data directories...")
    start_date = datetime.strptime(start_date_str, "%Y%m%d").date()
    end_date = date.today()
    current_date = start_date
    while current_date <= end_date:
        dt_obj = datetime.combine(current_date, datetime.min.time())
        paths = get_storage_paths(base_dir, dt_obj)
        if not list(paths.values())[0].parent.parent.exists():
            print(f"Creating missing directory structure for {current_date.strftime('%Y-%m-%d')}")
            for p in paths.values():
                p.parent.mkdir(parents=True, exist_ok=True)
        current_date += timedelta(days=1)
    print("Directory check complete.")

def load_whitelist() -> List[Dict[str, Any]]:
    if not WHITELIST_PATH.exists():
        return []
    try:
        with open(WHITELIST_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        print("Error loading whitelist")
        return []

def load_cache() -> Dict[str, Any]:
    if not CACHE_PATH.exists():
        return {}
    try:
        with open(CACHE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        print("Error loading cache, starting fresh")
        return {}

def save_cache(data: Dict[str, Any]):
    try:
        if len(data) > MAX_CACHE_SIZE:
            sorted_items = sorted(data.items(), key=lambda x: x[1] if isinstance(x[1], str) else str(x[1]))
            data = dict(sorted_items[-MAX_CACHE_SIZE:])
        with open(CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving cache: {e}")

def detect_duplicates(article_data: Dict[str, Any], existing_articles: List[Dict[str, Any]]) -> bool:
    current_title = article_data.get('title', '').lower()
    current_content = article_data.get('content', '')[:500].lower()
    for existing in existing_articles:
        existing_title = existing.get('title', '').lower()
        existing_content = existing.get('content', '')[:500].lower()
        title_similarity = len(set(current_title.split()) & set(existing_title.split())) / max(len(current_title.split()), len(existing_title.split())) if current_title and existing_title else 0
        if title_similarity > 0.8:
            return True
        content_similarity = len(set(current_content.split()) & set(existing_content.split())) / max(len(current_content.split()), len(existing_content.split())) if current_content and existing_content else 0
        if content_similarity > 0.7:
            return True
    return False

def cleanup_old_cache_files(base_dir: Path, days_to_keep: int = 30):
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            file_path = Path(root) / file
            try:
                file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_time < cutoff_date and file.endswith(('.tmp', '.cache')):
                    file_path.unlink()
                    print(f"Deleted old cache file: {file_path}")
            except Exception as e:
                print(f"Error cleaning up {file_path}: {e}")

async def main():
    print("Starting Simplified News Scraper v2.0.2")
    print("Method: RSS Discovery + Full Page Text Extraction with Anti-Ban Measures")
    print("=" * 50)
    check_and_create_missing_dates(BASE_DATA_DIR)
    cleanup_old_cache_files(BASE_DATA_DIR)
    whitelist = load_whitelist()
    if not whitelist:
        print("Whitelist is empty or could not be loaded. Exiting.")
        return
    print(f"Loaded {len(whitelist)} sites from whitelist")
    now = datetime.now(timezone.utc)
    storage_paths = get_storage_paths(BASE_DATA_DIR, now)
    existing_articles = []
    if storage_paths['json'].exists():
        try:
            with open(storage_paths['json'], 'r', encoding='utf-8') as f:
                existing_articles = json.load(f)
        except:
            existing_articles = []
    successful_scrapes = 0
    failed_scrapes = 0
    async with Spectre(headless=False) as spectre:
        for site in whitelist:
            try:
                print(f"\n--- Processing site: {site['name']} ---")
                article_data, article_url = await asyncio.wait_for(spectre.get_latest_article(site), timeout=120)
                if article_data:
                    if not detect_duplicates(article_data, existing_articles):
                        save_data(article_data, storage_paths)
                        existing_articles.append(article_data)
                        successful_scrapes += 1
                        print(f"✓ Successfully extracted from RSS: {article_data['title'][:100]}...")
                elif article_url:
                    try:
                        scraped_data = await asyncio.wait_for(spectre.scrape_article(article_url), timeout=120)
                        await asyncio.sleep(10)  # Increased delay to avoid rate-limiting
                        if scraped_data and not detect_duplicates(scraped_data, existing_articles):
                            save_data(scraped_data, storage_paths)
                            existing_articles.append(scraped_data)
                            successful_scrapes += 1
                            print(f"✓ Successfully scraped: {scraped_data['title'][:100]}...")
                        else:
                            print("✗ Failed to scrape article data or duplicate detected")
                            failed_scrapes += 1
                    except asyncio.TimeoutError:
                        print(f"Scraping timed out for {article_url}")
                        failed_scrapes += 1
                else:
                    print("○ No changes detected")
            except asyncio.TimeoutError:
                print(f"Timeout processing site {site['name']}")
                failed_scrapes += 1
            except Exception as e:
                print(f"✗ Error processing site {site['name']}: {e}")
                failed_scrapes += 1
                continue
    print("\n" + "=" * 50)
    print("SCRAPING SUMMARY")
    print("=" * 50)
    print(f"Successful scrapes: {successful_scrapes}")
    print(f"Failed scrapes: {failed_scrapes}")
    print(f"Total sites processed: {len(whitelist)}")
    print(f"Success rate: {(successful_scrapes / len(whitelist)) * 100:.1f}%")
    if successful_scrapes > 0:
        print(f"Data saved to: {storage_paths['json'].parent}")
        print(f"HTML sources saved to: {storage_paths['json'].parent / 'HTML'}")

if __name__ == "__main__":
    asyncio.run(main())