import requests
import json
import os
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
NEWS_API_KEY = os.getenv("NEWS_API_KEY") or "your_newsapi_key_here"
NEWS_API_URL = "https://newsapi.org/v2/everything"

# Define output directory relative to project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "news_logs", "202507", "raw")
CSV_FILE = os.path.join(OUTPUT_DIR, f"202507{datetime.now().strftime('%d')}.csv")
TXT_FILE = os.path.join(OUTPUT_DIR, f"202507{datetime.now().strftime('%d')}.txt")

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)
print(f"Output directory created/verified: {os.path.abspath(OUTPUT_DIR)}")

def fetch_news(query="Bitcoin", max_articles=10):
    """Fetch news articles using NewsAPI."""
    params = {
        "q": query,
        "apiKey": NEWS_API_KEY,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": max_articles
    }
    try:
        response = requests.get(NEWS_API_URL, params=params)
        response.raise_for_status()
        return response.json().get("articles", [])
    except requests.RequestException as e:
        print(f"Error fetching news: {e}")
        return []

def save_news_to_files(articles):
    """Save news articles to CSV and TXT."""
    data = []
    for article in articles:
        data.append({
            "timestamp": article["publishedAt"],
            "source": article["source"]["name"],
            "headline": article["title"],
            "body": article["description"] or "",
            "url": article["url"]
        })
    
    df = pd.DataFrame(data)
    df.to_csv(CSV_FILE, mode='a', index=False, header=not os.path.exists(CSV_FILE))
    
    with open(TXT_FILE, 'a', encoding='utf-8') as f:
        for article in data:
            f.write(f"[{article['timestamp']}] {article['source']}: {article['headline']}\n{article['body']}\n\n")

def main():
    """Main function to fetch and save news data."""
    if not NEWS_API_KEY or NEWS_API_KEY == "your_newsapi_key_here":
        print("Error: Please set NEWS_API_KEY in .env file")
        return
    articles = fetch_news(query="Bitcoin", max_articles=10)
    if articles:
        save_news_to_files(articles)
        print(f"Saved {len(articles)} articles to {CSV_FILE} and {TXT_FILE}")
    else:
        print("No articles fetched.")

if __name__ == "__main__":
    main()