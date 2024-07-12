LSTM Model Training and Forecasting Pipeline
This pipeline is designed to fetch data from a PostgreSQL database, preprocess it, and train an LSTM model with an attention mechanism for forecasting. The pipeline includes a web server built with Flask and Flask-SocketIO to provide real-time updates and visualizations.

Overview
Data Retrieval: Fetches data from a PostgreSQL database.
Data Preprocessing: Preprocesses the data for model training.
Model Training: Trains an LSTM model with an attention mechanism.
Forecasting: Uses the trained model to make future predictions.
Web Interface: Provides a web interface to visualize logs and predictions.
Setup Instructions
Prerequisites
Python 3.7+
PostgreSQL
Docker (for Redis, if applicable)
Environment Setup
Clone the Repository:

bash
Copy code
git clone <repository-url>
cd <repository-directory>
Install Dependencies:

bash
Copy code
pip install -r requirements.txt
Database Connection Configuration:
Update the database connection details in the script:

python
Copy code
db_params = {
}
Ensure the Static Directory Exists:

bash
Copy code
mkdir -p static
Running the Application
Start the Flask Application:

bash
Copy code
python app.py
Access the Web Interface:
Open your web browser and navigate to http://localhost:5300.

Pipeline Components
1. Data Retrieval
Fetches required columns from the PostgreSQL database for the specified rune name.

python
Copy code
def get_data():
    query = f"SELECT {', '.join(columns_to_fetch)}, timestamp FROM runes_token_info_genii WHERE rune_name = 'BILLION•DOLLAR•CAT'"
    df = pd.read_sql_query(query, engine)
    return df
2. Data Preprocessing
Preprocesses the retrieved data, including timestamp conversion, handling missing values, and setting the index.

python
Copy code
def preprocess_data(df):
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
    df.set_index('timestamp', inplace=True)
    df.fillna(df.mean(), inplace=True)
    return df
3. Model Definition
Defines an LSTM model with an attention mechanism.

python
Copy code
def create_lstm_attention_model(input_shape, output_steps):
    inputs = Input(shape=input_shape)
    x = LSTM(64, return_sequences=True)(inputs)
    x = Dropout(0.2)(x)
    x = LSTM(64, return_sequences=True)(x)
    x = Dropout(0.2)(x)
    x = LSTM(32, return_sequences=True)(x)
    x = Attention()([x, x])
    x = TimeDistributed(Dense(64))(x)
    x = Dense(output_steps)(x)
    
    model = keras.Model(inputs, x)
    model.compile(optimizer='adam', loss='mse')
    return model
4. Model Training
Trains the LSTM model using the preprocessed data.

python
Copy code
def train_model():
    df = get_data()
    df = preprocess_data(df)
    # ... [normalization and training code] ...
    model.save('model.h5')
5. Real-Time Predictions
Uses the trained model to make future predictions and emits them via WebSockets.

python
Copy code
socketio.emit('future_predictions', {'dates': future_dates, 'predictions': denorm_predicted_prices})
6. Web Interface
Provides a web interface to visualize logs and predictions.

python
Copy code
@app.route('/')
def index():
    return render_template('index.html', logs=parse_logs(log_content))
7. Log Parsing
Parses log files and displays the most recent entries.

python
Copy code
def parse_logs(logs):
    parsed_logs = {'INFO': [], 'WARNING': [], 'ERROR': []}
    log_pattern = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}):(\w+):(.*)')
    for log in logs:
        match = log_pattern.match(log)
        if match:
            timestamp, log_type, message = match.groups()
            parsed_logs[log_type].append({'timestamp': timestamp, 'message': message})
    return parsed_logs
Logging
Logging is set up to record important events and errors.

python
Copy code
logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s:%(levelname)s:%(message)s')
Scheduling
The application includes scheduling capabilities to periodically run tasks.

python
Copy code
schedule.run_pending()
time.sleep(1)
Conclusion
This pipeline integrates various components to provide a comprehensive solution for data retrieval, preprocessing, model training, forecasting, and real-time updates via a web interface. The use of Flask and Flask-SocketIO ensures a responsive and interactive experience for users.
