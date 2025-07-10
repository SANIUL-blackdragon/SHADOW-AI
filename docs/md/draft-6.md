# P.H.A.N.T.O.M. Development Plan

## 1. Overview and Objectives
P.H.A.N.T.O.M. (Predictive Heuristic AI for Navigating Trades & Order Management) is the central decision-making module within SHADOW AI (Strategic Heuristic AI for Data-Driven Order Writing), an advanced trading system designed to predict market movements with high accuracy and profitability. It integrates live and historical price data with processed news signals to generate actionable trade signals: 1 (long), 0 (short), or 0.5 (exit-only). The system aims to forecast market moves hours to weeks in advance, targeting a weekly profit and loss (P&L) of +100% to +300%, with a minimum acceptable threshold of +30%.
Core Objectives

Prediction Horizon: Anticipate market movements from hours to weeks ahead.
Accuracy: Achieve ≥80% to 95% accuracy on signal predictions.
Profitability: Deliver +100% to +300% weekly P&L, with a minimum of +30%.
Risk Management: Ensure 0% cumulative drawdown by week’s end, minimizing negative P&L outcomes.
Signal Precision: Generate 2–6 high-confidence signals per day, avoiding noise.

## 2. Data Inputs and Sources
P.H.A.N.T.O.M. relies on two primary data streams: chart-based price data and news-derived signals, processed by other SHADOW submodules.
Price Data

Live Data (via S.C.A.L.E.):
Source: binance api charts, extracted via Selenium-based screen reading.
Resolution: 1-second timeframe.
Content: Open, high, low, close (OHLC), volume, timestamps.


Historical Data (via G.R.I.M.):
Sources: Alpha Vantage API, Yahoo Finance (yfinance).
Format: .csv and .db for redundancy and accessibility.
Scope: As far back as available for each asset, with 1-second resolution where possible.
Content: OHLC, volume, timestamps.



News Data

Raw News (via S.P.E.C.T.R.E.):
Format: /news_logs/YYYYMM/raw/YYYYMMDD.txt.
Content: Unprocessed articles, posts, and events scraped globally using TOR and proxies.


Analyzed News (via F.L.A.R.E. and S.E.A.R.):
Format: /news_logs/YYYYMM/nlp/YYYYMMDD.csv/.db/.txt.
Content: Multi-metric scores, including:
Sentiment, urgency, impact scope, momentum potential, market alignment, source credibility, narrative saturation, and more.
Confidence scores per metric.
Validity spans (decay times) learned from historical market reactions.
Multi-hop event chains (e.g., "factory fire" → "chip price hike" → "stock drop").
Supersession flags for updated or overridden news.





## 3. Data Preprocessing and Feature Engineering
Price Data Processing

Cleaning: Remove outliers, bad ticks, and duplicates.
Normalization: Scale prices and volumes to consistent ranges.
Time Alignment: Synchronize with news data timestamps for joint analysis.
Feature Extraction:
Returns: Log returns for stability.
Volatility: Rolling standard deviation over multiple windows.
Momentum: RSI, MACD, stochastic oscillator.
Trends: Moving averages (SMA, EMA) and crossovers.
Patterns: Candlestick formations (doji, hammer) via pattern recognition.
Volume: Spikes, anomalies, price-volume correlation.
Temporal Context: Time of day, day of week, event-related windows.



News Data Integration

P.H.A.N.T.O.M. receives a comprehensive signal packet from F.L.A.R.E., including:
Core metrics: Sentiment, urgency, impact scope, chain reaction scores.
Temporal metadata: Validity spans, decay confidence, semantic velocity (immediate, gradual, long-tail).
Contextual metadata: Historical similarity scores, supersession status, entity correlations.
Behavioral metrics: Fear index triggers, herding amplifiers, FOMO potential.



## 4. Model Architecture
P.H.A.N.T.O.M. employs a multi-modal architecture to fuse price and news data, leveraging pattern recognition and adaptive learning.
Input Vector Builder

Price Encoder:
Uses CNNs or LSTMs to capture temporal patterns in price and volume data.
Output: Compressed price state vector per time window.


News Encoder:
Weights metrics by decay confidence and time-distance.
Output: Aggregated news signal vector.


Chain Encoder (via S.E.A.R.):
Embeds multi-hop event chains into graph representations.
Output: Influence map of causal cascades.



Fusion Module

Combines price, news, and chain vectors into a unified state vector.
Utilizes MLP or Transformer blocks with attention mechanisms to highlight critical features.

Prediction Head

Outputs:
Binary signal: 1 (long), 0 (short), 0.5 (exit-only).
Confidence score.
Conditional stop-loss price (if beneficial to P&L).


Mechanism: Sigmoid for classification, calibrated via Platt scaling.

Pattern Recognition Engine

Similarity Search:
Uses Dynamic Time Warping (DTW) or k-Nearest Neighbors on embeddings to match current patterns with historical data.
Anchors matches with news context for relevance.


Behavioral Mimicry: Emulates trader crowd reactions encoded in historical price movements.

## 5. Training and Validation
Training Phases

Historical Backtesting:
Uses G.R.I.M.’s full historical dataset.
Simulates trades via V.E.I.L., logging P&L per signal pair.


Live Paper Trading:
Runs on real-time data for 2 weeks to 1 month.
Signals ignored until performance criteria are met.



Dual-Mode Training

Mode A (Signal-Only):
Relies solely on PHANTOM signals for entry/exit.
Aims to minimize negatives through predictive exits.


Mode B (Signal + Stop-Loss):
Includes dynamic stop-losses per signal.
Tests if stop-losses enhance P&L positivity.



Performance Metrics

P&L Calculation:
Measures % change between consecutive signals (e.g., 1 → 0, 0 → 1, signal → 0.5).
Example: Long from 07:29 to 09:30 yields +2%, short from 09:30 to 13:27 yields +4%.


Stop-Loss Evaluation:
Only adopted if it increases cumulative P&L positivity.
Logged as an exit if triggered, with PHANTOM aiming to predict exits before stop-loss hits.



Validation Criteria

Minimum Threshold:
Weekly P&L: ≥ +30%.
Accuracy: ≥ 80%.
Win Rate: ≥ 70%.
Win/Loss Ratio: ≥ 2.0x.


Ideal Target:
Weekly P&L: +100% to +300%.
Cumulative Drawdown: 0% by week’s end.


Failure Conditions:
P&L < +30%: Retrain.
Any negative day: Log failure, adjust via V.E.I.L.
Accuracy < 75%: Revert to paper mode.



## 6. Deployment and Operation

Optimization: Converted to .bin format via B.L.A.D.E. for efficient VPS execution (4-core, 16GB RAM, Ubuntu 24.04 LTS).
Signal Generation: Outputs signals with confidence and optional stop-loss levels to E.C.H.O. for Discord webhook delivery.
Monitoring: Tracks performance against weekly targets, with V.E.I.L. providing continuous feedback.

## 7. Advanced Features

Stop-Loss Management:
Dynamic calculation based on historical adverse movements.
Used only if it improves P&L; otherwise, PHANTOM relies on signal-based exits.


Pattern Recognition:
Detects trader-driven patterns (e.g., breakouts, reversals) in price and volume data.
Matches with historical outcomes, enhanced by news context.


Adaptive Learning:
Adjusts weights via V.E.I.L.’s feedback to minimize negatives and maximize positives.



## 8. Performance Goals

Weekly P&L: +100% to +300%, with a hard minimum of +30%.
Drawdown: 0% cumulative by week’s end; intra-week dips < 2% tolerated.
Accuracy: ≥ 80%.
Signal Efficiency: 2–6 high-impact signals/day.
Deployment Gate: Live trading activated only after consistent performance in paper trading over a rolling window.

## 9. Conclusion

P.H.A.N.T.O.M. is engineered to predict market movements with exceptional precision and profitability, leveraging SHADOW’s integrated data pipeline. By combining advanced pattern recognition with news-driven insights, it aims to outpace human traders, delivering consistent, high-yield results while adhering to strict risk controls.