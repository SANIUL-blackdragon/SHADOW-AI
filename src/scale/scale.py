import requests
import time
import os
import json
import sqlite3
from datetime import datetime, timezone, timedelta
import glob
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.widgets import Button
from matplotlib.animation import FuncAnimation
from typing import Optional, Dict
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("scale_viz.log")
    ]
)
logger = logging.getLogger(__name__)

# Configuration
CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "symbol": "BTCUSDT",
    "poll_interval": 1,  # Seconds
    "max_api_retries": 3,
    "retry_delay": 2,  # Seconds
    "plot_points_limit": 100,
    "plot_color": "#4CAF50",  # Green
    "base_url": "https://api.binance.com/api/v3/ticker/price",
    "output_base_dir": os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")), "data", "scale")
}

def load_config() -> Dict:
    """Load configuration from config.json or use defaults."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"Loaded configuration from {CONFIG_FILE}")
            return {**DEFAULT_CONFIG, **config}
        else:
            logger.info("No config.json found, using default configuration")
            return DEFAULT_CONFIG
    except Exception as e:
        logger.error(f"Error loading config: {e}, using defaults")
        return DEFAULT_CONFIG

config = load_config()
SYMBOL = config["symbol"]
POLL_INTERVAL = config["poll_interval"]
MAX_API_RETRIES = config["max_api_retries"]
RETRY_DELAY = config["retry_delay"]
PLOT_POINTS_LIMIT = config["plot_points_limit"]
PLOT_COLOR = config["plot_color"]
BASE_URL = config["base_url"]
OUTPUT_BASE_DIR = config["output_base_dir"]
MONTH_DIR = os.path.join(OUTPUT_BASE_DIR, "202507")
CSV_DIR = os.path.join(MONTH_DIR, "csv")
SQLITE_DIR = os.path.join(MONTH_DIR, "sqlite")
TXT_DIR = os.path.join(MONTH_DIR, "txt")
TIMEZONE = timezone(timedelta(hours=6))  # Hardcoded to UTC+6

# Global visualization data
prices = []
timestamps = []
last_file_size = 0
current_date_str = ""
csv_file = ""
running = True  # Flag to control main loop
last_log_time = 0  # Track time of last 30-second log

def get_date_str() -> str:
    """Get date string in UTC+6 for file naming."""
    return datetime.now(TIMEZONE).strftime("%Y%m%d")  # e.g., 20250711

def setup_directories() -> None:
    """Create output directories if they don't exist."""
    for dir_path in [CSV_DIR, SQLITE_DIR, TXT_DIR]:
        try:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            logger.info(f"Directory created/verified: {dir_path}")
        except Exception as e:
            logger.error(f"Error creating directory {dir_path}: {e}")

def setup_sqlite(date_str: str) -> Optional[str]:
    """Initialize SQLite database and trades table."""
    sqlite_file = os.path.join(SQLITE_DIR, f"{date_str}.db")
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
            timestamp = datetime.now(TIMEZONE).strftime("%Y-%m-%dT%H:%M:%S%z")
            logger.info(f"Fetched price: {price} at {timestamp}")
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
    csv_file = os.path.join(CSV_DIR, f"{date_str}.csv")
    sqlite_file = os.path.join(SQLITE_DIR, f"{date_str}.db")
    txt_file = os.path.join(TXT_DIR, f"{date_str}.txt")
    
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
    
    logger.info(f"Saved data: {json.dumps({'ticker': data['ticker'], 'timestamp': data['timestamp'], 'price': data['price']})}")

def load_historical_data() -> None:
    """Load all CSV files from data/scale and its subfolders."""
    global prices, timestamps
    csv_files = glob.glob(os.path.join(OUTPUT_BASE_DIR, "**", "*.csv"), recursive=True)
    prices.clear()
    timestamps.clear()
    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file, parse_dates=['timestamp'])
            for _, row in df.iterrows():
                timestamp = pd.Timestamp(row['timestamp']).to_pydatetime()
                timestamps.append(timestamp)
                prices.append(row['price'])
            logger.info(f"Loaded {len(df)} records from {csv_file}")
        except Exception as e:
            logger.error(f"Error loading {csv_file}: {e}")
    # Sort by timestamp to ensure chronological order
    if timestamps:
        try:
            sorted_pairs = sorted(zip(timestamps, prices), key=lambda x: x[0])
            timestamps[:], prices[:] = zip(*sorted_pairs)
            logger.info(f"Sorted {len(timestamps)} historical data points")
        except Exception as e:
            logger.error(f"Error sorting historical data: {e}")

def stop_program(event) -> None:
    """Handle stop button click to terminate the program."""
    global running
    running = False
    logger.info("Stop button clicked. Stopping S.C.A.L.E.")
    plt.close()

def update_plot(frame, line, fig) -> None:
    """Update the plot with new data from the current CSV file."""
    global last_file_size, prices, timestamps, current_date_str, csv_file
    new_date_str = get_date_str()
    if new_date_str != current_date_str:
        logger.info(f"Date changed to {new_date_str}. Initializing new SQLite database.")
        if setup_sqlite(new_date_str) is None:
            logger.error("Failed to initialize new SQLite database")
            return
        current_date_str = new_date_str
        csv_file = os.path.join(CSV_DIR, f"{current_date_str}.csv")
        last_file_size = 0
        load_historical_data()
    
    # Update plot with new data from main loop
    if os.path.exists(csv_file):
        try:
            current_size = os.path.getsize(csv_file)
            if current_size != last_file_size:
                df = pd.read_csv(csv_file, parse_dates=['timestamp'])
                new_data = df.iloc[-1:]  # Read only the latest row
                for _, row in new_data.iterrows():
                    timestamp = pd.Timestamp(row['timestamp']).to_pydatetime()
                    timestamps.append(timestamp)
                    prices.append(row['price'])
                last_file_size = current_size
                logger.info(f"Updated plot with new data: {row['timestamp']} | {row['price']}")
        except Exception as e:
            logger.error(f"Error reading new data from {csv_file}: {e}")
    
    # Limit to last PLOT_POINTS_LIMIT points for performance
    if len(prices) > PLOT_POINTS_LIMIT:
        prices[:] = prices[-PLOT_POINTS_LIMIT:]
        timestamps[:] = timestamps[-PLOT_POINTS_LIMIT:]
    
    # Debug: Log data state
    logger.debug(f"Plotting {len(timestamps)} points: timestamps={[t.strftime('%Y-%m-%d %H:%M:%S%z') for t in timestamps[:5]]}, prices={prices[:5]}")
    
    # Update plot data incrementally
    try:
        if timestamps and prices:  # Ensure data exists
            line.set_data(timestamps, prices)
            ax = fig.gca()
            ax.relim()
            ax.autoscale_view()
            # Format x-axis as datetime
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            # Set x-ticks to show ~10 labels
            tick_indices = list(range(0, len(timestamps), max(1, len(timestamps)//10)))
            ax.set_xticks([timestamps[i] for i in tick_indices])
            # Ensure y-axis includes all prices
            if prices:
                ax.set_ylim(min(prices) * 0.999, max(prices) * 1.001)
            # Adjust margins to avoid layout issues
            fig.subplots_adjust(bottom=0.2, right=0.85)
        else:
            logger.warning("No data to plot: timestamps or prices empty")
    except Exception as e:
        logger.error(f"Error updating plot: {e}")

def main() -> None:
    """Main loop for S.C.A.L.E."""
    global current_date_str, csv_file, running, last_log_time
    setup_directories()
    current_date_str = get_date_str()
    csv_file = os.path.join(CSV_DIR, f"{current_date_str}.csv")
    sqlite_file = setup_sqlite(current_date_str)
    if sqlite_file is None:
        logger.error("Stopping S.C.A.L.E. due to SQLite setup failure")
        return
    
    load_historical_data()
    
    # Initialize plot
    plt.ion()
    fig, ax = plt.subplots(figsize=(10, 6))
    line, = ax.plot([], [], color=PLOT_COLOR, label='BTC/USDT Price')
    ax.set_xlabel('Time (UTC+6)')
    ax.set_ylabel('Price (USDT)')
    ax.set_title(f'BTC/USDT Live Price Trend ({current_date_str})')
    ax.legend(loc='upper left')
    ax.grid(True)
    
    # Add stop button
    ax_stop = plt.axes([0.85, 0.025, 0.1, 0.04])
    stop_button = Button(ax_stop, 'Stop', color='red', hovercolor='lightcoral')
    stop_button.on_clicked(stop_program)
    
    ani = FuncAnimation(fig, update_plot, fargs=(line, fig), interval=1000)
    
    try:
        while running:
            start_time = time.time()
            new_date_str = get_date_str()
            if new_date_str != current_date_str:
                logger.info(f"Date changed to {new_date_str}. Initializing new SQLite database.")
                sqlite_file = setup_sqlite(new_date_str)
                if sqlite_file is None:
                    logger.error("Stopping S.C.A.L.E. due to SQLite setup failure")
                    running = False
                    break
                current_date_str = new_date_str
                csv_file = os.path.join(CSV_DIR, f"{current_date_str}.csv")
                last_file_size = 0
                load_historical_data()
            
            data = fetch_price()
            save_data(data, current_date_str)
            if data:
                try:
                    timestamp = pd.Timestamp(data['timestamp']).to_pydatetime()
                    timestamps.append(timestamp)
                    prices.append(data['price'])
                    logger.info(f"Added to plot data: {data['timestamp']} | {data['price']}")
                except Exception as e:
                    logger.error(f"Error adding data to plot: {e}")
            
            # Log all timestamps and prices every 30 seconds
            current_time = time.time()
            if current_time - last_log_time >= 5: # Changed to 5 seconds for more frequent logging
                if timestamps and prices:
                    logger.info("Current saved data points:")
                    for ts, price in zip(timestamps, prices):
                        logger.info(f"  Timestamp: {ts.strftime('%Y-%m-%d %H:%M:%S%z')}, Price: {price}")
                    logger.info(f"Total points: {len(timestamps)}")
                else:
                    logger.info("No data points available to log")
                last_log_time = current_time
            
            elapsed = time.time() - start_time
            sleep_time = max(POLL_INTERVAL - elapsed, 0)
            plt.pause(sleep_time)
    except KeyboardInterrupt:
        logger.info("Stopping S.C.A.L.E. via KeyboardInterrupt")
        running = False
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
        running = False
    finally:
        logger.info("Cleaning up and closing plot")
        plt.close()

if __name__ == "__main__":
    main()