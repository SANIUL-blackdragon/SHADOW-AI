# Gemini Guidelines for SHADOW AI Project

This document provides guidelines for Gemini to assist in the development of the SHADOW AI project.

## 1. Project Overview

- **Project Name:** SHADOW AI (Strategic Heuristic AI for Data-Driven Order Writing)
- **Objective:** Develop a high-performance AI trading system to predict market movements and execute trades. The immediate goal is to build an MVP for the Notamedia Hackathon 2025 as outlined in `docs/md/FOR-NOW.md`.
- **Core Idea:** The system uses historical and live financial data (price and news sentiment) to generate binary trade signals (long/short).
- **Key Characteristics:** Private, stealthy, stable, scalable, and optimized for consumer hardware (no GPU).

## 2. System Architecture

SHADOW AI has a modular architecture. You should be aware of the following submodules and their functions as detailed in the `docs/md/` directory:

- **S.C.A.L.E.:** Captures live price data from Binance API.
- **G.R.I.M.:** Manages historical market data.
- **S.P.E.C.T.R.E.:** Scrapes news data stealthily.
- **F.L.A.R.E.:** Analyzes news text and generates sentiment scores.
- **P.H.A.N.T.O.M.:** The core predictive model that generates trade signals.
- **V.E.I.L.:** Simulates trades for testing and training (paper trading).
- **E.C.H.O.:** Sends trade signals to external platforms (e.g., Discord).
- **B.L.A.D.E.:** Compiles the final model into an optimized binary format.
- **Think Mirror:** A module to simulate human cognitive responses to market events to enhance predictions.

## 3. Technical Stack

- **Language:** Python 3.x
- **Core Libraries:** TensorFlow (CPU version), pandas, NumPy, Scrapy, Selenium, HuggingFace Transformers, Discord.py, SQLite.
- **Deployment:** The final application is intended to run on a VPS (Ubuntu 24.04 LTS).

## 4. How to Assist

- **Adhere to Conventions:** Follow the detailed plans in the `docs/md/` folder. The user values detailed planning before implementation.
- **Code Style:** Write clean, efficient, and well-documented Python code. All code should be compatible with a CPU-only environment.
- **File Structure:** Respect the existing file structure. Place new files in the appropriate directories (`src`, `data`, `logs`, etc.).
- **Proactive Assistance:** Help me follow the 10-day MVP development plan from `docs/md/FOR-NOW.md`. Let's start with Day 1 tasks.
- **Focus:** Our current focus is to build the MVP for the hackathon.

## 5. Current Goal

Our immediate objective is to implement the MVP as described in `docs/md/FOR-NOW.md`. Let's work together to complete the 10-day development plan.

## 6. Important Rules

- **Do not modify `src/scale/scale.py` or `src/grim/grim.py` unless explicitly instructed to do so.** These modules have been built by the user.

## 7. MVP Development Plan

This plan outlines the steps to build the SHADOW AI MVP. After completing each step, I will update this section to mark the task as done.

**Day 1: Project Setup**
- [X] Initialize GitHub repository.
- [X] Set up project structure.
- [X] Create `shadow_ai.py` with CLI integration.

**Day 2: S.C.A.L.E. Module**
- [ ] Develop S.C.A.L.E. to extract BTC/USD live data from Binance API.

**Day 3: G.R.I.M. Module**
- [ ] Implement G.R.I.M. to load and structure historical data.

**Day 4-5: P.H.A.N.T.O.M. Module**
- [ ] Build and train P.H.A.N.T.O.M. using an LSTM or Transformer model.

**Day 6: F.L.A.R.E. Module**
- [ ] Integrate F.L.A.R.E. for basic news sentiment analysis.

**Day 7: E.C.H.O. Module**
- [ ] Configure E.C.H.O. for CLI and Discord webhook outputs.

**Day 8: V.E.I.L. Module**
- [ ] Implement V.E.I.L. for paper trading and performance logging.

**Day 9: Documentation & Demo**
- [ ] Record and edit the MVP video demo.
- [ ] Write `README.md`.

**Day 10: Finalization**
- [ ] Finalize repository and submit.
