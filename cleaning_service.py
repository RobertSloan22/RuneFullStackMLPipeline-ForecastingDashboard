import re
import pandas as pd
import numpy as np
from tensorflow.keras.models import load_model
from sklearn.preprocessing import MinMaxScaler
import logging
from sqlalchemy import create_engine

# Set up logging
logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s:%(levelname)s:%(message)s",
)

def preprocess_data(df):
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df.sort_values("timestamp", inplace=True)  # Sort in ascending order
    df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df.set_index("timestamp", inplace=True)

    df = df.rename(columns={"price_usd": "Close"})
    df["Open"] = df["Close"]
    df["High"] = df["Close"]
    df["Low"] = df["Close"]
    df["Adj Close"] = df["Close"]
    df["Volume"] = 1

    df.ffill(inplace=True)
    return df[["Open", "High", "Low", "Close", "Adj Close", "Volume"]]

def create_sequences(data, sequence_length=30):
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(data["Close"].values.reshape(-1, 1))

    X = []
    for i in range(sequence_length, len(scaled_data)):
        X.append(scaled_data[i - sequence_length : i, 0])

    X = np.array(X)
    X = np.reshape(X, (X.shape[0], X.shape[1], 1))
    return X, scaler

def load_model_and_predict(rune_name):
    df = get_data(rune_name)
    if df is None:
        return None, None

    data = preprocess_data(df)
    X, scaler = create_sequences(data)

    model = load_model("modelsats5.h5")
    predictions = model.predict(X)
    predictions = predictions.reshape(predictions.shape[0], -1)

    predictions = scaler.inverse_transform(predictions)

    return predictions, df.index[-len(predictions) :]
