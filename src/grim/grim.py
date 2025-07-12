import os
import requests
import pandas as pd
import sqlite3
import json
from datetime import datetime, timezone, timedelta
import logging
from glob import glob
import time
from typing import Dict, Optional

# Configure logging
log_file = "grim.log"
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, mode='a', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Configuration
SYMBOL = "BTCUSDT"
BASE_URL = "https://api.binance.com/api/v3/aggTrades"
OUTPUT_BASE_DIR = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")), "data", "grim")
SCALE_DATA_DIR = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")), "data", "scale")
NEWS_DATA_DIR = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")), "data", "news_logs")
TIMEZONE = timezone.utc
MAX_API_RETRIES = 3
RETRY_DELAY = 5
CHECK_INTERVAL = 60
EARLIEST_TIMESTAMP = datetime(2018, 7, 1, tzinfo=TIMEZONE)  # Updated to a recent date
RATE_LIMIT_WAIT = 120

def get_month_dir(timestamp: datetime) -> str:
    return os.path.join(OUTPUT_BASE_DIR, timestamp.strftime("%Y%m"))

def setup_directories(timestamp: datetime) -> None:
    month_dir = get_month_dir(timestamp)
    for sub_dir in ["chart/csv", "chart/sqlite", "news/csv", "news/sqlite"]:
        dir_path = os.path.join(month_dir, sub_dir)
        try:
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"Directory created/verified: {dir_path}")
        except Exception as e:
            logger.error(f"Error creating directory {dir_path}: {e}")

def setup_sqlite(timestamp: datetime, date_str: str, table_type: str) -> Optional[str]:
    month_dir = get_month_dir(timestamp)
    sub_dir = "chart" if table_type == "trades" else "news"
    sqlite_file = os.path.join(month_dir, sub_dir, "sqlite", f"{date_str}.db")
    table_name = "trades" if table_type == "trades" else "news_logs"
    create_table_sql = """
        CREATE TABLE IF NOT EXISTS trades (
            timestamp TEXT,
            price REAL,
            quantity REAL,
            quoteQty REAL,
            tradeId INTEGER,
            PRIMARY KEY (tradeId)
        )
    """ if table_type == "trades" else """
        CREATE TABLE IF NOT EXISTS news_logs (
            timestamp TEXT,
            title TEXT,
            description TEXT,
            PRIMARY KEY (timestamp, title)
        )
    """
    try:
        conn = sqlite3.connect(sqlite_file)
        cursor = conn.cursor()
        cursor.execute(create_table_sql)
        conn.commit()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if cursor.fetchone():
            logger.info(f"SQLite table '{table_name}' confirmed in: {sqlite_file}")
            return sqlite_file
        logger.error(f"Failed to create '{table_name}' table in {sqlite_file}")
        return None
    except sqlite3.Error as e:
        logger.error(f"SQLite error during setup for {sqlite_file}: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()

def fetch_historical_trades(start_time: datetime, end_time: datetime) -> Optional[pd.DataFrame]:
    params = {
        "symbol": SYMBOL,
        "limit": 1000,
        "startTime": int(start_time.timestamp() * 1000),
        "endTime": int(end_time.timestamp() * 1000)
    }
    trades = []
    for attempt in range(1, MAX_API_RETRIES + 1):
        try:
            logger.debug(f"API request: {BASE_URL}, params: {params}")
            response = requests.get(BASE_URL, params=params, headers={'Cache-Control': 'no-cache'}, timeout=10)
            logger.debug(f"Raw response: {response.text}")
            if not response.ok:
                logger.error(f"API error response [{response.status_code}]: {response.text}")
            if response.status_code == 429:
                logger.warning(f"Rate limit hit on attempt {attempt}. Waiting {RATE_LIMIT_WAIT} seconds.")
                time.sleep(RATE_LIMIT_WAIT)
                continue
            try:
                response.raise_for_status()
            except requests.HTTPError as e:
                logger.error(f"HTTP error: {e} | Body: {response.text}")
                if attempt == MAX_API_RETRIES:
                    logger.error(f"Max retries reached for {start_time} to {end_time}")
                    return None
                time.sleep(RETRY_DELAY)
                continue
            data = response.json()
            if isinstance(data, dict) and "code" in data:
                logger.warning(f"API error on attempt {attempt}: {data.get('msg', 'Unknown error')}")
                logger.error(f"API error body: {response.text}")
                if attempt == MAX_API_RETRIES:
                    logger.error(f"Max retries reached for {start_time} to {end_time}")
                    return None
                time.sleep(RETRY_DELAY)
                continue
            if not data:
                logger.info(f"No trades fetched for {start_time} to {end_time}")
                return None
            for trade in data:
                try:
                    timestamp = datetime.fromtimestamp(trade["T"] / 1000, tz=TIMEZONE).strftime("%Y-%m-%dT%H:%M:%SZ")
                    price = float(trade["p"])
                    quantity = float(trade["q"])
                    trades.append({
                        "timestamp": timestamp,
                        "price": price,
                        "quantity": quantity,
                        "quoteQty": price * quantity,
                        "tradeId": int(trade["a"])
                    })
                except (ValueError, KeyError) as e:
                    logger.error(f"Error processing trade {trade}: {e}")
                    continue
            logger.info(f"Fetched {len(data)} trades from {start_time} to {end_time}")
            return pd.DataFrame(trades)
        except (requests.RequestException, ValueError, KeyError) as e:
            logger.warning(f"Error fetching trades on attempt {attempt}: {e}")
            if 'response' in locals():
                logger.error(f"API error body: {response.text}")
            if attempt == MAX_API_RETRIES:
                logger.error(f"Max retries reached for {start_time} to {end_time}")
                return None
            time.sleep(RETRY_DELAY)
    return None

def consolidate_scale_data() -> Optional[pd.DataFrame]:
    scale_files = glob(os.path.join(SCALE_DATA_DIR, "*/csv/*.csv"))
    if not scale_files:
        logger.warning("No scale.py CSV files found")
        return None
    dfs = []
    for file in scale_files:
        try:
            df = pd.read_csv(file)
            if not all(col in df.columns for col in ["timestamp", "price", "quantity", "tradeId"]):
                logger.warning(f"Missing required columns in {file}")
                continue
            dfs.append(df)
        except Exception as e:
            logger.error(f"Error reading scale CSV {file}: {e}")
    if dfs:
        combined_df = pd.concat(dfs, ignore_index=True)
        combined_df["timestamp"] = pd.to_datetime(combined_df["timestamp"], errors='coerce')
        combined_df = combined_df.dropna(subset=["timestamp"])
        combined_df = combined_df.sort_values("timestamp").drop_duplicates(subset=["tradeId"])
        combined_df["timestamp"] = combined_df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        combined_df["quoteQty"] = combined_df["price"] * combined_df["quantity"]
        logger.info(f"Consolidated {len(combined_df)} scale.py records")
        return combined_df
    return None

def consolidate_news_data() -> Optional[pd.DataFrame]:
    news_data = []
    csv_files = glob(os.path.join(NEWS_DATA_DIR, "*.csv"))
    for file in csv_files:
        try:
            df = pd.read_csv(file)
            if "timestamp" in df.columns and "title" in df.columns:
                df["description"] = df["description"].fillna("") if "description" in df.columns else ""
                news_data.append(df[["timestamp", "title", "description"]])
            logger.info(f"Read {len(df)} news records from {file}")
        except Exception as e:
            logger.error(f"Error reading news CSV {file}: {e}")
    
    txt_files = glob(os.path.join(NEWS_DATA_DIR, "*.txt"))
    for file in txt_files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        if "timestamp" in record and "title" in record:
                            news_data.append({
                                "timestamp": record["timestamp"],
                                "title": record["title"],
                                "description": record.get("description", "")
                            })
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON in {file}: {line.strip()}")
                        continue
        except Exception as e:
            logger.error(f"Error reading news TXT {file}: {e}")
    
    if news_data:
        df = pd.DataFrame(news_data) if isinstance(news_data[0], dict) else pd.concat(news_data, ignore_index=True)
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors='coerce')
        df = df.dropna(subset=["timestamp"])
        df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp", "title"])
        df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        logger.info(f"Consolidated {len(df)} news records")
        return df
    logger.warning("No valid news data found in news_logs")
    return None

def save_data(df: pd.DataFrame, table_type: str) -> None:
    if df.empty or df["timestamp"].isnull().all():
        logger.warning(f"No valid {table_type} data to save")
        return
    for date_str in df["timestamp"].str[:10].str.replace("-", "").unique():
        try:
            timestamp = datetime.strptime(date_str, "%Y%m%d")
            month_dir = get_month_dir(timestamp)
            sub_dir = "chart" if table_type == "trades" else "news"
            csv_file = os.path.join(month_dir, sub_dir, "csv", f"{date_str}.csv")
            sqlite_file = os.path.join(month_dir, sub_dir, "sqlite", f"{date_str}.db")
            date_formatted = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            df_date = df[df["timestamp"].str.startswith(date_formatted)]
            setup_directories(timestamp)
            sqlite_file = setup_sqlite(timestamp, date_str, table_type)
            if not sqlite_file:
                logger.error(f"Skipping save due to SQLite setup failure for {date_str}")
                continue
            try:
                df_date.to_csv(csv_file, index=False)
                logger.info(f"Saved {len(df_date)} {table_type} records to CSV: {csv_file}")
            except Exception as e:
                logger.error(f"Error writing to CSV {csv_file}: {e}")
            try:
                conn = sqlite3.connect(sqlite_file)
                cursor = conn.cursor()
                if table_type == "trades":
                    for _, row in df_date.iterrows():
                        cursor.execute("""
                            INSERT OR IGNORE INTO trades (timestamp, price, quantity, quoteQty, tradeId)
                            VALUES (?, ?, ?, ?, ?)
                        """, (row["timestamp"], row["price"], row["quantity"], row["quoteQty"], row["tradeId"]))
                else:
                    for _, row in df_date.iterrows():
                        cursor.execute("""
                            INSERT OR IGNORE INTO news_logs (timestamp, title, description)
                            VALUES (?, ?, ?)
                        """, (row["timestamp"], row["title"], row["description"]))
                conn.commit()
                logger.info(f"Saved {len(df_date)} {table_type} records to SQLite: {sqlite_file}")
            except sqlite3.Error as e:
                logger.error(f"SQLite error writing to {sqlite_file}: {e}")
            finally:
                if 'conn' in locals():
                    conn.close()
        except Exception as e:
            logger.error(f"Error processing date {date_str} for {table_type}: {e}")

def get_latest_trade_timestamp() -> datetime:
    sqlite_files = glob(os.path.join(OUTPUT_BASE_DIR, "*/chart/sqlite/*.db"))
    latest_timestamp = EARLIEST_TIMESTAMP
    for file in sqlite_files:
        try:
            conn = sqlite3.connect(file)
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(timestamp) FROM trades")
            result = cursor.fetchone()[0]
            if result:
                ts = datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=TIMEZONE)
                if ts > latest_timestamp:
                    latest_timestamp = ts
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"Error querying timestamp from {file}: {e}")
    logger.info(f"Latest trade timestamp: {latest_timestamp}")
    return latest_timestamp

def main() -> None:
    logger.info("Starting G.R.I.M. Press Ctrl+C to stop.")
    
    try:
        test_response = requests.get("https://api.binance.com/api/v3/ping", timeout=5)
        logger.info(f"Binance API ping: {test_response.status_code}")
    except Exception as e:
        logger.error(f"Binance API ping failed: {e}")
    
    while True:
        try:
            scale_df = consolidate_scale_data()
            if scale_df is not None and not scale_df.empty:
                save_data(scale_df, "trades")
            
            news_df = consolidate_news_data()
            if news_df is not None and not news_df.empty:
                save_data(news_df, "news")
            
            start_time = get_latest_trade_timestamp()
            end_time = datetime.now(TIMEZONE)
            while start_time < end_time:
                chunk_end = min(start_time + timedelta(hours=1), end_time)
                api_df = fetch_historical_trades(start_time, chunk_end)
                if api_df is not None and not api_df.empty:
                    save_data(api_df, "trades")
                start_time = chunk_end
            logger.info(f"Completed cycle at {datetime.now(TIMEZONE).strftime('%Y-%m-%dT%H:%M:%SZ')}")
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Stopping G.R.I.M. via Ctrl+C")
            break
        except Exception as e:
            logger.error(f"Error in G.R.I.M. main loop: {e}")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()