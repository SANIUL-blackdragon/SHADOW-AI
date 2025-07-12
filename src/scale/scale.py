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
BASE_URL = "https://api.binance.com/api/v3/aggTrades"  # Binance aggregated trades endpoint
OUTPUT_BASE_DIR = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")), "data", "scale")
TIMEZONE = timezone.utc

def get_month_dir(timestamp: datetime) -> str:
    """Get YYYYMM directory based on data's timestamp."""
    return os.path.join(OUTPUT_BASE_DIR, timestamp.strftime("%Y%m"))

def setup_directories(timestamp: datetime) -> None:
    """Create output directories based on data's timestamp."""
    month_dir = get_month_dir(timestamp)
    csv_dir = os.path.join(month_dir, "csv")
    sqlite_dir = os.path.join(month_dir, "sqlite")
    txt_dir = os.path.join(month_dir, "txt")
    for dir_path in [csv_dir, sqlite_dir, txt_dir]:
        try:
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"Directory created/verified: {dir_path}")
        except Exception as e:
            logger.error(f"Error creating directory {dir_path}: {e}")

def setup_sqlite(timestamp: datetime, date_str: str) -> Optional[str]:
    """Initialize SQLite database and trades table."""
    month_dir = get_month_dir(timestamp)
    sqlite_file = os.path.join(month_dir, "sqlite", f"{date_str}.db")
    try:
        conn = sqlite3.connect(sqlite_file)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                timestamp TEXT,
                price REAL,
                quantity REAL,
                quoteQty REAL,
                tradeId INTEGER
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
    """Fetch the latest aggregated trade from Binance API."""
    params = {"symbol": SYMBOL, "limit": 1}
    for attempt in range(1, MAX_API_RETRIES + 1):
        try:
            fetch_start = time.time()
            response = requests.get(BASE_URL, params=params, headers={'Cache-Control': 'no-cache'})
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and "code" in data:
                logger.warning(f"API error on attempt {attempt}: {data.get('msg', 'Unknown error')}")
                if attempt == MAX_API_RETRIES:
                    return None
                time.sleep(RETRY_DELAY)
                continue
            trade = data[0]
            timestamp = datetime.fromtimestamp(trade["T"] / 1000, tz=TIMEZONE).strftime("%Y-%m-%dT%H:%M:%SZ")
            price = float(trade["p"])
            quantity = float(trade["q"])
            quote_qty = price * quantity
            trade_id = int(trade["a"])
            fetch_end = time.time()
            logger.info(f"Fetched trade: price={price}, quantity={quantity}, tradeId={trade_id} at {timestamp}")
            logger.debug(f"Fetch time: {fetch_end - fetch_start:.2f} seconds")
            return {
                "ticker": f"BINANCE:{SYMBOL}",
                "timestamp": timestamp,
                "price": price,
                "quantity": quantity,
                "quoteQty": quote_qty,
                "tradeId": trade_id
            }
        except (requests.RequestException, IndexError, KeyError) as e:
            logger.warning(f"Error fetching trade on attempt {attempt}: {e}")
            if attempt == MAX_API_RETRIES:
                return None
            time.sleep(RETRY_DELAY)
    return None

def save_data(data: Optional[Dict], timestamp: datetime, date_str: str) -> None:
    """Save trade data to CSV, SQLite, and TXT."""
    if data is None:
        return
    month_dir = get_month_dir(timestamp)
    csv_file = os.path.join(month_dir, "csv", f"{date_str}.csv")
    sqlite_file = os.path.join(month_dir, "sqlite", f"{date_str}.db")
    txt_file = os.path.join(month_dir, "txt", f"{date_str}.txt")
    
    save_start = time.time()
    
    # CSV
    try:
        with open(csv_file, 'a', encoding='utf-8') as f:
            if not os.path.exists(csv_file) or os.path.getsize(csv_file) == 0:
                f.write("timestamp,price,quantity,quoteQty,tradeId\n")
            f.write(f"{data['timestamp']},{data['price']},{data['quantity']},{data['quoteQty']},{data['tradeId']}\n")
        logger.info(f"Saved to CSV: {csv_file}")
    except Exception as e:
        logger.error(f"Error writing to CSV {csv_file}: {e}")
    
    # SQLite
    try:
        conn = sqlite3.connect(sqlite_file)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO trades (timestamp, price, quantity, quoteQty, tradeId)
            VALUES (?, ?, ?, ?, ?)
        """, (data['timestamp'], data['price'], data['quantity'], data['quoteQty'], data['tradeId']))
        conn.commit()
        conn.close()
        logger.info(f"Saved to SQLite: {sqlite_file}")
    except sqlite3.Error as e:
        logger.error(f"SQLite error writing to {sqlite_file}: {e}")
    
    # TXT
    try:
        with open(txt_file, 'a', encoding='utf-8') as f:
            json.dump(data, f)
            f.write("\n")
        logger.info(f"Saved to TXT: {txt_file}")
    except Exception as e:
        logger.error(f"Error writing to TXT {txt_file}: {e}")
    
    save_end = time.time()
    logger.info(f"Saved data: {json.dumps(data)}")
    logger.debug(f"Save time: {save_end - save_start:.2f} seconds")

def main() -> None:
    """Main loop for S.C.A.L.E."""
    logger.info("Starting S.C.A.L.E. Press Ctrl+C to stop.")
    
    try:
        while True:
            start_time = time.time()
            data = fetch_price()
            if data:
                timestamp = datetime.strptime(data['timestamp'], "%Y-%m-%dT%H:%M:%SZ")
                date_str = timestamp.strftime("%Y%m%d")
                setup_directories(timestamp)
                sqlite_file = setup_sqlite(timestamp, date_str)
                if sqlite_file is None:
                    logger.error("Stopping S.C.A.L.E. due to SQLite setup failure")
                    return
                print(f"{data['timestamp']} | Price: {data['price']} | Volume: {data['quantity']}")
                save_data(data, timestamp, date_str)
            else:
                current_timestamp = datetime.now(TIMEZONE).strftime("%Y-%m-%dT%H:%M:%SZ")
                print(f"{current_timestamp} | No data fetched")
            
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