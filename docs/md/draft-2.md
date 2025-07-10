# What S.C.A.L.E. Does in SHADOW AI

S.C.A.L.E. (Signal Capture & Live Extraction) is a critical submodule of the SHADOW AI system, designed to serve as the real-time data acquisition engine. It is responsible for capturing live market data from TradingView charts and delivering it to the SHADOW AI backend for further processing. Below is a detailed breakdown of its purpose, functionality, and operational mechanics.

---

## Purpose
S.C.A.L.E. acts as the "eyes" of SHADOW AI, providing a continuous stream of live price data for a single selected asset (e.g., stocks, indices, forex, commodities) from TradingView. Its primary mission is to extract price information and timestamps in real-time, ensuring the system has up-to-date market signals to drive predictions and trading decisions.

---

## Two-Part Architecture
S.C.A.L.E. is split into two integrated components: a **frontend** (Browser Extension) and a **backend** (FastAPI Server). Together, they form a seamless pipeline for data capture and delivery.

### 1. Frontend: Brave Browser Extension
- **Platform**: Built for the Brave browser, chosen for its Chromium-based architecture, privacy focus, lightweight performance, and free availability.
- **Function**: Scrapes live data directly from the TradingView DOM (Document Object Model) every 5 seconds.
- **Key Features**:
  - **Data Extraction**: Captures the current price of the selected asset (e.g., NASDAQ:AAPL, SP:SPX, BINANCE:BTCUSDT) from the TradingView chart.
  - **Minimal UI**: On first use, prompts the user for the FastAPI server URL (e.g., `http://localhost:8000`). No additional UX elements—just a single input field and a "Connect" button.
  - **One-Way Communication**: Sends scraped data to the backend via POST requests without expecting responses, keeping it simple and efficient.
  - **Error Handling**: If the backend is unreachable or disconnected, it triggers:
    - A **loud buzzing alert** (e.g., an audio loop).
    - A **big red overlay** in the extension UI with a warning (e.g., "SERVER DOWN").
  - **DOM Change Detection**: If TradingView’s DOM structure changes (e.g., price class is missing), it raises a **red alert** with a loud sound to notify the user immediately.
- **Data Format**: Sends JSON payloads like:
  ```json
  {
    "ticker": "NASDAQ:AAPL",
    "price": 193.02,
    "timestamp": "2025-07-07T18:25:43Z",
    "source": "tradingview",
    "client_id": "scale-extension-v1"
  }
  ```
- **Timezone**: Default is UTC+0, but users can customize it via configuration.

### 2. Backend: FastAPI Server
- **Function**: Receives data from the extension, logs it, and makes it available for the broader SHADOW AI system.
- **Key Features**:
  - **Endpoints**:
    - **POST /data**: Accepts JSON data from the extension and logs it.
    - **GET /status**: Returns `{"status": "online"}` to confirm the server is operational (used by the extension to verify connectivity).
  - **Logging**: Stores all incoming data in a dual-format system:
    - **SQLite**: Daily `.db` files (e.g., `20250709.db`) with a `trades` table for structured querying.
    - **CSV**: Daily `.csv` files (e.g., `20250709.csv`) for human-readable backups.
    - **Folder Structure**:
      ```
      /logs
       ├── 202507/
       │   ├── csv/
       │   │   └── 20250709.csv
       │   └── sqlite/
       │       └── 20250709.db
       ├── 202508/
       │   ├── csv/
       │   │   └── 20250801.csv
       │   └── sqlite/
       │       └── 20250801.db
      ```
  - **Command-Line Interface (CUI)**: Provides a terminal-based status monitor (no GUI), showing server health and recent data logs.
  - **Data Integrity**: Captures all data, including gaps, based on timestamps from the chart. If SHADOW AI detects missing data, S.C.A.L.E. ensures it’s scraped and logged retroactively when possible.
  - **No Security Overhead**: No API keys or authentication—designed for personal use with one-way data flow.

---

## Operational Mechanics
1. **Startup**:
   - The user opens the Brave extension, enters the FastAPI server URL (e.g., `http://localhost:8000`), and connects.
   - If the server isn’t reachable, the extension refuses to proceed, displaying a red alert and buzzing loudly.

2. **Data Capture**:
   - Every 5 seconds, the extension scrapes the TradingView DOM for the current price of the selected asset.
   - It packages the price with a timestamp (default UTC+0) and the ticker (derived from the chart or URL).

3. **Data Transmission**:
   - The extension sends a POST request to the backend’s `/data` endpoint with the JSON payload.
   - If the request fails (e.g., server down), it triggers the loud red alert.

4. **Backend Processing**:
   - The FastAPI server receives the data, logs it to both SQLite and CSV files, and keeps it accessible for SHADOW AI’s other submodules (e.g., PHANTOM for predictions).
   - The server runs silently, with a CUI displaying logs and status updates.

5. **Error Scenarios**:
   - **DOM Failure**: If the price isn’t found (e.g., class changes), the extension flags it with a red alert and sound.
   - **Server Failure**: If the backend is offline, the extension notifies the user immediately.

---

## What S.C.A.L.E. Does Not Do
- **Multi-Asset Tracking**: Focuses on a single asset at a time—no multi-chart support.
- **Prediction**: It only captures data, leaving analysis to PHANTOM.
- **User Validation**: No ticker checks or security layers—it trusts the operator (you).
- **Compression**: Logs remain uncompressed for instant AI access.

---

## Summary
S.C.A.L.E. is a lean, mean, data-scraping machine built for one purpose: to extract live price data from TradingView with ruthless efficiency and reliability. It uses a Brave extension to scrape the DOM every 5 seconds, sends it to a FastAPI server for logging, and screams bloody murder if anything goes wrong. It’s a personal tool—no frills, no compromises—just the raw data feed SHADOW AI needs to make money and shut up.

This concludes the full definition of S.C.A.L.E.’s role and functionality within SHADOW AI.

--- 