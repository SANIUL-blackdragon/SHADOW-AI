SHADOW AI MVP Development Plan for Notamedia Hackathon 2025
1. Introduction
This document outlines the strategic plan to develop a Minimum Viable Product (MVP) of the SHADOW AI system, an AI-driven trading tool, for the Notamedia MVP Hackathon 2025. The hackathon, themed "By Innovation, We Build," challenges participants to create innovative solutions using Generative AI (GenAI) to address real-world problems. The goal is to build a functional prototype of SHADOW AI within 10 days, meeting hackathon requirements and positioning it as a competitive entry for the grand prize.
Purpose

MVP Focus: Demonstrate SHADOW AI’s core ability to predict market movements using live price data, historical datasets, and basic news sentiment analysis.
Hackathon Alignment: Comply with submission requirements, including a video demo and GitHub repository.
Short-Term Goals: Establish a clear, actionable timeline to complete the MVP by July 22, 2025.

2. Hackathon Context
Event Details

Event: The Notamedia MVP Hackathon 2025
Deadline: July 22, 2025, at 11:45 PM IST
Format: Online, open to public participation
Eligibility: Participants must be above the legal age of majority in their country of residence, with standard exceptions excluded.
Total Prizes: $3,726 in cash, plus various non-cash incentives.

Participation Requirements

MVP Construction: Must be developed during the hackathon period.
Deliverables: 
A functional MVP solving a real-world problem with GenAI.
A video demonstration of the MVP.
A GitHub repository containing all code and documentation.


Examples of Acceptable MVPs: Productivity AI assistants, AI-enhanced tools, browser plugins, content summarization tools, or creative aids.

3. SHADOW AI Project Overview
SHADOW AI (Strategic Heuristic AI for Data-Driven Order Writing) is an advanced trading system designed to generate predictive trade signals by integrating price data and news sentiment. For the hackathon, the MVP will focus on a subset of its full capabilities to ensure feasibility within the 10-day timeline.
Submodules Included in MVP

S.C.A.L.E. (Signal Capture & Live Extraction): Captures live price data (e.g., BTC/USD) from binance api.
G.R.I.M. (Grounded Repository for Indexed Market-data): Stores and manages historical price data.
F.L.A.R.E. (Filtered Linguistic Analysis & Reaction Engine): Analyzes news text to produce sentiment scores. But use a lite model of S.P.E.C.T.R.E. for F.L.A.R.E. to work.
P.H.A.N.T.O.M. (Predictive Heuristic AI for Navigating Trades & Order Management): Core predictive model generating trade signals.
E.C.H.O. (Event Communication & Heuristic Output): Delivers predictions via command-line interface (CLI) and Discord webhooks.
V.E.I.L. (Virtual Execution & Intelligent Learning): Simulates trades in paper mode and logs performance.

Submodules Excluded from MVP

S.P.E.C.T.R.E.: Complex news scraping with TOR/proxy rotation is deferred; a simplified approach or placeholder will be used. But use a lite model of S.P.E.C.T.R.E. for F.L.A.R.E. to work.
B.L.A.D.E.: Binary compilation is unnecessary for the MVP; a Python-based prototype suffices.

4. MVP Scope and Deliverables
Functional Scope
The MVP will showcase SHADOW AI’s ability to:

Extract live BTC/USD price data from binance api.
Store and process historical price data.
Perform basic sentiment analysis on news text.
Generate trade predictions using a machine learning model.
Simulate trades and log performance metrics.
Output results via CLI and Discord.

Deliverables

Price Scraper: Python-based tool using Selenium or OCR to fetch live prices.
Data Storage: Historical data managed in CSV or SQLite via pandas.
Sentiment Pipeline: Basic analysis using FinBERT or a dictionary-based method.
Predictive Model: LSTM or Transformer model trained on available data.
Trade Simulator: Logs mock trades and calculates gains/losses.
Output Handler: CLI display and Discord webhook integration.
GitHub Repository: Contains all code, setup instructions, and a README.md.
Video Demo: Highlights the MVP’s workflow from data input to trade signal output.

Output Format Example
Prediction: 1 (LONG)
Confidence: 84.27
Timestamp: 20250708155013
Logged to: CLI, Discord, CSV

5. 10-Day Development Timeline



Day
Task



1
Initialize GitHub repository, set up project structure, and create CLI.


2
Develop S.C.A.L.E. to extract BTC/USD live data from binance api.


3
Implement G.R.I.M. to load and structure historical data.


4-5
Build and train P.H.A.N.T.O.M. using an LSTM or Transformer model.


6
Integrate F.L.A.R.E. for basic news sentiment analysis.


7
Configure E.C.H.O. for CLI and Discord webhook outputs.


8
Implement V.E.I.L. for paper trading and performance logging.


9
Record and edit the MVP video demo showing the full workflow.


10
Finalize repository, write README.md, and submit to Devpost.


6. Technical Implementation
Technology Stack

Language: Python 3.x
Libraries: 
TensorFlow (CPU) for model development.
pandas and NumPy for data handling.
HuggingFace Transformers for sentiment analysis.
Selenium for price scraping.
Discord.py for webhook integration.


Storage: CSV files and SQLite database for price and trade logs.

Development Notes

Price Extraction: Use Selenium for reliability; fallback to OCR if needed.
Model Training: Focus on CPU-compatible TensorFlow to avoid hardware constraints.
Sentiment Analysis: Prioritize a pre-trained FinBERT model for efficiency.

7. Prizes and Motivation
Grand Prize

Cash: $3,736 USD (approximately 436,000 BDT).
Non-Cash Incentives:
.TECH domain (1 year free).
JetBrains subscription (renewable annually).
Heroku credits ($13/month for 24 months).
DataCamp premium (3 months).
GitHub Foundations Certification (1 free exam).
Codédex Club (6 months).
FrontendMasters (6 months).
GitKraken Pro and GitLens Pro licenses.
Termius Pro and Team features.
MongoDB credits ($50) and certification.
Skillshare and StackSkills Unlimited access.
DigitalOcean ($100 credit).
SendGrid (15,000 emails/month).
Additional tools: Travis CI, StyleCI, Adobe Creative Cloud (60% off), Datadog Pro, 1Password (6 months), etc.


Total Value: Exceeds $7,000 USD with cash and perks combined.

Runner-Up Prizes (20 Winners)

Cash: $173 USD.
Perks: Includes DigitalOcean ($100 credit), SendGrid (15,000 emails/month), and select software subscriptions.

Strategic Incentive
Winning the grand prize provides not only financial reward but also resources to scale SHADOW AI post-hackathon, potentially attracting venture capital interest.
8. Judging Criteria Alignment

Innovation: Novel integration of price data and news sentiment for trading predictions.
Technical Execution: Robust implementation of core submodules within 10 days.
UI/UX Design: Simple, effective CLI and Discord output for usability.
Real-World Impact: Demonstrates potential to improve trading decisions.

9. Conclusion
The Notamedia MVP Hackathon 2025 offers a platform to validate SHADOW AI’s concept while competing for significant rewards. By focusing on essential functionality and adhering to the 10-day plan, the MVP will highlight the system’s predictive power and scalability, positioning it as a standout entry. This document serves as the definitive guide for planning and execution, ensuring all critical aspects are addressed efficiently.