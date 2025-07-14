import tensorflow as tf
import pandas as pd
import numpy as np
import os
import glob
from datetime import datetime, timedelta
import logging

# Configure logging
log_file = "phantom.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, mode='a', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class PHANTOM:
    def __init__(self, input_shape):
        self.model = self._build_model(input_shape)

    def _build_model(self, input_shape):
        """Builds the LSTM model."""
        model = tf.keras.Sequential([
            tf.keras.layers.LSTM(50, return_sequences=True, input_shape=input_shape),
            tf.keras.layers.LSTM(50),
            tf.keras.layers.Dense(1, activation='sigmoid')
        ])
        model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
        return model

    def train(self, data, labels, epochs=10, batch_size=32):
        """Trains the model."""
        logger.info(f"Training model with {len(data)} samples for {epochs} epochs.")
        self.model.fit(data, labels, epochs=epochs, batch_size=batch_size)
        logger.info("Model training complete.")

    def predict(self, data):
        """Makes a prediction."""
        logger.info(f"Making prediction for {len(data)} samples.")
        predictions = self.model.predict(data)
        logger.info("Prediction complete.")
        return predictions

def load_and_preprocess_data(data_dir, sequence_length=60):
    """
    Loads trade data from CSV files, aggregates to daily OHLCV,
    and creates sequences for LSTM training.
    """
    all_files = glob.glob(os.path.join(data_dir, "**", "chart", "csv", "*.csv"))
    if not all_files:
        logger.error(f"No CSV files found in {data_dir}")
        return None, None

    list_df = []
    for file in all_files:
        try:
            df = pd.read_csv(file)
            list_df.append(df)
        except Exception as e:
            logger.warning(f"Error reading {file}: {e}")
            continue

    if not list_df:
        logger.error("No data loaded from CSV files.")
        return None, None

    full_df = pd.concat(list_df, ignore_index=True)
    full_df['timestamp'] = pd.to_datetime(full_df['timestamp'])
    full_df = full_df.sort_values('timestamp')
    full_df = full_df.drop_duplicates(subset=['tradeId']) # Ensure unique trades

    # Aggregate to daily OHLCV
    ohlcv_df = full_df.set_index('timestamp')['price'].resample('D').ohlc()
    ohlcv_df['volume'] = full_df.set_index('timestamp')['quantity'].resample('D').sum()
    ohlcv_df = ohlcv_df.dropna()

    if ohlcv_df.empty:
        logger.error("OHLCV data is empty after aggregation.")
        return None, None

    # Create sequences and labels
    X, y = [], []
    for i in range(len(ohlcv_df) - sequence_length):
        X.append(ohlcv_df.iloc[i:i+sequence_length][['open', 'high', 'low', 'close', 'volume']].values)
        # Predict next day's closing price movement (1 for up, 0 for down)
        y.append(1 if ohlcv_df['close'].iloc[i+sequence_length] > ohlcv_df['close'].iloc[i+sequence_length-1] else 0)

    if not X:
        logger.error("Not enough data to create sequences. Ensure sequence_length is less than total data points.")
        return None, None

    X = np.array(X)
    y = np.array(y)

    logger.info(f"Loaded and preprocessed data. X shape: {X.shape}, y shape: {y.shape}")
    return X, y

def main():
    """Main function to run the P.H.A.N.T.O.M. module."""
    DATA_DIR = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")), "data", "grim")
    SEQUENCE_LENGTH = 60 # Number of past days to consider for prediction

    logger.info("Starting P.H.A.N.T.O.M. module.")

    X, y = load_and_preprocess_data(DATA_DIR, SEQUENCE_LENGTH)

    if X is None or y is None:
        logger.error("Failed to load and preprocess data. Exiting.")
        return

    # Determine input shape for the model
    input_shape = (X.shape[1], X.shape[2]) # (sequence_length, num_features)

    phantom = PHANTOM(input_shape)

    # Train the model
    phantom.train(X, y)

    # Example prediction (using the last sequence from the data)
    if X.shape[0] > 0:
        sample_for_prediction = X[-1].reshape(1, X.shape[1], X.shape[2])
        prediction = phantom.predict(sample_for_prediction)
        logger.info(f"Prediction for next day's price movement: {prediction[0][0]:.4f} (closer to 1 means UP, closer to 0 means DOWN)")
    else:
        logger.warning("No data available for example prediction.")

    logger.info("P.H.A.N.T.O.M. module finished.")

if __name__ == "__main__":
    main()

