import os
import requests
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timezone, timedelta
import logging
from glob import glob
import time
from typing import Optional, Set

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
PING_URL = "https://api.binance.com/api/v3/ping"
OUTPUT_BASE_DIR = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")), "data", "grim")
SCALE_DATA_DIR = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")), "data", "scale")
ZIP_DATA_DIR = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")), "data", "zip")
TIMEZONE = timezone.utc
MAX_API_RETRIES = 3
RETRY_DELAY = 5
CHECK_INTERVAL = 60
EARLIEST_TIMESTAMP = datetime(2012, 1, 1, tzinfo=TIMEZONE)  # Start from 2012 for Bitstamp
RATE_LIMIT_WAIT = 120
BITFINEX_START_DATE = datetime(2022, 3, 17, 6, 12, tzinfo=TIMEZONE)  # Bitfinex data starts 3/17/2022 6:12:00 AM

# Define dtypes for CSV processing
CSV_DTYPES: dict[str, str] = {
    'unix': 'float64',
    'date': 'object',
    'open': 'float64',
    'high': 'float64',
    'low': 'float64',
    'close': 'float64',
    'Volume BTC': 'float64',
    'Volume USD': 'float64',
    'id': 'object',
    'tradeId': 'object',
    'price': 'float64',
    'amount': 'float64',
    'quantity': 'float64'
}

def get_all_csv_files(directory: str) -> list:
    """Find all CSV files in directory and subfolders."""
    csv_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".csv"):
                csv_files.append(os.path.join(root, file))
    return csv_files

def get_existing_dates() -> Set[str]:
    """Get set of dates (YYYYMMDD) present in SQLite or CSV files."""
    existing_dates = set()
    # Check SQLite files
    sqlite_files = glob(os.path.join(OUTPUT_BASE_DIR, "*/chart/sqlite/*.db"))
    for file in sqlite_files:
        date_str = os.path.basename(file).split('.')[0]
        if len(date_str) == 8 and date_str.isdigit():
            existing_dates.add(date_str)
    # Check CSV files
    csv_files = glob(os.path.join(OUTPUT_BASE_DIR, "*/chart/csv/*.csv"))
    for file in csv_files:
        date_str = os.path.basename(file).split('.')[0]
        if len(date_str) == 8 and date_str.isdigit():
            existing_dates.add(date_str)
    return existing_dates

def check_csv_date_range(file_path: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Check the date range of a CSV file based on its unix timestamps."""
    try:
        df = pd.read_csv(file_path, usecols=['unix'], dtype={'unix': 'float64'}, low_memory=False)
        if 'unix' not in df.columns or df['unix'].isna().all():
            return None, None
        min_ts = pd.to_datetime(df['unix'].min(), unit='ms', errors='coerce', utc=True)
        max_ts = pd.to_datetime(df['unix'].max(), unit='ms', errors='coerce', utc=True)
        return min_ts, max_ts
    except Exception as e:
        logger.error(f"Error checking date range for {file_path}: {e}")
        return None, None

def process_csv_file(file_path: str, missing_dates: Set[str]) -> None:
    """Process a single CSV file (OHLCV or trade data) if it covers missing dates."""
    try:
        min_ts, max_ts = check_csv_date_range(file_path)
        if min_ts is None or max_ts is None:
            logger.warning(f"Skipping {file_path}: Invalid date range")
            return
        
        # Extract dates in the CSV's range
        csv_dates = set()
        current_ts = min_ts
        while current_ts <= max_ts:
            csv_dates.add(current_ts.strftime("%Y%m%d"))
            current_ts += timedelta(days=1)
        
        # Check if CSV covers any missing dates
        if not csv_dates.intersection(missing_dates):
            logger.info(f"Skipping {file_path}: No missing dates in range {min_ts} to {max_ts}")
            return
        
        # Read CSV with specified dtypes
        df = pd.read_csv(file_path, dtype=CSV_DTYPES, low_memory=False)
        
        # Determine if the CSV is OHLCV or trade data
        is_ohlcv = all(col in df.columns for col in ['open', 'high', 'low', 'close'])
        
        if is_ohlcv:
            # Map OHLCV columns
            df['timestamp'] = pd.to_datetime(df['unix'], unit='ms', errors='coerce').dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            df['open'] = df['open']
            df['high'] = df['high']
            df['low'] = df['low']
            df['close'] = df['close']
            df['volume_btc'] = df['Volume BTC']
            df['volume_usd'] = df.get('Volume USD', df['close'] * df['volume_btc'])
            df['data_type'] = 'ohlcv'
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume_btc', 'volume_usd', 'data_type']]
            # Filter for missing dates
            df['date_str'] = df['timestamp'].str[:10].str.replace("-", "")
            df = df[df['date_str'].isin(missing_dates)]
            df = df.drop(columns=['date_str'])
        else:
            # Map trade data columns
            df['tradeId'] = df.get('id', df.get('tradeId'))
            if 'date' in df.columns:
                df['timestamp'] = pd.to_datetime(df['date'], unit='ms', errors='coerce').dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            elif 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce').dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            else:
                df['timestamp'] = None
            df['price'] = df.get('price')
            df['quantity'] = df.get('amount', df.get('quantity'))
            df['quoteQty'] = df['price'] * df['quantity']
            df['data_type'] = 'trade'
            df = df[['timestamp', 'price', 'quantity', 'quoteQty', 'tradeId', 'data_type']]
            # Filter for missing dates
            df['date_str'] = df['timestamp'].str[:10].str.replace("-", "")
            df = df[df['date_str'].isin(missing_dates)]
            df = df.drop(columns=['date_str'])
        
        df = df.dropna(subset=['timestamp'])
        if df.empty:
            logger.warning(f"No valid data in {file_path} for missing dates")
            return
        
        save_data(df)
        logger.info(f"Processed {len(df)} records from {file_path} for missing dates")
    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")

def process_csv_files(missing_dates: Set[str]) -> None:
    """Process CSV files in ZIP_DATA_DIR that cover missing dates, prioritizing Bitfinex for dates >= 3/17/2022."""
    csv_files = get_all_csv_files(ZIP_DATA_DIR)
    if not csv_files:
        logger.warning("No CSV files found in ZIP_DATA_DIR")
        return
    
    # Prioritize Bitfinex for dates >= 3/17/2022
    bitfinex_files = [f for f in csv_files if 'Bitfinex' in os.path.basename(f)]
    other_files = [f for f in csv_files if 'Bitfinex' not in os.path.basename(f)]
    
    # Process Bitfinex files first for dates >= 3/17/2022
    for file_path in bitfinex_files:
        min_ts, max_ts = check_csv_date_range(file_path)
        if min_ts is None or max_ts is None:
            continue
        if max_ts >= BITFINEX_START_DATE:
            process_csv_file(file_path, missing_dates)
    
    # Process other files (e.g., Bitstamp) for all missing dates
    for file_path in other_files:
        process_csv_file(file_path, missing_dates)

def get_month_dir(timestamp: datetime) -> str:
    return os.path.join(OUTPUT_BASE_DIR, timestamp.strftime("%Y%m"))

def setup_directories(timestamp: datetime) -> None:
    month_dir = get_month_dir(timestamp)
    for sub_dir in ["chart/csv", "chart/sqlite"]:
        dir_path = os.path.join(month_dir, sub_dir)
        try:
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"Directory created/verified: {dir_path}")
        except Exception as e:
            logger.error(f"Error creating directory {dir_path}: {e}")

def setup_sqlite(timestamp: datetime, date_str: str) -> Optional[str]:
    month_dir = get_month_dir(timestamp)
    sqlite_file = os.path.join(month_dir, "chart", "sqlite", f"{date_str}.db")
    create_trades_table_sql = """
        CREATE TABLE IF NOT EXISTS trades (
            timestamp TEXT,
            price REAL,
            quantity REAL,
            quoteQty REAL,
            tradeId TEXT,
            PRIMARY KEY (tradeId)
        )
    """
    create_ohlcv_table_sql = """
        CREATE TABLE IF NOT EXISTS ohlcv (
            timestamp TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume_btc REAL,
            volume_usd REAL,
            PRIMARY KEY (timestamp)
        )
    """
    try:
        conn = sqlite3.connect(sqlite_file)
        cursor = conn.cursor()
        cursor.execute(create_trades_table_sql)
        cursor.execute(create_ohlcv_table_sql)
        conn.commit()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
        if not cursor.fetchone():
            logger.error(f"Failed to create 'trades' table in {sqlite_file}")
            conn.close()
            return None
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ohlcv'")
        if not cursor.fetchone():
            logger.error(f"Failed to create 'ohlcv' table in {sqlite_file}")
            conn.close()
            return None
        logger.info(f"SQLite tables 'trades' and 'ohlcv' confirmed in: {sqlite_file}")
        conn.close()
        return sqlite_file
    except sqlite3.Error as e:
        logger.error(f"SQLite error during setup for {sqlite_file}: {e}")
        return None

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
            if response.status_code == 429:
                wait_time = RATE_LIMIT_WAIT * (2 ** (attempt - 1))
                logger.warning(f"Rate limit hit on attempt {attempt}. Waiting {wait_time} seconds.")
                time.sleep(wait_time)
                continue
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and "code" in data:
                logger.warning(f"API error on attempt {attempt}: {data.get('msg', 'Unknown error')}")
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
                        "tradeId": str(trade["a"]),
                        "data_type": "trade"
                    })
                except (ValueError, KeyError) as e:
                    logger.error(f"Error processing trade {trade}: {e}")
                    continue
            logger.info(f"Fetched {len(data)} trades from {start_time} to {end_time}")
            return pd.DataFrame(trades)
        except (requests.RequestException, ValueError, KeyError) as e:
            logger.warning(f"Error fetching trades on attempt {attempt}: {e}")
            if attempt == MAX_API_RETRIES:
                logger.error(f"Max retries reached for {start_time} to {end_time}")
                return None
            time.sleep(RETRY_DELAY)
    return None

def consolidate_scale_data(missing_dates: Set[str]) -> Optional[pd.DataFrame]:
    scale_files = glob(os.path.join(SCALE_DATA_DIR, "*/csv/*.csv"))
    if not scale_files:
        logger.warning("No scale.py CSV files found")
        return None
    dfs = []
    for file in scale_files:
        try:
            df = pd.read_csv(file, dtype=CSV_DTYPES, low_memory=False)
            if not all(col in df.columns for col in ["timestamp", "price", "quantity", "tradeId"]):
                logger.warning(f"Missing required columns in {file}")
                continue
            df['data_type'] = 'trade'
            df['date_str'] = pd.to_datetime(df['timestamp'], errors='coerce').dt.strftime("%Y%m%d")
            df = df[df['date_str'].isin(missing_dates)]
            df = df.drop(columns=['date_str'])
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
        if combined_df.empty:
            logger.warning("No scale.py data for missing dates")
            return None
        logger.info(f"Consolidated {len(combined_df)} scale.py records for missing dates")
        return combined_df
    return None

def save_data(df: pd.DataFrame) -> None:
    if df.empty or df["timestamp"].isnull().all():
        logger.warning("No valid data to save")
        return
    for date_str in df["timestamp"].str[:10].str.replace("-", "").unique():
        try:
            timestamp = datetime.strptime(date_str, "%Y%m%d")
            month_dir = get_month_dir(timestamp)
            csv_file = os.path.join(month_dir, "chart", "csv", f"{date_str}.csv")
            sqlite_file = os.path.join(month_dir, "chart", "sqlite", f"{date_str}.db")
            date_formatted = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            df_date = df[df["timestamp"].str.startswith(date_formatted)]
            
            setup_directories(timestamp)
            sqlite_file_path = setup_sqlite(timestamp, date_str)
            if not sqlite_file_path:
                logger.error(f"Skipping save due to SQLite setup failure for {date_str}")
                continue
            
            # Handle CSV: Append to existing or create new, remove duplicates
            try:
                if os.path.exists(csv_file):
                    existing_df = pd.read_csv(csv_file)
                    combined_df = pd.concat([existing_df, df_date], ignore_index=True)
                    # Remove duplicates based on timestamp for OHLCV, tradeId for trades
                    if df_date['data_type'].iloc[0] == 'ohlcv':
                        combined_df = combined_df.drop_duplicates(subset=['timestamp', 'data_type'], keep='last')
                    else:
                        combined_df = combined_df.drop_duplicates(subset=['tradeId', 'data_type'], keep='last')
                    combined_df.to_csv(csv_file, index=False)
                    logger.info(f"Updated {csv_file} with {len(df_date)} new records, total {len(combined_df)} records")
                else:
                    df_date.to_csv(csv_file, index=False)
                    logger.info(f"Saved {len(df_date)} records to new CSV: {csv_file}")
            except Exception as e:
                logger.error(f"Error writing to CSV {csv_file}: {e}")
            
            # Handle SQLite: Update or insert based on data_type
            try:
                conn = sqlite3.connect(sqlite_file)
                cursor = conn.cursor()
                if df_date['data_type'].iloc[0] == 'ohlcv':
                    for _, row in df_date.iterrows():
                        cursor.execute("""
                            INSERT OR REPLACE INTO ohlcv (timestamp, open, high, low, close, volume_btc, volume_usd)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (row["timestamp"], row["open"], row["high"], row["low"], row["close"], row["volume_btc"], row["volume_usd"]))
                    logger.info(f"Updated {sqlite_file} with {len(df_date)} OHLCV records")
                else:
                    for _, row in df_date.iterrows():
                        cursor.execute("""
                            INSERT OR IGNORE INTO trades (timestamp, price, quantity, quoteQty, tradeId)
                            VALUES (?, ?, ?, ?, ?)
                        """, (row["timestamp"], row["price"], row["quantity"], row["quoteQty"], row["tradeId"]))
                    logger.info(f"Updated {sqlite_file} with {len(df_date)} trade records")
                conn.commit()
            except sqlite3.Error as e:
                logger.error(f"SQLite error writing to {sqlite_file}: {e}")
            finally:
                if 'conn' in locals():
                    conn.close()
        except Exception as e:
            logger.error(f"Error processing date {date_str}: {e}")

def get_latest_trade_timestamp() -> datetime:
    sqlite_files = glob(os.path.join(OUTPUT_BASE_DIR, "*/chart/sqlite/*.db"))
    latest_timestamp = EARLIEST_TIMESTAMP
    for file in sqlite_files:
        try:
            conn = sqlite3.connect(file)
            cursor = conn.cursor()
            # Check trades table
            cursor.execute("SELECT MAX(timestamp) FROM trades")
            result = cursor.fetchone()[0]
            if result:
                ts = datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=TIMEZONE)
                if ts > latest_timestamp:
                    latest_timestamp = ts
            # Check ohlcv table
            cursor.execute("SELECT MAX(timestamp) FROM ohlcv")
            result = cursor.fetchone()[0]
            if result:
                ts = datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=TIMEZONE)
                if ts > latest_timestamp:
                    latest_timestamp = ts
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"Error querying timestamp from {file}: {e}")
    logger.info(f"Latest timestamp: {latest_timestamp}")
    return latest_timestamp

def main() -> None:
    logger.info("Starting G.R.I.M. Press Ctrl+C to stop.")
    
    # Test API connectivity
    try:
        test_response = requests.get(PING_URL, timeout=5)
        logger.info(f"Binance API ping: {test_response.status_code}")
        if 'x-mbx-used-weight-1m' in test_response.headers:
            logger.info(f"API weight used (1m): {test_response.headers['x-mbx-used-weight-1m']}")
    except Exception as e:
        logger.error(f"Binance API ping failed: {e}")
    
    while True:
        try:
            # Get missing dates from SQLite and CSV files
            existing_dates = get_existing_dates()
            start_date = EARLIEST_TIMESTAMP
            end_date = datetime.now(TIMEZONE)
            all_dates = set()
            current_date = start_date
            while current_date <= end_date:
                all_dates.add(current_date.strftime("%Y%m%d"))
                current_date += timedelta(days=1)
            missing_dates = all_dates - existing_dates
            if not missing_dates:
                logger.info("No missing dates in SQLite or CSV files")
            
            # Process CSV files from ZIP_DATA_DIR for missing dates
            process_csv_files(missing_dates)
            
            # Consolidate scale.py data for missing dates
            scale_df = consolidate_scale_data(missing_dates)
            if scale_df is not None and not scale_df.empty:
                save_data(scale_df)
            
            # Fetch historical trades
            start_time = get_latest_trade_timestamp()
            end_time = datetime.now(TIMEZONE)
            total_seconds = (end_time - start_time).total_seconds()
            if total_seconds > 0:
                logger.info(f"Fetching historical trades from {start_time} to {end_time} ({total_seconds/3600:.2f} hours)")
            while start_time < end_time:
                time_gap = (end_time - start_time).total_seconds() / 3600
                chunk_size = timedelta(days=1) if time_gap > 168 else timedelta(hours=1) if time_gap > 1 else timedelta(minutes=1)
                chunk_end = min(start_time + chunk_size, end_time)
                api_df = fetch_historical_trades(start_time, chunk_end)
                if api_df is not None and not api_df.empty:
                    save_data(api_df)
                progress = ((chunk_end - start_time).total_seconds() / total_seconds * 100) if total_seconds > 0 else 100
                logger.info(f"Progress: {progress:.2f}% completed up to {chunk_end}")
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