# G.R.I.M. Development Plan for SHADOW AI
Date and Time of Plan Creation: Wednesday, July 09, 2025, 05:17 PM +06
# 1. Introduction to G.R.I.M.
G.R.I.M., or Grounded Repository for Indexed Market-data, serves as a pivotal submodule within the SHADOW AI system (Strategic Heuristic AI for Data-Driven Order Writing). It functions as the centralized data logistics hub, managing access to historical market data processed by other submodules. Unlike modules that collect or refine raw data, G.R.I.M. focuses on indexing, unifying, and serving this data to ensure seamless integration with the system's predictive and simulation components, such as PHANTOM and VEIL. Its purpose is to act as the "memory bank" of SHADOW AI, providing clean, aligned, and queryable datasets without duplicating the data collection or cleaning efforts of other modules.
Key Objectives:

Centralized Data Indexing: Maintains a unified index of processed data files from various submodules.
Data Accessibility: Supplies time-aligned datasets to PHANTOM for predictions and VEIL for simulations.
Efficiency: Avoids redundant storage or processing by referencing existing files.
Consistency: Ensures all required data is available and properly formatted for downstream use.

This plan outlines G.R.I.M.'s responsibilities, operational mechanics, and integration strategy within the broader SHADOW AI architecture, which operates on a development PC (16 GB RAM, 3 GHz CPU, 100-200 GB NVMe, no GPU) and deploys on a VPS (4-core CPU, 16 GB RAM, Ubuntu 24.04 LTS).

# 2. Role and Responsibilities
G.R.I.M. does not collect, clean, or generate raw data—those tasks are handled by upstream modules like SCALE, SPECTRE, and FLARE. Instead, it acts as a data curator and access layer, ensuring that processed data is efficiently indexed, unified, and delivered to the AI and simulation modules.

## 2.1 Indexing Processed Data

G.R.I.M. maintains a central index of processed data files produced by other submodules:
SCALE: Daily CSV files with price data (e.g., 20250708.csv containing OHLCV—open, high, low, close, volume).
SPECTRE: Daily TXT files with raw news or event data (e.g., 20250708.txt).
FLARE: Daily DB or CSV files with timestamped sentiment scores (e.g., 20250708.db).


It tracks the locations of these files (e.g., /data/scale/, /data/spectre/, /data/flare/) without modifying their content.

## 2.2 Unifying Datasets

Combines data from multiple sources into a single, timestamp-aligned dataset:
Merges SCALE’s price data with FLARE’s sentiment scores based on matching timestamps.
Ensures compatibility for PHANTOM’s training and VEIL’s backtesting needs.


Example: Combines 20250708.csv (price) and 20250708.db (sentiment) into a unified time-series matrix.

## 2.3 Serving Time-Windowed Data Slices

Delivers specific time ranges of data upon request:
Example: "Provide price and sentiment data from May 1 to May 7, 2025."
Supports PHANTOM’s model training and VEIL’s historical trade simulations.


Filters and packages data into formats suitable for machine learning (e.g., pandas DataFrames or NumPy arrays).

## 2.4 Validating Data Consistency

Verifies that all necessary files for a requested date range are present and accessible:
Checks for missing files (e.g., if 20250708.csv exists but 20250708.db is absent).
Ensures data integrity before delivery to prevent incomplete datasets from affecting downstream processes.




# 3. Data Sources and Integration
G.R.I.M. relies entirely on pre-processed data from other submodules, integrating their outputs into a cohesive system without performing any initial data collection or refinement.
## 3.1 Input Data Sources

SCALE: Provides daily CSV files with cleaned price data:
Format: Columns like timestamp, open, high, low, close, volume.
Path: /data/scale/YYYYMMDD.csv.


SPECTRE: Supplies daily TXT files with raw news or event data:
Format: Timestamped text entries.
Path: /data/spectre/YYYYMMDD.txt.


FLARE: Outputs daily DB or CSV files with sentiment scores:
Format: Timestamped sentiment values derived from news data.
Path: /data/flare/YYYYMMDD.db.



## 3.2 Integration Process

G.R.I.M. reads these files directly from their designated directories.
It does not store copies or alter the original data, maintaining efficiency by referencing existing outputs.
Uses a meta-index to map dates to file locations for rapid retrieval.

## 3.3 Data Flow

Upstream: Receives finalized datasets from SCALE, SPECTRE, and FLARE after they complete their cleaning and storage tasks.
Downstream: Supplies unified datasets to PHANTOM for prediction and VEIL for simulation, ensuring seamless handoffs.


# 4. Operational Mechanics
G.R.I.M.’s operations focus on indexing, assembling, and serving data efficiently, leveraging the pre-processed outputs of other modules.
## 4.1 Indexing Mechanism

Maintains a meta-index file (e.g., JSON or SQLite database) mapping dates to file locations:
Example JSON structure:{
  "20250708": {
    "price": "data/scale/20250708.csv",
    "news": "data/spectre/202507    "sentiment": "data/flare/20250708.db"
  },
  "20250709": {
    "price": "data/scale/20250709.csv",
    "news": "data/spectre/20250709.txt",
    "sentiment": "data/flare/20250709.db"
  }
}




Updates automatically as new files are generated by upstream modules.

## 4.2 Data Assembly Process

Responds to requests by:
Locating relevant files using the meta-index.
Reading data from each file (e.g., CSV, TXT, DB).
Merging data based on timestamps into a unified dataset.
Delivering the result in a machine-learning-ready format.



## 4.3 Time-Windowed Delivery

Filters data to specific time periods:
Example: Extracts data for a week-long window centered on a significant news event.


Ensures only relevant data is provided, optimizing performance for PHANTOM and VEIL.

## 4.4 Validation Checks

Performs pre-delivery checks:
Confirms all files for the requested range exist.
Verifies basic format compatibility (e.g., expected columns in CSVs).


Raises alerts if inconsistencies are detected, preventing downstream errors.


# 5. Implementation Considerations
G.R.I.M. is designed to be lightweight and efficient, aligning with SHADOW AI’s hardware constraints (no GPU, limited RAM) and deployment goals.
## 5.1 Storage Efficiency

References existing files rather than duplicating them, minimizing disk usage.
Meta-index remains compact (e.g., JSON or SQLite) for fast lookups.

## 5.2 Meta-Index Implementation

Uses JSON for simplicity or SQLite for scalability:
JSON suits smaller datasets; SQLite supports complex queries for larger histories.


Stored in /grim/index/ and updated daily as new data arrives.

## 5.3 Data Integrity

Implements lightweight validation:
Checks file existence and basic structure.
Avoids deep cleaning (handled upstream) to reduce overhead.


Triggers alerts via Discord (via E.C.H.O.) if issues are found.

## 5.4 Performance Optimization

Optional caching for frequently accessed data:
Stores recent slices in memory to reduce disk I/O.


Balances RAM usage (16 GB limit) with query speed.


# 6. Directory Structure Integration
G.R.I.M. operates within SHADOW’s broader file system, interfacing with other modules’ outputs:
/shadow/
├── data/
│   ├── scale/
│   │   ├── 20250708.csv
│   │   ├── 20250709.csv
│   ├── spectre/
│   │   ├── 20250708.txt
│   │   ├── 20250709.txt
│   ├── flare/
│   │   ├── 20250708.db
│   │   ├── 20250709.db
├── grim/
│   ├── grim.py              # Core logic for indexing and serving
│   ├── index/
│   │   ├── meta_index.json # Maps dates to file paths
│   ├── utils.py            # Helper functions for data merging


Runtime Flow: grim.py reads from /data/ subdirectories, assembles datasets, and delivers them via function calls from phantom.py or veil.py.


# 7. Interaction with Other Modules
G.R.I.M. serves as the data bridge between collection/processing modules and analytical components:

Inputs:
SCALE: Price data CSVs, pre-cleaned and stored.
SPECTRE: News TXT files, optionally used for context.
FLARE: Sentiment DBs or CSVs, timestamp-aligned.


Outputs:
PHANTOM: Unified datasets for training and real-time predictions.
VEIL: Historical slices for mock trading and backtesting.


No Direct Interaction:
E.C.H.O. and B.L.A.D.E., which handle signal dispatch and deployment, respectively.




# 8. Future Enhancements
While G.R.I.M.’s core role is data logistics, optional features could enhance its utility:
## 8.1 Rolling Cache

Caches frequently accessed data in memory:
Reduces disk reads for real-time operations.
Configurable to fit within 16 GB RAM constraints.



## 8.2 Snapshot Exports

Exports data states for specific past dates:
Useful for auditing or recreating historical simulations.
Example: "Export data as known on 2025-03-01."



## 8.3 Extended Data Merging

Integrates additional data types (e.g., technical indicators) if provided by other modules.
Enhances dataset richness for PHANTOM’s predictions.

## 8.4 Consistency Automation

Periodic checks for timestamp alignment across sources.
Alerts developers to upstream issues (e.g., missing files).


# 9. Summary

G.R.I.M. is the unsung backbone of SHADOW AI’s data pipeline. It doesn’t collect or clean data but ensures that processed outputs from SCALE, SPECTRE, and FLARE are indexed, unified, and delivered efficiently to PHANTOM and VEIL. By acting as the system’s data logistics hub, G.R.I.M. enables accurate predictions and simulations without adding complexity or redundancy. This plan provides a clear, actionable framework for its development, ensuring it meets the needs of the SHADOW AI project while remaining lightweight and reliable.