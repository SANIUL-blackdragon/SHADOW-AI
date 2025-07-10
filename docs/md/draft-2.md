# What S.C.A.L.E. Does in SHADOW AI

S.C.A.L.E. (Signal Capture & Live Extraction) is a critical submodule of the SHADOW AI system, designed to serve as the real-time data acquisition engine. **It captures live market data directly from the Binance API and delivers it to the SHADOW AI system for further processing, while providing live visualization of price data through a terminal-based interface, displaying trends from all historical and live data in a unified 1-second framework.** Below is a detailed breakdown of its purpose, functionality, and operational mechanics.

---

## Purpose
S.C.A.L.E. acts as the "eyes" of SHADOW AI, providing a continuous stream of live price data for a single selected asset (e.g., BINANCE:BTCUSDT) from the Binance API. Its primary mission is to extract price information and timestamps in real-time, ensuring the system has up-to-date market signals to drive predictions and trading decisions. **Additionally, it visualizes live and historical price data to aid monitoring and debugging, presenting trends in a 1-second time framework without interpolating missing timestamps, ensuring gaps (e.g., due to network delays or API errors) are preserved as discontinuities in the visualization.**

---

## Architecture
**S.C.A.L.E. is a single Python-based component that directly queries the Binance API (`/api/v3/ticker/price`) every 1 second, integrating data capture, logging, and visualization into a streamlined pipeline. It eliminates the need for browser extensions or external servers, relying solely on Python libraries for efficiency and simplicity.**

### Functionality
- **Platform**: Built in Python 3.x, using the `requests` library to query the Binance API for real-time price data, `sqlite3` for structured storage, `pandas` for data handling, and `matplotlib` for visualization, all optimized for consumer hardware (16 GB RAM, no GPU).
- **Key Features**:
  - **Data Extraction**: Captures the current price of the selected asset (e.g., BINANCE:BTCUSDT) every 1 second, along with UTC timestamps, using the Binance API endpoint `/api/v3/ticker/price` (weight: 2, well within the 6,000 weight/minute limit).
  - **Logging**: Stores all incoming data in a triple-format system:
    - **SQLite**: Daily `.db` files (e.g., `20250711.db`) with a `trades` table (`timestamp TEXT, price REAL`) for structured querying, enabling efficient analysis by downstream modules like PHANTOM.
    - **CSV**: Daily `.csv` files (e.g., `20250711.csv`) with `timestamp,price` columns for human-readable backups, suitable for manual inspection or external tools.
    - **TXT**: Daily `.txt` files (e.g., `20250711.txt`) with JSON lines for compatibility with other SHADOW AI submodules (e.g., G.R.I.M. for indexing), formatted as `{"ticker": "BINANCE:BTCUSDT", "timestamp": "2025-07-10T19:04:08Z", "price": 113551.35}`.
    - **Folder Structure**:
      ```
      /data/scale
       ├── 202507/
       │   ├── csv/
       │   │   └── 20250711.csv
       │   ├── sqlite/
       │   │   └── 20250711.db
       │   └── txt/
       │       └── 20250711.txt
       ├── 202508/
       │   ├── csv/
       │   │   └── 20250801.csv
       │   ├── sqlite/
       │   │   └── 20250801.db
       │   └── txt/
       │       └── 20250801.txt
      ```
  - **Command-Line Interface (CUI)**: Provides a terminal-based status monitor (no GUI), displaying:
    - **Real-Time Logs**: Prints fetched prices (e.g., `Fetched price: 113551.35 at 2025-07-10T19:04:08Z`) and save confirmations (e.g., `Saved data: {"ticker": "BINANCE:BTCUSDT", "timestamp": ..., "price": 113551.35}`).
    - **Live Visualization**: A live-updating plot using `matplotlib`, showing prices from all CSV files in `/data/scale` and its subfolders (e.g., `202507/csv/20250710.csv`, `20250711.csv`). The plot uses a 1-second time framework, with timestamps (HH:MM:SS) on the x-axis and prices (USDT) on the y-axis. Gaps in timestamps (e.g., 8-second or 39-second skips due to network delays) are preserved as discontinuities, with no interpolation or stitching. The plot updates every second, limited to the last 100 data points for performance, and uses a green line (`#4CAF50`) for visibility.
  - **Data Integrity**: Captures all data, including gaps, based on API responses. If gaps are detected (e.g., missing seconds due to network latency), S.C.A.L.E. logs them as-is without filling. **For historical gaps, it can fetch data retroactively using the Binance API `/api/v3/klines` endpoint (1-minute candles) when instructed by SHADOW AI, ensuring completeness for backtesting by G.R.I.M. or PHANTOM.**
  - **Error Handling**: Implements robust error handling for API failures:
    - Retries up to 3 times with a 2-second delay if the API is unreachable or returns errors (e.g., rate limits, HTTP 429).
    - Logs errors to the console (e.g., `API error on attempt 2: Too Many Requests`) without interrupting the main loop.
    - If visualization fails (e.g., due to file access issues), logs the error (e.g., `Error reading new data from 20250711.csv: Permission denied`) without stopping data capture.
  - **No Security Overhead**: Uses public Binance API endpoints without API keys or authentication, designed for personal use with minimal setup.
- **Data Format**: Stores data in the following JSON structure for TXT files, with CSV and SQLite using `timestamp,price`:
  ```json
  {
    "ticker": "BINANCE:BTCUSDT",
    "price": 113551.35,
    "timestamp": "2025-07-10T19:04:08Z"
  }