#!/usr/bin/env python3
"""
S.P.E.C.T.R.E. - Strategic Parsing and Extraction for Comprehensive Text Retrieval Engine
A production-ready news scraping module for the SHADOW AI MVP
Notamedia Hackathon 2025
"""

import asyncio
import json
import sqlite3
import csv
import logging
import hashlib
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
import pandas as pd

# Third-party imports
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from bs4 import BeautifulSoup, Tag
import requests


# Configuration constants
BASE_DATA_DIR = Path("data/news_logs")
DATE_FORMAT_DIR = "%Y/%Y%m/%Y%m%d"
DATE_FORMAT_FILE = "%Y%m%d"
SCRAPER_VERSION = "1.0.0"
HISTORICAL_START_DATE = "20120101"

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('spectre.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SPECTRENewsExtractor:
    """
    Advanced news extraction system with JavaScript rendering, paywall bypass,
    and multi-format data storage capabilities.
    """
    
    def __init__(self, headless: bool = True, cookies_path: Optional[str] = None):
        """
        Initialize the SPECTRE news extraction system.
        
        Args:
            headless: Run browser in headless mode
            cookies_path: Path to Chrome cookies JSON file for paywall bypass
        """
        self.headless = headless
        self.cookies_path = cookies_path
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.whitelist_cache = {}
        self.content_cache = {}
        
        # Ensure base directory structure exists
        BASE_DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        # Load whitelist and cache
        self.load_whitelist()
        self.load_cache()
    
    def load_whitelist(self) -> None:
        """Load site whitelist from JSON file."""
        whitelist_path = Path("whitelist.json")
        if whitelist_path.exists():
            try:
                with open(whitelist_path, 'r') as f:
                    self.whitelist_cache = json.load(f)
                logger.info(f"Loaded whitelist with {len(self.whitelist_cache)} sites")
            except Exception as e:
                logger.error(f"Error loading whitelist: {e}")
                self.whitelist_cache = self._get_default_whitelist()
        else:
            self.whitelist_cache = self._get_default_whitelist()
            self.save_whitelist()
    
    def _get_default_whitelist(self) -> Dict:
        """Return default whitelist configuration."""
        return {
            "bbc.com": {
                "url": "https://www.bbc.com/news",
                "type": "news_site",
                "paywall_type": "none",
                "selectors": {
                    "article": "article",
                    "title": "h1",
                    "content": ".story-body__inner, .gel-body-copy"
                }
            },
            "reuters.com": {
                "url": "https://www.reuters.com/world/",
                "type": "news_site",
                "paywall_type": "soft",
                "selectors": {
                    "article": "article",
                    "title": "h1",
                    "content": ".StandardArticleBody_body"
                }
            },
            "nytimes.com": {
                "url": "https://www.nytimes.com/",
                "type": "news_site",
                "paywall_type": "soft",
                "selectors": {
                    "article": "article",
                    "title": "h1",
                    "content": ".StoryBodyCompanionColumn"
                }
            }
        }
    
    def save_whitelist(self) -> None:
        """Save whitelist to JSON file."""
        try:
            with open("whitelist.json", 'w') as f:
                json.dump(self.whitelist_cache, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving whitelist: {e}")
    
    def load_cache(self) -> None:
        """Load content cache from JSON file."""
        cache_path = Path("content_cache.json")
        if cache_path.exists():
            try:
                with open(cache_path, 'r') as f:
                    self.content_cache = json.load(f)
                logger.info(f"Loaded content cache with {len(self.content_cache)} entries")
            except Exception as e:
                logger.error(f"Error loading cache: {e}")
                self.content_cache = {}
        else:
            self.content_cache = {}
    
    def save_cache(self) -> None:
        """Save content cache to JSON file."""
        try:
            with open("content_cache.json", 'w') as f:
                json.dump(self.content_cache, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
    
    async def initialize_browser(self) -> None:
        """Initialize Playwright browser and context."""
        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(
                headless=self.headless,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            
            # Create context with user agent
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            
            # Load cookies if provided
            if self.cookies_path and Path(self.cookies_path).exists():
                try:
                    with open(self.cookies_path, 'r') as f:
                        cookies = json.load(f)
                    await self.context.add_cookies(cookies)
                    logger.info(f"Loaded {len(cookies)} cookies from {self.cookies_path}")
                except Exception as e:
                    logger.error(f"Error loading cookies: {e}")
            
            logger.info("Browser initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing browser: {e}")
            raise
    
    async def close_browser(self) -> None:
        """Close browser and cleanup resources."""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            logger.info("Browser closed successfully")
        except Exception as e:
            logger.error(f"Error closing browser: {e}")
    
    def check_for_updates(self, url: str) -> bool:
        """
        Check if content has changed since last scrape.
        
        Args:
            url: URL to check for updates
            
        Returns:
            True if content has changed or is new, False otherwise
        """
        try:
            # Simple check for today's file existence
            now = datetime.utcnow()
            date_str = now.strftime(DATE_FORMAT_FILE)
            date_dir = BASE_DATA_DIR / now.strftime(DATE_FORMAT_DIR)
            
            # If today's files don't exist, we need to scrape
            json_file = date_dir / "JSON" / f"{date_str}.json"
            if not json_file.exists():
                return True
            
            # Check content hash for more sophisticated detection
            domain = urlparse(url).netloc
            response = requests.get(url, timeout=10)
            content_hash = hashlib.md5(response.content).hexdigest()
            
            cached_hash = self.content_cache.get(domain)
            if cached_hash != content_hash:
                self.content_cache[domain] = content_hash
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            # If we can't check, assume we need to scrape
            return True
    
    async def bypass_paywall(self, page: Page) -> None:
        """
        Implement soft paywall bypass techniques.
        
        Args:
            page: Playwright page object
        """
        try:
            # Scroll to trigger lazy loading
            await page.evaluate('''
                () => {
                    window.scrollTo(0, document.body.scrollHeight);
                }
            ''')
            
            # Wait for any dynamic content to load
            await page.wait_for_timeout(2000)
            
            # Remove common paywall elements
            await page.evaluate('''
                () => {
                    // Remove paywall overlays and blurs
                    const selectors = [
                        '[class*="paywall"]',
                        '[class*="overlay"]',
                        '[class*="modal"]',
                        '[style*="blur"]',
                        '.subscription-barrier',
                        '.paywall-barrier',
                        '.meter-paywall',
                        '.article-gate'
                    ];
                    
                    selectors.forEach(selector => {
                        document.querySelectorAll(selector).forEach(el => {
                            el.remove();
                        });
                    });
                    
                    // Remove blur styles
                    document.querySelectorAll('*').forEach(el => {
                        if (el.style.filter && el.style.filter.includes('blur')) {
                            el.style.filter = '';
                        }
                    });
                }
            ''')
            
            logger.info("Paywall bypass techniques applied")
            
        except Exception as e:
            logger.error(f"Error during paywall bypass: {e}")
    
    async def extract_article_content(self, page: Page, url: str) -> Optional[Dict]:
        """
        Extract clean article content from the page.
        
        Args:
            page: Playwright page object
            url: Article URL
            
        Returns:
            Dictionary containing extracted article data
        """
        try:
            # Get page content
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Save raw HTML for debugging
            await self._save_raw_html(html, url)
            
            # Extract article data
            article_data = self._extract_data(soup, url, html)
            
            return article_data
            
        except Exception as e:
            logger.error(f"Error extracting article content: {e}")
            return None
    
    def _extract_data(self, soup: BeautifulSoup, url: str, html: str) -> Dict:
        """
        Extract structured data from BeautifulSoup object.
        
        Args:
            soup: BeautifulSoup parsed HTML
            url: Article URL
            html: Raw HTML content
            
        Returns:
            Dictionary with extracted article data
        """
        now = datetime.utcnow()
        domain = urlparse(url).netloc
        
        # Extract title
        title_tag = soup.find('h1') or soup.find('title')
        title = title_tag.get_text(strip=True) if title_tag else "No title found"
        
        # Extract content from common article containers
        content_containers = [
            soup.find('article'),
            soup.find('main'),
            soup.find('div', class_=['article-body', 'content', 'story-body']),
            soup.find('div', id=['article-content', 'content']),
            soup.body
        ]
        
        container = None
        for cont in content_containers:
            if cont:
                container = cont
                break
        
        if not container:
            container = soup
        
        # Extract paragraphs
        paragraphs = container.find_all('p')
        content = "\n\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        
        # Extract author
        author_selectors = ['[rel="author"]', '.author', '.byline', '[class*="author"]']
        author = "Unknown"
        for selector in author_selectors:
            author_elem = soup.select_one(selector)
            if author_elem:
                author = author_elem.get_text(strip=True)
                break
        
        # Generate summary (first 200 characters)
        summary = content[:200] + "..." if len(content) > 200 else content
        
        # Determine paywall type
        paywall_type = "none"
        if any(term in html.lower() for term in ['paywall', 'subscription', 'premium']):
            paywall_type = "soft"
        
        # Extract tags/categories
        tags = []
        for tag_elem in soup.find_all(['meta'], {'name': ['keywords', 'news_keywords']}):
            if tag_elem.get('content'):
                tags.extend([tag.strip() for tag in tag_elem.get('content').split(',')])
        
        # Language detection (simplified)
        lang_elem = soup.find('html')
        language = lang_elem.get('lang', 'en') if lang_elem else 'en'
        
        return {
            'TimeOfRelease': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'title': title,
            'url': url,
            'domain': domain,
            'scraped_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'published_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),  # Simplified for MVP
            'author': author,
            'content': content,
            'summary': summary,
            'paywall_type': paywall_type,
            'tags': ', '.join(tags) if tags else '',
            'language': language,
            'word_count': len(content.split()) if content else 0,
            'category': 'news',  # Simplified for MVP
            'scraper_version': SCRAPER_VERSION
        }
    
    async def _save_raw_html(self, html: str, url: str) -> None:
        """Save raw HTML content for debugging."""
        try:
            now = datetime.utcnow()
            html_dir = BASE_DATA_DIR / now.strftime(DATE_FORMAT_DIR) / "HTML"
            html_dir.mkdir(parents=True, exist_ok=True)
            
            # Sanitize filename
            domain = urlparse(url).netloc
            filename = f"{now.strftime('%H%M%S')}_{domain}.html"
            filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
            
            html_file = html_dir / filename
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html)
            
            logger.debug(f"Saved raw HTML to {html_file}")
            
        except Exception as e:
            logger.error(f"Error saving raw HTML: {e}")
    
    def save_data(self, article_data: Dict) -> None:
        """
        Save article data in all required formats.
        
        Args:
            article_data: Dictionary containing article data
        """
        try:
            now = datetime.utcnow()
            date_str = now.strftime(DATE_FORMAT_FILE)
            date_dir = BASE_DATA_DIR / now.strftime(DATE_FORMAT_DIR)
            
            # Create directories
            for format_dir in ['TXT', 'CSV', 'JSON', 'SQLITE3']:
                (date_dir / format_dir).mkdir(parents=True, exist_ok=True)
            
            # Save TXT format
            txt_file = date_dir / 'TXT' / f'{date_str}.txt'
            txt_line = ' || '.join(str(article_data.get(field, '')) for field in [
                'TimeOfRelease', 'title', 'url', 'domain', 'scraped_at',
                'published_at', 'author', 'content', 'summary', 'paywall_type',
                'tags', 'language', 'word_count', 'category', 'scraper_version'
            ])
            
            with open(txt_file, 'a', encoding='utf-8') as f:
                f.write(txt_line + '\n')
            
            # Save CSV format
            csv_file = date_dir / 'CSV' / f'{date_str}.csv'
            fieldnames = [
                'TimeOfRelease', 'title', 'url', 'domain', 'scraped_at',
                'published_at', 'author', 'content', 'summary', 'paywall_type',
                'tags', 'language', 'word_count', 'category', 'scraper_version'
            ]
            
            file_exists = csv_file.exists()
            with open(csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(article_data)
            
            # Save JSON format
            json_file = date_dir / 'JSON' / f'{date_str}.json'
            if json_file.exists():
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = []
            
            data.append(article_data)
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Save SQLite format
            sqlite_file = date_dir / 'SQLITE3' / f'{date_str}.db'
            conn = sqlite3.connect(sqlite_file)
            cursor = conn.cursor()
            
            # Create table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_articles (
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
                )
            ''')
            
            # Insert data
            cursor.execute('''
                INSERT INTO daily_articles (
                    TimeOfRelease, title, url, domain, scraped_at,
                    published_at, author, content, summary, paywall_type,
                    tags, language, word_count, category, scraper_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                article_data['TimeOfRelease'], article_data['title'],
                article_data['url'], article_data['domain'],
                article_data['scraped_at'], article_data['published_at'],
                article_data['author'], article_data['content'],
                article_data['summary'], article_data['paywall_type'],
                article_data['tags'], article_data['language'],
                article_data['word_count'], article_data['category'],
                article_data['scraper_version']
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Saved article data in all formats for {date_str}")
            
        except Exception as e:
            logger.error(f"Error saving data: {e}")
    
    async def scrape_article(self, url: str) -> Optional[Dict]:
        """
        Scrape a single article from the given URL.
        
        Args:
            url: URL to scrape
            
        Returns:
            Dictionary containing article data or None if failed
        """
        try:
            if not self.browser:
                await self.initialize_browser()
            
            page = await self.context.new_page()
            
            # Navigate to the URL
            await page.goto(url, wait_until='domcontentloaded', timeout=90000)
            
            # Wait for dynamic content
            await page.wait_for_timeout(5000)
            
            # Apply paywall bypass
            await self.bypass_paywall(page)
            
            # Extract article content
            article_data = await self.extract_article_content(page, url)
            
            await page.close()
            
            if article_data:
                self.save_data(article_data)
                logger.info(f"Successfully scraped article from {url}")
                return article_data
            else:
                logger.warning(f"Failed to extract content from {url}")
                return None
                
        except Exception as e:
            logger.error(f"Error scraping article {url}: {e}")
            return None
    
    def check_and_create_missing_dates(self) -> List[str]:
        """
        Check for missing data directories and create them if needed.
        
        Returns:
            List of missing date strings
        """
        missing_dates = []
        
        try:
            # Parse start date
            start_date = datetime.strptime(HISTORICAL_START_DATE, '%Y%m%d')
            end_date = datetime.utcnow()
            
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime(DATE_FORMAT_FILE)
                date_dir = BASE_DATA_DIR / current_date.strftime(DATE_FORMAT_DIR)
                
                # Check if directory exists and has all required subdirectories
                required_dirs = ['TXT', 'CSV', 'JSON', 'SQLITE3']
                missing_dir = False
                
                if not date_dir.exists():
                    missing_dir = True
                else:
                    for req_dir in required_dirs:
                        if not (date_dir / req_dir).exists():
                            missing_dir = True
                            break
                
                if missing_dir:
                    missing_dates.append(date_str)
                    # Create missing directories
                    for req_dir in required_dirs:
                        (date_dir / req_dir).mkdir(parents=True, exist_ok=True)
                
                current_date += timedelta(days=1)
            
            logger.info(f"Historical data check complete. Missing dates: {len(missing_dates)}")
            if missing_dates:
                logger.warning(f"Created directories for {len(missing_dates)} missing dates")
            
            return missing_dates
            
        except Exception as e:
            logger.error(f"Error checking historical data: {e}")
            return []
    
    async def run_daily_scrape(self) -> None:
        """Run the daily scraping process for all whitelisted sites."""
        try:
            logger.info("Starting daily scrape process")
            
            # Check and create missing historical directories
            missing_dates = self.check_and_create_missing_dates()
            
            # Initialize browser
            await self.initialize_browser()
            
            scraped_count = 0
            
            # Process each site in whitelist
            for domain, config in self.whitelist_cache.items():
                url = config['url']
                
                # Check if we need to scrape this site
                if self.check_for_updates(url):
                    logger.info(f"Scraping {domain}...")
                    
                    article_data = await self.scrape_article(url)
                    if article_data:
                        scraped_count += 1
                    
                    # Brief delay between requests
                    await asyncio.sleep(2)
                else:
                    logger.info(f"No updates detected for {domain}, skipping")
            
            # Save updated cache
            self.save_cache()
            
            logger.info(f"Daily scrape complete. Scraped {scraped_count} articles")
            
        except Exception as e:
            logger.error(f"Error during daily scrape: {e}")
        finally:
            await self.close_browser()


async def main():
    """Main execution function."""
    try:
        # Initialize SPECTRE
        spectre = SPECTRENewsExtractor(headless=True)
        
        # Run daily scraping process
        await spectre.run_daily_scrape()
        
        logger.info("SPECTRE execution completed successfully")
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
