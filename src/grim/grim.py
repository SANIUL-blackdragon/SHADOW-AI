import os
import requests
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timezone, timedelta
import logging
from glob import glob
import time
import hashlib
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
EARLIEST_TIMESTAMP = datetime(2012, 1, 1, tzinfo=TIMEZONE)
RATE_LIMIT_WAIT = 120
BITFINEX_START_DATE = datetime(2022, 3, 17, 6, 12, tzinfo=TIMEZONE)

# Binance aggregated trade columns (no headers)
binance_trade_columns = [
    'agg_trade_id', 'price', 'quantity', 'first_trade_id', 
    'last_trade_id', 'transact_time', 'is_buyer_maker', 'is_best_match'
]

# Define dtypes for CSV processing (use numpy types and 'object' for strings)
CSV_DTYPES = {
    'unix': np.float64,
    'date': 'object',
    'symbol': 'object',
    'open': np.float64,
    'high': np.float64,
    'low': np.float64,
    'close': np.float64,
    'Volume BTC': np.float64,
    'Volume USD': np.float64,
    'id': 'object',
    'tradeId': 'object',
    'price': np.float64,
    'amount': np.float64,
    'quantity': np.float64,
    'agg_trade_id': 'object',
    'transact_time': np.float64,
    'first_trade_id': 'object',
    'last_trade_id': 'object',
    'is_buyer_maker': 'object',
    'is_best_match': 'object'
}

def get_all_csv_files(directory: str) -> list:
    """Find all CSV files in directory and subfolders."""
    csv_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".csv"):
                full_path = os.path.join(root, file)
                csv_files.append(full_path)
                logger.debug(f"Found CSV file: {full_path}")
    return csv_files

def get_existing_dates() -> Set[str]:
    """Get set of dates (YYYYMMDD) present in SQLite or CSV files."""
    existing_dates = set()
    sqlite_files = glob(os.path.join(OUTPUT_BASE_DIR, "*/chart/sqlite/*.db"))
    for file in sqlite_files:
        date_str = os.path.basename(file).split('.')[0]
        if len(date_str) == 8 and date_str.isdigit():
            existing_dates.add(date_str)
    csv_files = glob(os.path.join(OUTPUT_BASE_DIR, "*/chart/csv/*.csv"))
    for file in csv_files:
        date_str = os.path.basename(file).split('.')[0]
        if len(date_str) == 8 and date_str.isdigit():
            existing_dates.add(date_str)
    logger.debug(f"Existing dates: {sorted(existing_dates)}")
    return existing_dates

def detect_csv_format(file_path: str) -> tuple[bool, Optional[list], bool]:
    """Detect if CSV has headers, return column names, and identify if OHLCV."""
    try:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip().split(',')
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin1') as f:
                first_line = f.readline().strip().split(',')
                logger.warning(f"File {file_path} used latin1 encoding fallback")
        file_size = os.path.getsize(file_path)
        logger.debug(f"File {file_path} size: {file_size} bytes")
        is_header = any(
            s.lower() in ['unix', 'date', 'symbol', 'open', 'price', 'transact_time', 'close', 'Volume BTC'] 
            for s in first_line
        )
        is_ohlcv = is_header and all(col in first_line for col in ['open', 'high', 'low', 'close'])
        if 'aggTrades' in os.path.basename(file_path) and not is_header:
            return False, binance_trade_columns, False
        logger.debug(f"CSV {file_path} first line: {first_line}")
        return is_header, None if is_header else binance_trade_columns, is_ohlcv
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        return True, None, False
    except Exception as e:
        logger.error(f"Error detecting CSV format for {file_path}: {e}")
        return True, None, False

def check_csv_date_range(file_path: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Check the date range of a CSV file based on its timestamp column."""
    try:
        has_headers, column_names, is_ohlcv = detect_csv_format(file_path)
        timestamp_col = None
        if 'aggTrades' in os.path.basename(file_path) and not has_headers:
            df = pd.read_csv(
                file_path, header=None, names=binance_trade_columns,
                dtype=CSV_DTYPES, low_memory=False, engine='python', encoding='utf-8'
            )
            logger.debug(f"Headerless CSV {file_path} shape: {df.shape}")
            logger.debug(f"First 3 rows:\n{df.head(3).to_string()}")
            timestamp_col = 'transact_time'
        else:
            for col in ['unix', 'date', 'transact_time']:
                try:
                    df = pd.read_csv(
                        file_path, usecols=[col], header=0 if has_headers else None,
                        dtype={col: np.float64}, low_memory=False, engine='python', encoding='utf-8'
                    )
                    timestamp_col = col
                    break
                except ValueError:
                    continue
            if not timestamp_col:
                logger.warning(f"No valid timestamp column ('unix', 'date', or 'transact_time') in {file_path}")
                return None, None
        
        if timestamp_col not in df.columns or df[timestamp_col].isna().all():
            logger.warning(f"'{timestamp_col}' column missing or all NaN in {file_path}")
            return None, None
        
        for unit in ['ms', 's']:
            try:
                df['datetime'] = pd.to_datetime(df[timestamp_col], unit=unit, errors='coerce', utc=True)
                if not df['datetime'].isna().all():
                    break
            except Exception as e:
                logger.debug(f"Failed to parse timestamps with unit={unit} in {file_path}: {e}")
                continue
        else:
            logger.warning(f"Could not parse timestamps in {file_path}")
            return None, None
        
        df = df.dropna(subset=['datetime'])
        if df.empty:
            logger.warning(f"No valid timestamps in {file_path}")
            return None, None
        
        min_ts = df['datetime'].min()
        max_ts = df['datetime'].max()
        if min_ts.year < 2000 or max_ts.year < 2000:
            logger.warning(f"Invalid date range in {file_path}: {min_ts} to {max_ts}")
            return None, None
        logger.info(f"Date range for {file_path}: {min_ts} to {max_ts}")
        return min_ts, max_ts
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        return None, None
    except pd.errors.EmptyDataError:
        logger.warning(f"Skipping {file_path}: File is empty")
        return None, None
    except pd.errors.ParserError as e:
        logger.error(f"Parser error reading {file_path}: {e}")
        return None, None
    except Exception as e:
        logger.error(f"Unexpected error checking date range for {file_path}: {e}")
        return None, None

def migrate_legacy_tables(sqlite_file: str) -> None:
    """Merge legacy 'trades' and 'ohlcv' tables into 'market_data'."""
    try:
        conn = sqlite3.connect(sqlite_file)
        cursor = conn.cursor()
        
        # Create market_data table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_data (
                timestamp TEXT,
                price REAL,
                quantity REAL,
                quoteQty REAL,
                tradeId TEXT,
                symbol TEXT,
                PRIMARY KEY (timestamp, symbol, tradeId)
            )
        """)
        
        # Migrate 'trades' table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
        if cursor.fetchone():
            logger.info(f"Migrating legacy 'trades' table in {sqlite_file}")
            cursor.execute("SELECT timestamp, price, quantity, quoteQty, tradeId, symbol FROM trades")
            trades_data = cursor.fetchall()
            for row in trades_data:
                cursor.execute("""
                    INSERT OR REPLACE INTO market_data (
                        timestamp, price, quantity, quoteQty, tradeId, symbol
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, row)
            logger.info(f"Migrated {len(trades_data)} records from 'trades' to 'market_data' in {sqlite_file}")
        
        # Migrate 'ohlcv' table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ohlcv'")
        if cursor.fetchone():
            logger.info(f"Migrating legacy 'ohlcv' table in {sqlite_file}")
            cursor.execute("SELECT unix, close, `Volume BTC` FROM ohlcv")
            ohlcv_data = cursor.fetchall()
            for idx, row in enumerate(ohlcv_data):
                timestamp_ms, close, volume_btc = row
                timestamp = datetime.fromtimestamp(timestamp_ms / 1000, tz=TIMEZONE).strftime("%Y-%m-%dT%H:%M:%SZ")
                price = float(close)
                quantity = float(volume_btc) if volume_btc is not None else 0.0
                quote_qty = price * quantity
                # Generate synthetic tradeId for OHLCV
                trade_id = hashlib.md5(f"{timestamp}_{idx}".encode()).hexdigest()
                cursor.execute("""
                    INSERT OR REPLACE INTO market_data (
                        timestamp, price, quantity, quoteQty, tradeId, symbol
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (timestamp, price, quantity, quote_qty, trade_id, SYMBOL))
            logger.info(f"Migrated {len(ohlcv_data)} records from 'ohlcv' to 'market_data' in {sqlite_file}")
        
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        logger.error(f"Error migrating legacy tables in {sqlite_file}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error migrating {sqlite_file}: {e}")

def process_csv_file(file_path: str, missing_dates: Set[str]) -> None:
    """Process a single CSV file (trade or OHLCV) into unified format."""
    try:
        min_ts, max_ts = check_csv_date_range(file_path)
        if min_ts is None or max_ts is None:
            logger.warning(f"Skipping {file_path}: Invalid date range")
            return
        
        csv_dates = set()
        current_ts = min_ts
        while current_ts <= max_ts:
            csv_dates.add(current_ts.strftime("%Y%m%d"))
            current_ts += timedelta(days=1)
        
        if not csv_dates.intersection(missing_dates):
            logger.info(f"Skipping {file_path}: No missing dates in range {min_ts} to {max_ts}")
            return
        
        has_headers, column_names, is_ohlcv = detect_csv_format(file_path)
        try:
            if 'aggTrades' in os.path.basename(file_path) and not has_headers:
                df = pd.read_csv(
                    file_path, header=None, names=binance_trade_columns,
                    dtype=CSV_DTYPES, low_memory=False, engine='python', encoding='utf-8'
                )
            else:
                df = pd.read_csv(
                    file_path, header=0 if has_headers else None,
                    names=column_names if not has_headers else None,
                    dtype=CSV_DTYPES, low_memory=False, engine='python', encoding='utf-8'
                )
        except UnicodeDecodeError:
            df = pd.read_csv(
                file_path, header=0 if has_headers else None,
                names=column_names if not has_headers else None,
                dtype=CSV_DTYPES, low_memory=False, engine='python', encoding='latin1'
            )
            logger.warning(f"File {file_path} used latin1 encoding fallback")
        logger.debug(f"Loaded CSV {file_path} with columns: {df.columns.tolist()}")
        logger.debug(f"First 3 rows:\n{df.head(3).to_string()}")
        
        if is_ohlcv:
            # Process OHLCV data
            for unit in ['ms', 's']:
                try:
                    df['timestamp'] = pd.to_datetime(df['unix'], unit=unit, errors='coerce', utc=True).dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                    if not df['timestamp'].isna().all():
                        break
                except Exception:
                    continue
            else:
                logger.warning(f"No valid timestamp in {file_path}")
                df['timestamp'] = None
            df['price'] = df['close']
            df['quantity'] = df.get('Volume BTC', 0.0)
            df['quoteQty'] = df['price'] * df['quantity']
            df['symbol'] = SYMBOL
            # Generate synthetic tradeId
            df['tradeId'] = [hashlib.md5(f"{ts}_{idx}".encode()).hexdigest() for idx, ts in enumerate(df['timestamp'])]
        else:
            # Process trade data
            is_binance_trade = 'aggTrades' in os.path.basename(file_path)
            if is_binance_trade:
                for unit in ['ms', 's']:
                    try:
                        df['timestamp'] = pd.to_datetime(df['transact_time'], unit=unit, errors='coerce', utc=True).dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                        if not df['timestamp'].isna().all():
                            break
                    except Exception:
                        continue
                else:
                    logger.warning(f"No valid timestamp in {file_path}")
                    df['timestamp'] = None
                df['tradeId'] = df['agg_trade_id']
                df['price'] = df['price']
                df['quantity'] = df['quantity']
                df['quoteQty'] = df['price'] * df['quantity']
                df['symbol'] = SYMBOL
            else:
                df['tradeId'] = df.get('id', df.get('tradeId'))
                timestamp_col = 'date' if 'date' in df.columns else 'timestamp' if 'timestamp' in df.columns else None
                if timestamp_col:
                    for unit in ['ms', 's']:
                        try:
                            df['timestamp'] = pd.to_datetime(df[timestamp_col], unit=unit, errors='coerce', utc=True).dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                            if not df['timestamp'].isna().all():
                                break
                        except Exception:
                            continue
                    else:
                        logger.warning(f"No valid timestamp in {file_path}")
                        df['timestamp'] = None
                else:
                    logger.warning(f"No timestamp column in {file_path}")
                    df['timestamp'] = None
                df['price'] = df.get('price')
                df['quantity'] = df.get('amount', df.get('quantity'))
                df['quoteQty'] = df['price'] * df['quantity']
                df['symbol'] = df.get('symbol', SYMBOL)
        
        df = df[['timestamp', 'price', 'quantity', 'quoteQty', 'tradeId', 'symbol']]
        df = df.dropna(subset=['timestamp', 'price', 'quantity', 'tradeId'])
        df['date_str'] = df['timestamp'].str[:10].str.replace("-", "")
        df = df[df['date_str'].isin(missing_dates)]
        df = df.drop(columns=['date_str'])
        
        if df.empty:
            logger.warning(f"No valid data in {file_path} for missing dates")
            return
        
        save_data(df)
        logger.info(f"Processed {len(df)} records from {file_path} (OHLCV={is_ohlcv})")
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
    except pd.errors.EmptyDataError:
        logger.warning(f"Skipping {file_path}: File is empty")
    except pd.errors.ParserError as e:
        logger.error(f"Parser error reading {file_path}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error processing {file_path}: {e}")

def process_csv_files(missing_dates: Set[str]) -> None:
    """Process CSV files in ZIP_DATA_DIR for missing dates."""
    csv_files = get_all_csv_files(ZIP_DATA_DIR)
    if not csv_files:
        logger.warning("No CSV files found in ZIP_DATA_DIR")
        return
    
    bitfinex_files = [f for f in csv_files if 'Bitfinex' in os.path.basename(f)]
    other_files = [f for f in csv_files if 'Bitfinex' not in os.path.basename(f)]
    
    logger.info(f"Processing Bitfinex files: {bitfinex_files}")
    for file_path in bitfinex_files:
        min_ts, max_ts = check_csv_date_range(file_path)
        if min_ts and max_ts and max_ts >= BITFINEX_START_DATE:
            process_csv_file(file_path, missing_dates)
    
    logger.info(f"Processing other files: {other_files}")
    for file_path in other_files:
        process_csv_file(file_path, missing_dates)

def get_month_dir(timestamp: datetime) -> str:
    """Get directory for a given timestamp's year and month."""
    return os.path.join(OUTPUT_BASE_DIR, timestamp.strftime("%Y%m"))

def setup_directories(timestamp: datetime) -> None:
    """Create necessary directories for storing data."""
    month_dir = get_month_dir(timestamp)
    for sub_dir in ["chart/csv", "chart/sqlite"]:
        dir_path = os.path.join(month_dir, sub_dir)
        try:
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"Directory created/verified: {dir_path}")
        except Exception as e:
            logger.error(f"Error creating directory {dir_path}: {e}")

def setup_sqlite(timestamp: datetime, date_str: str) -> Optional[str]:
    """Set up SQLite database for a given date and migrate legacy tables."""
    month_dir = get_month_dir(timestamp)
    sqlite_file = os.path.join(month_dir, "chart", "sqlite", f"{date_str}.db")
    create_table_sql = """
        CREATE TABLE IF NOT EXISTS market_data (
            timestamp TEXT,
            price REAL,
            quantity REAL,
            quoteQty REAL,
            tradeId TEXT,
            symbol TEXT,
            PRIMARY KEY (timestamp, symbol, tradeId)
        )
    """
    try:
        migrate_legacy_tables(sqlite_file)
        conn = sqlite3.connect(sqlite_file)
        cursor = conn.cursor()
        cursor.execute(create_table_sql)
        conn.commit()
        conn.close()
        logger.info(f"SQLite table 'market_data' created in: {sqlite_file}")
        return sqlite_file
    except sqlite3.Error as e:
        logger.error(f"SQLite error for {sqlite_file}: {e}")
        return None

def fetch_historical_trades(start_time: datetime, end_time: datetime) -> Optional[pd.DataFrame]:
    """Fetch historical trades from Binance API."""
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
                        "symbol": SYMBOL
                    })
                except (ValueError, KeyError) as e:
                    logger.error(f"Error processing trade {trade}: {e}")
                    continue
            logger.info(f"Fetched {len(data)} trades from {start_time} to {end_time}")
            return pd.DataFrame(trades)
        except requests.RequestException as e:
            logger.warning(f"Request error on attempt {attempt}: {e}")
            if attempt == MAX_API_RETRIES:
                logger.error(f"Max retries reached for {start_time} to {end_time}")
                return None
            time.sleep(RETRY_DELAY)
        except ValueError as e:
            logger.warning(f"Value error on attempt {attempt}: {e}")
            if attempt == MAX_API_RETRIES:
                logger.error(f"Max retries reached for {start_time} to {end_time}")
                return None
            time.sleep(RETRY_DELAY)
        except KeyError as e:
            logger.warning(f"Key error on attempt {attempt}: {e}")
            if attempt == MAX_API_RETRIES:
                logger.error(f"Max retries reached for {start_time} to {end_time}")
                return None
            time.sleep(RETRY_DELAY)
    return None

def consolidate_scale_data(missing_dates: Set[str]) -> Optional[pd.DataFrame]:
    """Consolidate scale.py CSV data (trade or OHLCV) for missing dates."""
    scale_files = glob(os.path.join(SCALE_DATA_DIR, "*/csv/*.csv"))
    if not scale_files:
        logger.warning("No scale.py CSV files found")
        return None
    dfs = []
    for file in scale_files:
        try:
            has_headers, column_names, is_ohlcv = detect_csv_format(file)
            try:
                if 'aggTrades' in os.path.basename(file) and not has_headers:
                    df = pd.read_csv(
                        file, header=None, names=binance_trade_columns,
                        dtype=CSV_DTYPES, low_memory=False, engine='python', encoding='utf-8'
                    )
                else:
                    df = pd.read_csv(
                        file, header=0 if has_headers else None,
                        names=column_names if not has_headers else None,
                        dtype=CSV_DTYPES, low_memory=False, engine='python', encoding='utf-8'
                    )
            except UnicodeDecodeError:
                df = pd.read_csv(
                    file, header=0 if has_headers else None,
                    names=column_names if not has_headers else None,
                    dtype=CSV_DTYPES, low_memory=False, engine='python', encoding='latin1'
                )
                logger.warning(f"File {file} used latin1 encoding fallback")
            logger.debug(f"Loaded scale CSV {file} with columns: {df.columns.tolist()}")
            logger.debug(f"First 3 rows:\n{df.head(3).to_string()}")
            
            if is_ohlcv:
                # Process OHLCV data
                for unit in ['ms', 's']:
                    try:
                        df['timestamp'] = pd.to_datetime(df['unix'], unit=unit, errors='coerce', utc=True).dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                        if not df['timestamp'].isna().all():
                            break
                    except Exception:
                        continue
                else:
                    logger.warning(f"No valid timestamp in {file}")
                    df['timestamp'] = None
                df['price'] = df['close']
                df['quantity'] = df.get('Volume BTC', 0.0)
                df['quoteQty'] = df['price'] * df['quantity']
                df['symbol'] = SYMBOL
                # Generate synthetic tradeId
                df['tradeId'] = [hashlib.md5(f"{ts}_{idx}".encode()).hexdigest() for idx, ts in enumerate(df['timestamp'])]
            else:
                # Process trade data
                if 'aggTrades' in os.path.basename(file):
                    for unit in ['ms', 's']:
                        try:
                            df['timestamp'] = pd.to_datetime(df['transact_time'], unit=unit, errors='coerce', utc=True).dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                            if not df['timestamp'].isna().all():
                                break
                        except Exception:
                            continue
                    else:
                        logger.warning(f"No valid timestamp in {file}")
                        df['timestamp'] = None
                    df['tradeId'] = df['agg_trade_id']
                    df['price'] = df['price']
                    df['quantity'] = df['quantity']
                    df['quoteQty'] = df['price'] * df['quantity']
                    df['symbol'] = SYMBOL
                else:
                    df['tradeId'] = df.get('id', df.get('tradeId'))
                    timestamp_col = 'date' if 'date' in df.columns else 'timestamp' if 'timestamp' in df.columns else None
                    if timestamp_col:
                        for unit in ['ms', 's']:
                            try:
                                df['timestamp'] = pd.to_datetime(df[timestamp_col], unit=unit, errors='coerce', utc=True).dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                                if not df['timestamp'].isna().all():
                                    break
                            except Exception:
                                continue
                        else:
                            logger.warning(f"No valid timestamp in {file}")
                            df['timestamp'] = None
                    else:
                        logger.warning(f"No timestamp column in {file}")
                        df['timestamp'] = None
                    df['price'] = df.get('price')
                    df['quantity'] = df.get('amount', df.get('quantity'))
                    df['quoteQty'] = df['price'] * df['quantity']
                    df['symbol'] = df.get('symbol', SYMBOL)
            
            df = df[['timestamp', 'price', 'quantity', 'quoteQty', 'tradeId', 'symbol']]
            df = df.dropna(subset=['timestamp', 'price', 'quantity', 'tradeId'])
            df['date_str'] = pd.to_datetime(df['timestamp'], errors='coerce').dt.strftime("%Y%m%d")
            df = df[df['date_str'].isin(missing_dates)]
            df = df.drop(columns=['date_str'])
            if not df.empty:
                dfs.append(df)
        except FileNotFoundError:
            logger.error(f"File not found: {file}")
        except pd.errors.EmptyDataError:
            logger.warning(f"Skipping {file}: File is empty")
        except pd.errors.ParserError as e:
            logger.error(f"Parser error reading {file}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error reading scale CSV {file}: {e}")
    if dfs:
        combined_df = pd.concat(dfs, ignore_index=True)
        combined_df["timestamp"] = pd.to_datetime(combined_df["timestamp"], errors='coerce')
        combined_df = combined_df.dropna(subset=["timestamp"])
        combined_df = combined_df.sort_values("timestamp").drop_duplicates(subset=["timestamp", "symbol", "tradeId"], keep='last')
        combined_df["timestamp"] = combined_df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        if combined_df.empty:
            logger.warning("No scale.py data for missing dates")
            return None
        logger.info(f"Consolidated {len(combined_df)} scale.py records")
        return combined_df
    return None

def save_data(df: pd.DataFrame) -> None:
    """Save data to CSV and SQLite, handling duplicates."""
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
            
            try:
                if os.path.exists(csv_file):
                    try:
                        existing_df = pd.read_csv(csv_file, dtype=CSV_DTYPES, engine='python', encoding='utf-8', errors='ignore')
                    except UnicodeDecodeError:
                        existing_df = pd.read_csv(csv_file, dtype=CSV_DTYPES, engine='python', encoding='latin1')
                        logger.warning(f"CSV {csv_file} used latin1 encoding fallback")
                    combined_df = pd.concat([existing_df, df_date], ignore_index=True)
                    combined_df = combined_df.drop_duplicates(subset=['timestamp', 'symbol', 'tradeId'], keep='last')
                    combined_df.to_csv(csv_file, index=False)
                    logger.info(f"Updated {csv_file} with {len(df_date)} new records, total {len(combined_df)} records")
                else:
                    df_date.to_csv(csv_file, index=False)
                    logger.info(f"Saved {len(df_date)} records to new CSV: {csv_file}")
            except (IOError, pd.errors.EmptyDataError, pd.errors.ParserError) as e:
                logger.error(f"Error writing/reading CSV {csv_file}: {e}")
            
            try:
                conn = sqlite3.connect(sqlite_file)
                cursor = conn.cursor()
                for _, row in df_date.iterrows():
                    cursor.execute("""
                        INSERT OR REPLACE INTO market_data (
                            timestamp, price, quantity, quoteQty, tradeId, symbol
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        row["timestamp"], row["price"], row["quantity"], row["quoteQty"],
                        row["tradeId"], row["symbol"]
                    ))
                conn.commit()
                logger.info(f"Updated {sqlite_file} with {len(df_date)} records")
            except sqlite3.Error as e:
                logger.error(f"SQLite error writing to {sqlite_file}: {e}")
            finally:
                if conn:
                    conn.close()
        except Exception as e:
            logger.error(f"Error processing date {date_str}: {e}")

def get_latest_timestamp() -> datetime:
    """Get the latest timestamp from SQLite databases."""
    sqlite_files = glob(os.path.join(OUTPUT_BASE_DIR, "*/chart/sqlite/*.db"))
    latest_timestamp = EARLIEST_TIMESTAMP
    for file in sqlite_files:
        try:
            conn = sqlite3.connect(file)
            cursor = conn.cursor()
            for table in ['market_data', 'trades', 'ohlcv']:
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
                if cursor.fetchone():
                    if table == 'ohlcv':
                        cursor.execute("SELECT MAX(unix) FROM ohlcv")
                        result = cursor.fetchone()[0]
                        if result:
                            ts = datetime.fromtimestamp(result / 1000, tz=TIMEZONE)
                            latest_timestamp = max(latest_timestamp, ts)
                    else:
                        cursor.execute(f"SELECT MAX(timestamp) FROM {table}")
                        result = cursor.fetchone()[0]
                        if result:
                            ts = datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=TIMEZONE)
                            latest_timestamp = max(latest_timestamp, ts)
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"Error querying timestamp from {file}: {e}")
    logger.info(f"Latest timestamp: {latest_timestamp}")
    return latest_timestamp

def main() -> None:
    """Main loop for G.R.I.M."""
    logger.info("Starting G.R.I.M. Press Ctrl+C to stop.")
    
    try:
        test_response = requests.get(PING_URL, timeout=5)
        logger.info(f"Binance API ping: {test_response.status_code}")
        if 'x-mbx-used-weight-1m' in test_response.headers:
            logger.info(f"API weight used (1m): {test_response.headers['x-mbx-used-weight-1m']}")
    except Exception as e:
        logger.error(f"Binance API ping failed: {e}")
    
    while True:
        try:
            existing_dates = get_existing_dates()
            start_date = EARLIEST_TIMESTAMP
            end_date = datetime.now(TIMEZONE)
            all_dates = set()
            current_date = start_date
            while current_date <= end_date:
                all_dates.add(current_date.strftime("%Y%m%d"))
                current_date += timedelta(days=1)
            missing_dates = all_dates - existing_dates
            logger.info(f"Missing dates: {sorted(missing_dates)}")
            
            process_csv_files(missing_dates)
            
            scale_df = consolidate_scale_data(missing_dates)
            if scale_df is not None and not scale_df.empty:
                save_data(scale_df)
            
            start_time = get_latest_timestamp()
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