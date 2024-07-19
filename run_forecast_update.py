import time
from pymongo import MongoClient
import pandas as pd
from prophet import Prophet
import matplotlib.pyplot as plt
import io
import base64

# Establish a connection to the MongoDB server
client = MongoClient('')
database = client['runes']
collection = database['GinidataRunes']

def fetch_data(rune_name):
    # Fetch data for the specified rune name
    query = {"rune_name": rune_name}
    data = collection.find(query, {"timestamp": 1, "price_sats": 1})
    df = pd.DataFrame(list(data))
    df['ds'] = pd.to_datetime(df['timestamp'])
    df['y'] = df['price_sats'].astype(float)
    return df[['ds', 'y']]

def update_forecast_plot(rune_name):
    df = fetch_data(rune_name)

    if df.empty:
        return None

    # Initialize and fit the Prophet model
    model = Prophet()
    model.fit(df)

    # Create a DataFrame for future predictions
    future = model.make_future_dataframe(periods=365)

    # Generate predictions
    forecast = model.predict(future)

    # Plot the forecast
    fig, ax = plt.subplots()
    model.plot(forecast, ax=ax)
    plt.title(f"Real-time Price Forecast for {rune_name}")
    plt.xlabel("Date")
    plt.ylabel("Price (sats)")

    # Convert plot to PNG image
    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode('utf8')
    plt.close(fig)

    return plot_url

# Update forecast plot every 5 minutes
rune_name = 'BILLION•DOLLAR•CAT'
while True:
    update_forecast_plot(rune_name)
    time.sleep(300)
