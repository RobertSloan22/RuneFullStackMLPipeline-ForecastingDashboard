const express = require('express');
const { MongoClient } = require('mongodb');
const Redis = require('ioredis');
const winston = require('winston');
const moment = require('moment');
require('dotenv').config();  // Load environment variables from a .env file

// Configure winston logger
const logger = winston.createLogger({
    level: 'info',
    format: winston.format.combine(
        winston.format.colorize(),
        winston.format.simple()
    ),
    transports: [
        new winston.transports.Console(),
        new winston.transports.File({ filename: 'server.log' })
    ]
});

const app = express();

// Initialize Redis client
const redis = new Redis({
    host: process.env.REDIS_HOST || '127.0.0.1',
    port: process.env.REDIS_PORT || 6379
});

redis.on('error', (err) => {
    logger.error('Redis error: ', err);
});

// MongoDB URI
const uri = process.env.MONGODB_URI;

// Connect to MongoDB
const client = new MongoClient(uri, { useNewUrlParser: true, useUnifiedTopology: true });

let db_forecasts;
let db_runes;

async function connectToMongoDB() {
    try {
        await client.connect();
        logger.info('Connected to MongoDB');

        // Initialize databases and collections
        db_forecasts = client.db("runes_forecasts");
        db_runes = client.db("runes").collection("GinidataRunes");

        // Start the server after successful connection
        const PORT = process.env.PORT || 3000;
        app.listen(PORT, () => {
            logger.info(`Server running on port ${PORT}`);
        });
    } catch (err) {
        logger.error('Failed to connect to MongoDB', err);
        setTimeout(connectToMongoDB, 5000);  // Retry after 5 seconds
    }
}

connectToMongoDB();

// Preprocess data
function preprocessData(data) {
    data.forEach(item => {
        if (item.timestamp) {
            item.timestamp = moment(item.timestamp).isValid()
                ? moment(item.timestamp).format('YYYY-MM-DD HH:mm:ss')
                : null;
        }
    });
    data = data.filter(item => item.timestamp !== null);  // Remove invalid dates
    return data;
}

app.get('/forecast', async (req, res) => {
    logger.info('Fetching forecast data');
    try {
        const cachedData = await redis.get('forecast_data');
        if (cachedData) {
            logger.info('Forecast data retrieved from Redis cache');
            return res.json(JSON.parse(cachedData));
        }

        const forecast_collection = db_forecasts.collection("forecast");
        const forecastData = await forecast_collection.find().sort({ "dates": -1 }).limit(1).toArray();
        if (forecastData.length === 0) {
            return res.status(404).json({ error: 'No forecast data found' });
        }
        const predictions = forecastData[0].predictions.map(pred => pred[0]);
        const dates = forecastData[0].dates;

        const data = { dates, predictions };
        await redis.set('forecast_data', JSON.stringify(data), 'EX', 3600); // Cache for 1 hour
        logger.info('Forecast data fetched from MongoDB and cached in Redis');
        res.json(data);
    } catch (err) {
        logger.error('Error fetching forecast data: ', err);
        res.status(500).json({ error: 'Internal Server Error' });
    }
});

app.get('/rune-names', async (req, res) => {
    logger.info('Fetching unique rune names');
    try {
        const cachedData = await redis.get('rune_names');
        if (cachedData) {
            logger.info('Rune names retrieved from Redis cache');
            return res.json(JSON.parse(cachedData));
        }

        const runeNames = await db_runes.distinct('rune_name');
        await redis.set('rune_names', JSON.stringify(runeNames), 'EX', 3600); // Cache for 1 hour
        logger.info('Rune names fetched from MongoDB and cached in Redis');
        res.json(runeNames);
    } catch (err) {
        logger.error('Error fetching rune names: ', err);
        res.status(500).json({ error: 'Internal Server Error' });
    }
});

app.get('/rune-data', async (req, res) => {
    const runeName = req.query.rune_name;
    logger.info(`Fetching data for rune: ${runeName}`);
    try {
        const cachedData = await redis.get(`rune_data_${runeName}`);
        if (cachedData) {
            logger.info(`Data for rune ${runeName} retrieved from Redis cache`);
            return res.json(JSON.parse(cachedData));
        }

        const filter = { 'rune_name': runeName };
        const project = { 'rune_name': 1, 'timestamp': 1, 'price_sats': 1, 'volume_1d_btc': 1, '_id': 0 };
        const cursor = db_runes.find(filter).project(project);
        let data = await cursor.toArray();

        if (data.length === 0) {
            return res.status(404).json({ error: `No data found for rune ${runeName}` });
        }

        data = preprocessData(data);

        await redis.set(`rune_data_${runeName}`, JSON.stringify(data), 'EX', 3600); // Cache for 1 hour
        logger.info(`Data for rune ${runeName} fetched from MongoDB and cached in Redis`);
        res.json(data);
    } catch (err) {
        logger.error(`Error fetching data for rune ${runeName}: `, err);
        res.status(500).json({ error: 'Internal Server Error' });
    }
});

process.on('SIGINT', () => {
    client.close();
    redis.disconnect();
    logger.info('Server shutdown gracefully');
    process.exit(0);
});
