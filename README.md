SHADOW AI MVP
An open-source, non-commercial AI-driven trading system for predicting BTC/USD movements using live price data and news sentiment, built for the Notamedia MVP Hackathon 2025.
Overview
SHADOW AI (Strategic Heuristic AI for Data-Driven Order Writing) is a prototype trading system that integrates live BTC/USD price data from TradingView and basic news sentiment analysis to generate predictive trade signals (LONG/SHORT). Developed for the Notamedia MVP Hackathon 2025, this project is licensed under the Creative Commons Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0), prohibiting commercial use without explicit permission from SANIUL-blackdragon.
MVP Scope
The Minimum Viable Product (MVP) includes:

S.C.A.L.E.: Extracts live BTC/USD prices from TradingView using Selenium.
G.R.I.M.: Manages historical price data in CSV or SQLite.
S.P.E.C.T.R.E. (Simplified): Fetches Bitcoin news via NewsAPI.
F.L.A.R.E.: Performs basic sentiment analysis using FinBERT or dictionary-based methods.
P.H.A.N.T.O.M.: Generates trade predictions using an LSTM model.
E.C.H.O.: Outputs predictions via CLI and Discord webhooks.
V.E.I.L.: Simulates paper trades and logs performance.

Installation

Clone the repository:git clone https://github.com/SANIUL-blackdragon/SHADOW-AI.git
cd SHADOW-AI


Set up a virtual environment:python -m venv shadow-ai-venv
.\shadow-ai-venv\Scripts\Activate.ps1  # Windows
# source shadow-ai-venv/bin/activate  # Unix/Linux


Install dependencies:pip install -r requirements.txt


Obtain a NewsAPI key from newsapi.org and configure it in src/spectre/spectre.py or a .env file.

Usage
(To be completed by July 19, 2025)Run the MVP: python src/main.py (main script to be added).
Project Structure
SHADOW-AI/
├───data
│   ├───flare
│   ├───grim
│   ├───news_logs
│   ├───scale
│   └───trades
├───docs
├───logs
└───src
    ├───echo
    ├───flare
    ├───grim
    ├───phantom
    ├───scale
    ├───spectre
    └───veil

License
Licensed under the Creative Commons Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0). See LICENSE for details. Commercial use requires explicit written permission from SANIUL-blackdragon, contactable via GitHub issues (https://github.com/SANIUL-blackdragon/SHADOW-AI/issues).
Contributing
Contributions are welcome for non-commercial purposes. Submit pull requests or open issues on GitHub, adhering to the hackathon timeline (July 10–22, 2025).
Contact
For inquiries or commercial use requests, open an issue on GitHub (https://github.com/SANIUL-blackdragon/SHADOW-AI/issues).