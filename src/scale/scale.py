import os
import requests
import time
import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional, Dict
import logging

# Configure logging
log_file = "scale.log" if os.name == 'nt' else ("/var/log/scale.log" if os.getenv("ENV") == "production" else "scale.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, mode='a', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Hardcoded configuration
SYMBOL = "BTCUSDT"
POLL_INTERVAL = 1  # Seconds
MAX_API_RETRIES = 3  # Maximum retries for API requests
RETRY_DELAY = 2  # Seconds
BASE_URL = "https://api.binance.com/api/v3/ticker/price"  # Binance API endpoint
OUTPUT_BASE_DIR = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")), "data", "scale")  # Base output directory
TIMEZONE = timezone.utc  # UTC timezone for timestamps

def get_month_dir() -> str:
    """Get the current YYYYMM directory."""
    return os.path.join(OUTPUT_BASE_DIR, datetime.now(TIMEZONE).strftime("%Y%m"))

def setup_directories(date_str: str) -> None:
    """Create output directories for the current month."""
    month_dir = get_month_dir()
    csv_dir = os.path.join(month_dir, "csv")
    sqlite_dir = os.path.join(month_dir, "sqlite")
    txt_dir = os.path.join(month_dir, "txt")
    for dir_path in [csv_dir, sqlite_dir, txt_dir]:
        try:
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"Directory created/verified: {dir_path}")
        except Exception as e:
            logger.error(f"Error creating directory {dir_path}: {e}")

def setup_sqlite(date_str: str) -> Optional[str]:
    """Initialize SQLite database and trades table."""
    month_dir = get_month_dir()
    sqlite_file = os.path.join(month_dir, "sqlite", f"{date_str}.db")
    try:
        conn = sqlite3.connect(sqlite_file)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                timestamp TEXT,
                price REAL
            )
        """)
        conn.commit()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
        if cursor.fetchone():
            logger.info(f"SQLite table 'trades' confirmed in: {sqlite_file}")
        else:
            logger.error(f"Failed to create 'trades' table in {sqlite_file}")
            return None
        conn.close()
        return sqlite_file
    except sqlite3.Error as e:
        logger.error(f"SQLite error during setup for {sqlite_file}: {e}")
        return None

def fetch_price() -> Optional[Dict]:
    """Fetch the latest price from Binance API."""
    params = {"symbol": SYMBOL}
    for attempt in range(1, MAX_API_RETRIES + 1):
        try:
            fetch_start = time.time()
            response = requests.get(BASE_URL, params=params, headers={'Cache-Control': 'no-cache'})
            response.raise_for_status()
            data = response.json()
            if "code" in data:
                logger.warning(f"API error on attempt {attempt}: {data.get('msg', 'Unknown error')}")
                if attempt == MAX_API_RETRIES:
                    return None
                time.sleep(RETRY_DELAY)
                continue
            price = float(data["price"])
            timestamp = datetime.now(TIMEZONE).strftime("%Y-%m-%dT%H:%M:%SZ")
            fetch_end = time.time()
            logger.info(f"Fetched price: {price} at {timestamp}")
            logger.debug(f"Fetch time: {fetch_end - fetch_start:.2f} seconds")
            return {"ticker": f"BINANCE:{SYMBOL}", "timestamp": timestamp, "price": price}
        except requests.RequestException as e:
            logger.warning(f"Error fetching price on attempt {attempt}: {e}")
            if attempt == MAX_API_RETRIES:
                return None
            time.sleep(RETRY_DELAY)
    return None

def save_data(data: Optional[Dict], date_str: str) -> None:
    """Save price data to CSV, SQLite, and TXT."""
    if data is None:
        return
    month_dir = get_month_dir()
    csv_file = os.path.join(month_dir, "csv", f"{date_str}.csv")
    sqlite_file = os.path.join(month_dir, "sqlite", f"{date_str}.db")
    txt_file = os.path.join(month_dir, "txt", f"{date_str}.txt")
    
    save_start = time.time()
    
    # CSV
    try:
        with open(csv_file, 'a', encoding='utf-8') as f:
            if not os.path.exists(csv_file) or os.path.getsize(csv_file) == 0:
                f.write("timestamp,price\n")
            f.write(f"{data['timestamp']},{data['price']}\n")
        logger.info(f"Saved to CSV: {csv_file}")
    except Exception as e:
        logger.error(f"Error writing to CSV {csv_file}: {e}")
    
    # SQLite
    try:
        conn = sqlite3.connect(sqlite_file)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO trades (timestamp, price) VALUES (?, ?)", 
                      (data['timestamp'], data['price']))
        conn.commit()
        conn.close()
        logger.info(f"Saved to SQLite: {sqlite_file}")
    except sqlite3.Error as e:
        logger.error(f"SQLite error writing to {sqlite_file}: {e}")
    
    # TXT
    try:
        with open(txt_file, 'a', encoding='utf-8') as f:
            json.dump({"ticker": data['ticker'], "timestamp": data['timestamp'], "price": data['price']}, f)
            f.write("\n")
        logger.info(f"Saved to TXT: {txt_file}")
    except Exception as e:
        logger.error(f"Error writing to TXT {txt_file}: {e}")
    
    save_end = time.time()
    logger.info(f"Saved data: {json.dumps({'ticker': data['ticker'], 'timestamp': data['timestamp'], 'price': data['price']})}")
    logger.debug(f"Save time: {save_end - save_start:.2f} seconds")

def main() -> None:
    """Main loop for S.C.A.L.E."""
    logger.info("Starting S.C.A.L.E. Press Ctrl+C to stop.")
    
    current_date_str = datetime.now(TIMEZONE).strftime("%Y%m%d")
    setup_directories(current_date_str)
    sqlite_file = setup_sqlite(current_date_str)
    if sqlite_file is None:
        logger.error("Stopping S.C.A.L.E. due to SQLite setup failure")
        return
    
    try:
        while True:
            start_time = time.time()
            new_date_str = datetime.now(TIMEZONE).strftime("%Y%m%d")
            if new_date_str != current_date_str:
                logger.info(f"Date changed to {new_date_str}. Updating directories and SQLite database.")
                setup_directories(new_date_str)
                sqlite_file = setup_sqlite(new_date_str)
                if sqlite_file is None:
                    logger.error("Stopping S.C.A.L.E. due to SQLite setup failure")
                    return
                current_date_str = new_date_str
            
            data = fetch_price()
            if data:
                print(f"{data['timestamp']} | Price: {data['price']}")
                save_data(data, current_date_str)
            else:
                print(f"{datetime.now(TIMEZONE).strftime('%Y-%m-%dT%H:%M:%SZ')} | No data fetched")
            
            elapsed = time.time() - start_time
            sleep_time = max(POLL_INTERVAL - elapsed, 0)
            time.sleep(sleep_time)
    except KeyboardInterrupt:
        logger.info("Stopping S.C.A.L.E. via Ctrl+C")
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
    finally:
        logger.info("Cleaning up and stopping S.C.A.L.E.")

if __name__ == "__main__":
    main()