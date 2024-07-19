import re
import pandas as pd
import numpy as np
from tensorflow.keras.models import load_model
from sklearn.preprocessing import MinMaxScaler
import matplotlib.pyplot as plt
from sqlalchemy import create_engine
import logging
from flask import Flask, jsonify, request
from flask_socketio import SocketIO
from threading import Thread
import os
from datetime import datetime, timedelta
import json
from pymongo import MongoClient

# Set up logging
logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s:%(levelname)s:%(message)s')

# Database connection details
db_params = {
    'dbname': 'sandbox',
    'user': 'postgres',
    'host': 'runes.csxbyr0egtki.us-east-1.rds.amazonaws.com',
    'password': 'uIPRefz6doiqQcbpM5po'
}

# MongoDB connection details
mongo_uri = "mongodb+srv://radevai1201:szZ2HmXFRc902EeW@cluster0.b8z5ks7.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
mongo_client = MongoClient(mongo_uri)

# Create the SQLAlchemy engine
engine = create_engine(f"postgresql+psycopg2://{db_params['user']}:{db_params['password']}@{db_params['host']}/{db_params['dbname']}")

app = Flask(__name__)
socketio = SocketIO(app)

# Ensure the static directory exists
if not os.path.exists('static'):
    os.makedirs('static')

# Columns to fetch from the database
columns_to_fetch = ['price_sats']

def get_data(rune_name):
    try:
        query = f"SELECT {', '.join(columns_to_fetch)}, timestamp FROM runes_token_info_genii WHERE rune_name = '{rune_name}' ORDER BY timestamp DESC LIMIT 100"
        df = pd.read_sql_query(query, engine)
        logging.info("Data fetched successfully")
        return df
    except Exception as e:
        logging.error(f"Error retrieving data: {e}")
        return None

def preprocess_data(df):
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df.sort_values('timestamp', inplace=True)  # Sort in ascending order
    df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
    df.set_index('timestamp', inplace=True)

    df = df.rename(columns={'price_sats': 'Close'})
    df['Open'] = df['Close']
    df['High'] = df['Close']
    df['Low'] = df['Close']
    df['Adj Close'] = df['Close']
    df['Volume'] = 1

    df.ffill(inplace=True)
    return df[['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']]

def create_sequences(data, sequence_length=30):
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(data['Close'].values.reshape(-1, 1))

    X = []
    for i in range(sequence_length, len(scaled_data)):
        X.append(scaled_data[i-sequence_length:i, 0])

    X = np.array(X)
    X = np.reshape(X, (X.shape[0], X.shape[1], 1))
    return X, scaler

def load_model_and_predict(rune_name):
    df = get_data(rune_name)
    if df is None:
        return None, None

    data = preprocess_data(df)
    X, scaler = create_sequences(data)

    model = load_model('modelsats5.h5')
    predictions = model.predict(X)
    predictions = predictions.reshape(predictions.shape[0], -1)

    predictions = scaler.inverse_transform(predictions)

    return predictions, df.index[-len(predictions):]

@app.route('/rune-names', methods=['GET'])
def get_rune_names():
    try:
        db = mongo_client["runes"]
        collection = db["GinidataRunes"]
        rune_names = collection.distinct("rune_name", {"holders": {"$gte": 1200}})
        return jsonify(rune_names)
    except Exception as e:
        logging.error(f"Error fetching rune names: {e}")
        return jsonify([]), 500

@app.route('/rune-data', methods=['GET'])
def get_rune_data():
    rune_name = request.args.get('rune_name')
    if not rune_name:
        return jsonify({"error": "Missing rune_name parameter"}), 400

    df = get_data(rune_name)
    if df is None:
        return jsonify([])

    data = preprocess_data(df)
    data.reset_index(inplace=True)
    return data.to_json(orient='records')

@app.route('/forecast', methods=['GET'])
def get_forecast():
    try:
        db = mongo_client["runes"]
        collection = db["forecast"]
        forecast_data = collection.find_one(sort=[('dates', -1)])
        if not forecast_data:
            return jsonify({"error": "No forecast data found"}), 404

        predictions = forecast_data['predictions']
        dates = forecast_data['dates']
        return jsonify({"dates": dates, "predictions": predictions})
    except Exception as e:
        logging.error(f"Error fetching forecast data: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

@app.route('/log-data', methods=['GET'])
def get_logs():
    try:
        with open('app.log', 'r') as f:
            log_content = f.readlines()
        return jsonify(parse_logs(log_content))
    except Exception as e:
        logging.error(f"Error fetching logs: {e}")
        return jsonify([]), 500

def parse_logs(logs):
    parsed_logs = {
        'INFO': [],
        'WARNING': [],
        'ERROR': []
    }
    log_pattern = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}):(\w+):(.*)')

    for log in logs:
        match = log_pattern.match(log)
        if match:
            timestamp, log_type, message = match.groups()
            parsed_logs[log_type].append({'timestamp': timestamp, 'message': message})

    for log_type in parsed_logs:
        parsed_logs[log_type] = parsed_logs[log_type][-10:]

    return parsed_logs

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=5600, debug=True)
