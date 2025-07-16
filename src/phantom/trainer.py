import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get project root directory (SHADOW-AI/)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# Configuration
DATA_PATH = os.path.join(PROJECT_ROOT, 'data', 'grim', 'historical_data.csv')  # Historical data from G.R.I.M.
NEWS_LOGS_PATH = os.path.join(PROJECT_ROOT, 'data', 'news_logs')  # News logs from F.L.A.R.E.
MODELS_PATH = os.path.join(PROJECT_ROOT, 'models')  # Directory for saving models
LOOKBACK = 60  # Number of time steps to look back

def get_current_date_str():
    """Get current date string in YYYYMMDD format."""
    return datetime.utcnow().strftime("%Y%m%d")

def get_news_log_path(date_str):
    """Get path to news log CSV for a given date."""
    year = date_str[:4]
    month = date_str[4:6]
    day = date_str[6:]
    return os.path.join(NEWS_LOGS_PATH, year, month, day, 'CSV', f'{date_str}.csv')

def load_data():
    """Load and combine price and sentiment data."""
    # Load historical price data from G.R.I.M.
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Historical data not found at {DATA_PATH}")
    price_data = pd.read_csv(DATA_PATH)
    price_data = price_data[['timestamp', 'close', 'volume']].sort_values('timestamp')
    
    # Get current date's news log path
    current_date_str = get_current_date_str()
    sentiment_path = get_news_log_path(current_date_str)
    
    # Load sentiment data from F.L.A.R.E.
    if os.path.exists(sentiment_path):
        sentiment_data = pd.read_csv(sentiment_path)
        sentiment_data = sentiment_data[['TimeOfRelease', 'summary']].copy()
        sentiment_data['sentiment'] = sentiment_data['summary'].apply(lambda x: 0.5)  # Placeholder sentiment
    else:
        sentiment_data = pd.DataFrame(columns=['TimeOfRelease', 'sentiment'])
    
    # Merge on timestamp
    data = price_data.merge(sentiment_data[['TimeOfRelease', 'sentiment']], 
                           left_on='timestamp', right_on='TimeOfRelease', how='left')
    data['sentiment'] = data['sentiment'].fillna(0.5)  # Neutral sentiment for missing data
    return data[['close', 'volume', 'sentiment']].values

def prepare_sequences(data, lookback=LOOKBACK):
    """Create sequences for LSTM input."""
    scaler = MinMaxScaler()
    scaled_data = scaler.fit_transform(data)
    
    X, y = [], []
    for i in range(lookback, len(data)):
        X.append(scaled_data[i-lookback:i])
        y.append(1 if scaled_data[i, 0] > scaled_data[i-1, 0] else 0)  # 1 for price increase, 0 for decrease
    return np.array(X), np.array(y), scaler

def build_model():
    """Build and compile LSTM model."""
    model = Sequential([
        LSTM(50, return_sequences=True, input_shape=(LOOKBACK, 3)),  # 3 features: close, volume, sentiment
        Dropout(0.2),
        LSTM(50),
        Dropout(0.2),
        Dense(1, activation='sigmoid')  # Binary output
    ])
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    return model

def train_model(X, y):
    """Train the LSTM model."""
    model = build_model()
    model.fit(X, y, epochs=10, batch_size=32, validation_split=0.2, verbose=1)
    os.makedirs(MODELS_PATH, exist_ok=True)
    model.save(os.path.join(MODELS_PATH, 'phantom_model.h5'))
    return model

def main():
    """Main function to train the P.H.A.N.T.O.M. model."""
    # Load and prepare data
    data = load_data()
    X, y, scaler = prepare_sequences(data)
    
    # Train model
    model = train_model(X, y)
    print("Model training completed and saved to models/phantom_model.h5")

if __name__ == "__main__":
    main()