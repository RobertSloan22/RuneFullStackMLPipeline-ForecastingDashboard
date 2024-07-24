import logging
import threading
from threading import Thread
from flask import Flask, jsonify, request
import os
from pymongo import MongoClient
import pandas as pd
from tensorflow.keras.models import load_model
from tensorflow.keras.losses import MeanSquaredError
from sklearn.preprocessing import MinMaxScaler
import numpy as np

# Initialize Flask app
app = Flask(__name__)
results_lock = threading.Lock()

# Ensure the static directory exists
if not os.path.exists("static"):
    os.makedirs("static")

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Connect to MongoDB
client = MongoClient(
    ""
)
db = client["runes"]


class ForecastingService:
    def __init__(self):
        self.model = self.load_model()

    @staticmethod
    def get_data(rune_name):
        try:
            filter = {"rune_name": rune_name}
            project = {
                "rune_name": 1,
                "price_sats": 1,
                "timestamp": 1,
                "volume_1h_btc": 1,
            }
            result = client["runes"]["GinidataRunes"].find(
                filter=filter, projection=project
            )
            df = pd.DataFrame(list(result))
            logging.info(f"Data fetched successfully for rune: {rune_name}")
            return df
        except Exception as e:
            logging.error(f"Error retrieving data for rune {rune_name}: {e}")
            return None

    @staticmethod
    def preprocess_data(df):
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df.sort_values("timestamp", inplace=True)
        df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
        df.set_index("timestamp", inplace=True)
        df = df.rename(columns={"price_sats": "Close"})
        df["Open"] = df["Close"]
        df["High"] = df["Close"]
        df["Low"] = df["Close"]
        df["Adj Close"] = df["Close"]
        df["Volume"] = 1
        df.ffill(inplace=True)
        return df[["Open", "High", "Low", "Close", "Adj Close", "Volume"]]

    @staticmethod
    def create_sequences(data, sequence_length=30):
        scaler = MinMaxScaler(feature_range=(0, 1))
        scaled_data = scaler.fit_transform(data["Close"].values.reshape(-1, 1))
        X = []
        for i in range(sequence_length, len(scaled_data)):
            X.append(scaled_data[i - sequence_length : i, 0])
        X = np.array(X)
        X = np.reshape(X, (X.shape[0], X.shape[1], 1))
        return X, scaler

    @staticmethod
    def load_model():
        try:
            model = load_model(
                "modelsats5.h5", custom_objects={"mse": MeanSquaredError()}
            )
            logging.info("Model loaded successfully.")
            return model
        except Exception as e:
            logging.error(f"Error loading model: {e}")
            return None

    def load_model_and_predict(self, rune_name):
        logging.info(f"Starting to load model and predict for rune: {rune_name}.")
        df = self.get_data(rune_name)
        if df is None or df.empty:
            logging.error(f"No data fetched for rune: {rune_name}, returning None.")
            return None, None

        data = self.preprocess_data(df)
        X, scaler = self.create_sequences(data)

        try:
            predictions = self.model.predict(X)
            predictions = predictions.reshape(predictions.shape[0], -1)
            predictions = scaler.inverse_transform(predictions)
            logging.info(f"Predictions made successfully for rune: {rune_name}.")
        except Exception as e:
            logging.error(f"Error during prediction for rune {rune_name}: {e}")
            return None, None

        return predictions, df.index[-len(predictions) :]

    @staticmethod
    def save_forecast_to_mongo(rune_name, forecast_data):
        try:
            forecast_collection = db[rune_name]
            forecast_collection.insert_one(forecast_data)
            logging.info(
                f"Forecast data saved to MongoDB successfully for rune: {rune_name}"
            )
        except Exception as e:
            logging.error(
                f"Error saving forecast data to MongoDB for rune {rune_name}: {e}"
            )


@app.route("/forecast", methods=["POST"])
def forecast():
    rune_name = request.json.get("rune_name")
    if not rune_name:
        return jsonify({"error": "rune_name is required"}), 400

    service = ForecastingService()
    predictions, dates = service.load_model_and_predict(rune_name)
    if predictions is None:
        return jsonify({"error": "Error during forecasting"}), 500

    forecast_data = {
        "dates": list(dates),
        "predictions": predictions.tolist(),
    }
    service.save_forecast_to_mongo(rune_name, forecast_data)

    return jsonify({"message": "Forecasting completed successfully"}), 200


@app.route("/")
def home():
    return "Forecasting Service Running"


if __name__ == "__main__":
    logging.info("Starting Flask app")
    app.run(port=5600, debug=True)
