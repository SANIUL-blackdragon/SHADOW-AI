import os
import requests
import zipfile
import logging
from datetime import datetime, timedelta
from tqdm import tqdm
import time

# Configure logging
log_file = "download_binance_data.log"
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
BASE_URL = "https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-{}.zip"
OUTPUT_DIR = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")), "data", "zip")
START_DATE = datetime(2022, 5, 1)
END_DATE = datetime(2025, 6, 30)
MAX_RETRIES = 3
RETRY_DELAY = 5
RATE_LIMIT_WAIT = 120

def setup_directories():
    """Create output directory if it doesn't exist."""
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        logger.info(f"Output directory created/verified: {OUTPUT_DIR}")
    except Exception as e:
        logger.error(f"Error creating directory {OUTPUT_DIR}: {e}")
        raise

def download_and_extract(date: datetime):
    """Download and extract ZIP file for a given date."""
    date_str = date.strftime("%Y-%m-%d")
    zip_url = BASE_URL.format(date_str)
    zip_filename = os.path.join(OUTPUT_DIR, f"BTCUSDT-aggTrades-{date_str}.zip")
    csv_filename = os.path.join(OUTPUT_DIR, f"BTCUSDT-aggTrades-{date_str}.csv")

    # Skip if CSV already exists
    if os.path.exists(csv_filename):
        logger.info(f"Skipping {csv_filename}: File already exists")
        return

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.debug(f"Downloading {zip_url}")
            response = requests.get(zip_url, stream=True, timeout=10)
            if response.status_code == 429:
                wait_time = RATE_LIMIT_WAIT * (2 ** (attempt - 1))
                logger.warning(f"Rate limit hit on attempt {attempt} for {date_str}. Waiting {wait_time} seconds.")
                time.sleep(wait_time)
                continue
            response.raise_for_status()

            # Save ZIP file
            with open(zip_filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            logger.info(f"Downloaded {zip_filename}")

            # Extract CSV
            with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
                zip_ref.extractall(OUTPUT_DIR)
            logger.info(f"Extracted {csv_filename}")

            # Remove ZIP file
            os.remove(zip_filename)
            logger.info(f"Removed {zip_filename}")
            break

        except (requests.RequestException, zipfile.BadZipFile) as e:
            logger.warning(f"Error downloading/extracting {date_str} on attempt {attempt}: {e}")
            if attempt == MAX_RETRIES:
                logger.error(f"Failed to download/extract {date_str} after {MAX_RETRIES} attempts")
                return
            time.sleep(RETRY_DELAY)

def main():
    """Download and extract daily BTCUSDT aggTrades CSVs from Binance."""
    logger.info("Starting Binance data download script. Press Ctrl+C to stop.")
    setup_directories()

    total_days = (END_DATE - START_DATE).days + 1
    current_date = START_DATE

    for _ in tqdm(range(total_days), desc="Downloading files"):
        try:
            download_and_extract(current_date)
            current_date += timedelta(days=1)
        except KeyboardInterrupt:
            logger.info("Stopping download script via Ctrl+C")
            break
        except Exception as e:
            logger.error(f"Error processing {current_date.strftime('%Y-%m-%d')}: {e}")
            current_date += timedelta(days=1)
            continue

    logger.info("Download script completed")

if __name__ == "__main__":
    main()