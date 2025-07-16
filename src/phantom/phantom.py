import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import load_model
from datetime import datetime
import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get project root directory (SHADOW-AI/)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# Configuration
DATA_PATH = os.path.join(PROJECT_ROOT, 'data', 'grim', 'historical_data.csv')  # Historical data from G.R.I.M.
NEWS_LOGS_PATH = os.path.join(PROJECT_ROOT, 'data', 'news_logs')  # News logs from F.L.A.R.E.
MODELS_PATH = os.path.join(PROJECT_ROOT, 'models')  # Directory for saving models
OUTPUT_PATH = os.path.join(PROJECT_ROOT, 'data', 'trades')  # Directory for predictions
LOOKBACK = 60  # Number of time steps to look back
API_URL = os.getenv("DEEPSEEK_API_URL")
API_KEY = os.getenv("DEEPSEEK_API_KEY")
MODEL_NAME = os.getenv("DEEPSEEK-R1_MODEL")

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
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout
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

def get_deepseek_opinion(data, local_prediction):
    """Get trade signal opinion from DeepSeek R1 via OpenRouter API."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You are a financial analyst. Provide a trade signal (1 for LONG, 0 for SHORT) based on the given data."},
            {"role": "user", "content": json.dumps({
                "live_price": float(data[-1, 0]),
                "historical_data": data[-LOOKBACK:].tolist(),
                "sentiment_scores": data[-LOOKBACK:, 2].tolist(),
                "local_prediction": int(local_prediction)
            })}
        ],
        "max_tokens": 10  # Expecting a simple response like "1" or "0"
    }
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        opinion = response.json()["choices"][0]["message"]["content"].strip()
        return int(opinion) if opinion in ["0", "1"] else None
    except Exception as e:
        print(f"Error getting DeepSeek opinion: {e}")
        return None

def predict(model, scaler, recent_data):
    """Generate trade prediction and get DeepSeek opinion."""
    scaled_data = scaler.transform(recent_data[-LOOKBACK:])
    X = np.array([scaled_data])
    local_prediction = model.predict(X)[0][0]
    local_signal = 1 if local_prediction > 0.5 else 0
    local_confidence = local_prediction if local_signal == 1 else 1 - local_prediction
    
    # Get DeepSeek opinion
    deepseek_opinion = get_deepseek_opinion(recent_data, local_signal)
    
    # Combine predictions (simple voting)
    final_signal = local_signal if deepseek_opinion is None else (1 if (local_signal + deepseek_opinion) >= 1 else 0)
    
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    
    output = {
        "Local_Prediction": local_signal,
        "Local_Confidence": float(local_confidence),
        "DeepSeek_Opinion": deepseek_opinion,
        "Final_Prediction": final_signal,
        "Timestamp": timestamp
    }
    
    # Save to CSV
    os.makedirs(OUTPUT_PATH, exist_ok=True)
    pd.DataFrame([output]).to_csv(os.path.join(OUTPUT_PATH, f'prediction_{timestamp}.csv'), index=False)
    return output

def main():
    """Main function to run the P.H.A.N.T.O.M. module."""
    # Load and prepare data
    data = load_data()
    X, y, scaler = prepare_sequences(data)
    
    # Train model (or load pre-trained)
    model_path = os.path.join(MODELS_PATH, 'phantom_model.h5')
    if not os.path.exists(model_path):
        model = train_model(X, y)
    else:
        model = load_model(model_path)
    
    # Predict using recent data
    recent_data = data[-LOOKBACK:]  # Assume recent data from S.C.A.L.E.
    prediction = predict(model, scaler, recent_data)
    
    # Output results
    print(f"Local Prediction: {prediction['Local_Prediction']} (LONG)" if prediction['Local_Prediction'] == 1 else 
          f"Local Prediction: {prediction['Local_Prediction']} (SHORT)")
    print(f"Local Confidence: {prediction['Local_Confidence']:.4f}")
    print(f"DeepSeek Opinion: {prediction['DeepSeek_Opinion']}")
    print(f"Final Prediction: {prediction['Final_Prediction']} (LONG)" if prediction['Final_Prediction'] == 1 else 
          f"Final Prediction: {prediction['Final_Prediction']} (SHORT)")
    print(f"Timestamp: {prediction['Timestamp']}")

if __name__ == "__main__":
    main()