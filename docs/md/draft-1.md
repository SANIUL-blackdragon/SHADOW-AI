# SHADOW AI Development Plan

**Date and Time of Plan Creation**: Wednesday, July 09, 2025, 04:53 PM +06

## 1. Introduction to SHADOW AI

SHADOW AI (Strategic Heuristic AI for Data-Driven Order Writing) is a private, high-performance AI trading system designed to predict market movements and execute trades using historical and live financial data. It integrates price data and news sentiment analysis to forecast binary trade signals (1 = long, 0 = short), aiming for precision and profitability. Initially developed in Python and optimized into a binary (.bin) format for efficiency, SHADOW operates on consumer hardware without a GPU, emphasizing stealth, stability, and scalability for personal use.

### Key Features:
- **Data-Driven Predictions**: Learns from historical price patterns and news events to predict market movements.
- **Real-Time Execution**: Monitors live market data and executes trades based on AI-driven signals.
- **Stealth and Security**: Designed for private use with a focus on data privacy and operational security.
- **Optimized Efficiency**: Runs on modest hardware with no GPU, using a custom binary inference engine for speed.

---

## 2. System Architecture

SHADOW's architecture comprises several components working sequentially to process data, predict trades, and execute actions:

- **Data Input**: Captures live and historical price data and news articles.
- **Training Pipeline**: Employs machine learning models (e.g., LSTM or Transformers) to analyze data patterns.
- **Decision Engine**: Analyzes signals to determine buy, sell, or hold actions with confidence levels.
- **Execution Bot**: Sends trade signals via Discord webhooks for manual execution.
- **Submodules**: Eight specialized modules handle tasks from data capture to final execution.

### 2.1 Data Input
- **Live Data**: Extracted via a screen reader on binance api, focusing on price digits and timestamps in real-time.
- **Historical Data**: Sourced from APIs like Binance, Yahoo Finance, or Alpha Vantage, stored and managed locally.

### 2.2 Training Pipeline
- **Model Types**: LSTM, GRU, Transformer, or Temporal Convolution for time-series analysis.
- **Feedback Loop**: Incorporates trade outcomes into future training, enabling continuous learning.

### 2.3 Decision Engine
- Analyzes model signals to select buy, sell, or hold actions with confidence scores.
- Optimizes for ROI, risk management, and portfolio balancing.

### 2.4 Execution Bot
- Sends trade signals via Discord webhooks for manual execution.
- Includes safety features like limits and slippage controls.

---

## 3. Data Requirements

SHADOW processes two main data categories:

### 3.1 Price Data
- **Historical Prices**: Sourced from Binance, Yahoo Finance, or Alpha Vantage, dating back as far as available.
- **Live Prices**: Captured via a screen reader on binance api, focusing on BTC/USD due to its market influence.
- **Format**: OHLCV (Open, High, Low, Close, Volume) with UNIX timestamps.

### 3.2 News Data
- **Raw News**: Scraped globally using stealth techniques (TOR, proxies, rotating IPs).
- **Sentiment Scores**: Derived from news text using FinBERT or a custom dictionary, scaled from -1 (bearish) to +1 (bullish).
- **Timestamps**: Aligned with price data to correlate events with market movements.

The system learns market behavior patterns with and without news influences, analyzing trader reactions to various events.

---

## 4. Submodule Details (Functional Order)

SHADOW's submodules are listed in their operational sequence, detailing their missions and tasks:

### 4.1 S.C.A.L.E. (Signal Capture & Live Extraction)
- **Mission**: Reads binance api live charts in real-time.
- **Task**: Extracts price digits and timestamps, feeding clean data to GRIM and PHANTOM for processing.

### 4.2 S.P.E.C.T.R.E. (Stealthy Proxy & Extraction Covert Tactical Retrieval Engine)
- **Mission**: Scrapes news globally, bypassing restrictions.
- **Task**: Uses TOR, proxies, and rotating IPs to collect raw news articles, passing them to FLARE for analysis.

### 4.3 G.R.I.M. (Grounded Repository for Indexed Market-data)
- **Mission**: Manages all historical price data.
- **Task**: Stores, cleans, and prepares datasets from historical sources and live SCALE feeds for PHANTOM's training and backtesting.

### 4.4 F.L.A.R.E. (Filtered Linguistic Analysis & Reaction Engine)
- **Mission**: Turns news text into numerical sentiment scores.
- **Task**: Processes raw news from SPECTRE, generates sentiment scores aligned with timestamps, and feeds them to PHANTOM.

### 4.5 P.H.A.N.T.O.M. (Predictive Heuristic AI for Navigating Trades & Order Management)
- **Mission**: Predicts market moves as the core model.
- **Task**: Combines price data from GRIM and news sentiment from FLARE to output binary predictions (1 = long, 0 = short) with confidence scores, sending them to VEIL or ECHO.

### 4.6 V.E.I.L. (Virtual Execution & Intelligent Learning)
- **Mission**: Simulates trades for testing and training.
- **Task**: Runs paper trades based on PHANTOM's predictions, logs performance (% gain/loss), and refines PHANTOM to maximize gains.

### 4.7 E.C.H.O. (Event Communication & Heuristic Output)
- **Mission**: Sends trade signals to external platforms.
- **Task**: Pushes predictions, confidence scores, and timestamps from PHANTOM to Discord via webhooks, formatted as:
  - Prediction: 0 / 1
  - Confidence: XX.XX
  - Timestamp: YYYYMMDDHHMMSS

### 4.8 B.L.A.D.E. (Binary Lightweight Autonomous Decision Engine)
- **Mission**: Deploys the final optimized system.
- **Task**: Compiles PHANTOM's trained model into a .bin binary format, enabling fast, efficient predictions on the target hardware without Python dependencies.

---

## 5. Hardware and Software Specifications

### 5.1 Development PC
- **RAM**: 16 GB
- **CPU**: 3 GHz max turbo
- **Storage**: 100-200 GB NVMe
- **GPU**: None

### 5.2 Deployment VPS
- **CPU**: 4-core
- **RAM**: 16 GB
- **OS**: Ubuntu 24.04 LTS

### 5.3 Software Stack
- **Language**: Python 3.x
- **ML Framework**: TensorFlow (CPU version)
- **Data Handling**: pandas, NumPy
- **Web Scraping**: Scrapy, Selenium
- **NLP**: FinBERT or custom sentiment dictionary
- **Communication**: Discord.py
- **Optimization**: ONNX
- **Monitoring**: Prometheus, Grafana

---

## 6. Deployment and Execution

- **Modes of Operation**:
  - **Paper Mode**: Simulates trades, logs results, and refines the model without real money. Ignores Discord webhooks for execution.
  - **Live Mode**: Sends actionable trade signals via Discord webhooks for manual execution once performance criteria are met.
- **Transition to Live Mode**: Occurs when the system achieves a consistent net positive gain of at least +100% in paper trades over a week.

### Execution Flow:
1. SCALE captures live price data.
2. SPECTRE scrapes news data concurrently.
3. GRIM stores and prepares price data.
4. FLARE processes news into sentiment scores.
5. PHANTOM predicts trade signals.
6. VEIL simulates trades in paper mode, logging outcomes.
7. ECHO sends signals to Discord (ignored in paper mode, acted upon in live mode).
8. BLADE optimizes the system into a .bin file for final deployment.

---

## 7. Logging and Monitoring

- **Log Structure**: Daily SQLite (.db) and CSV (.csv) files, organized by month (YYYYMM) and day (YYYYMMDD).
  - **Directory Layout**:
    ```
    /logs
     ├── YYYYMM/
     │   ├── csv/
     │   │   └── YYYYMMDD.csv
     │   └── sqlite/
     │       └── YYYYMMDD.db
    ```
- **Log Entries**:
  - Timestamp (YYYYMMDDHHMMSS)
  - Prediction (0 or 1)
  - Confidence score (out of 100)
  - Price at prediction
  - Price at next prediction
  - Percentage change (% gain/loss)
  - Outcome (WIN or LOSS)

- **Monitoring**: Prometheus and Grafana track system performance and prediction accuracy.

---

## 8. Optimization and Future Enhancements

- **Optimization**: Transition from Python to a .bin binary format using ONNX for enhanced performance on the target hardware.
- **Future Enhancements**:
  - Implement continuous learning mechanisms to adapt to new market patterns.
  - Add anti-detection features for news scraping (e.g., randomized delays, human-like behavior simulation).

---

This development plan provides a comprehensive roadmap for building SHADOW AI, ensuring all specified details are preserved and organized for clarity and actionability. It is designed to guide development within a constrained timeframe, such as a 10-day hackathon, while maintaining scalability for future enhancements.