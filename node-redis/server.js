const express = require('express');
const { MongoClient } = require('mongodb');
const Redis = require('ioredis');
const winston = require('winston');
const moment = require('moment');  // Import moment for date formatting
const axios = require('axios');
const cors = require('cors');  // Import cors

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
app.use(cors());  // Enable CORS

// Initialize Redis client
const redis = new Redis({
    host: process.env.REDIS_HOST || '127.0.0.1',
    port: process.env.REDIS_PORT || 6379
});

redis.on('error', (err) => {
    logger.error('Redis error: ', err);
});

// MongoDB connection details
const uri = "";
const client = new MongoClient(uri, { useNewUrlParser: true, useUnifiedTopology: true, poolSize: 10 });

client.connect(async err => {
    if (err) {
        logger.error('Failed to connect to MongoDB', err);
    } else {
        logger.info('Connected to MongoDB');

        const db_forecasts = client.db("runes");
        const forecast_collection = db_forecasts.collection("forecast");

        const db_runes = client.db("runes");
        const runes_collection = db_runes.collection("GinidataRunes");

        const db_logs = client.db("runes");
        const logs_collection = db_logs.collection("logs");

        const db_rune_logs = client.db("runes");
        const rune_logs_collection = db_rune_logs.collection("RUNELOGS");

        // Preprocess data
        function preprocessData(data) {
            return data.map(item => {
                if (item.timestamp) {
                    item.timestamp = moment(item.timestamp).isValid()
                        ? moment(item.timestamp).format('YYYY-MM-DD HH:mm:ss')
                        : null;
                }
                return item;
            });
        }

        // Prefetch forecast data
        async function prefetchForecastData() {
            try {
                const filter = {};
                const sort = { 'dates': -1 };
                const limit = 1;
                const cursor = forecast_collection.find(filter).sort(sort).limit(limit);
                const forecastData = await cursor.toArray();
                if (forecastData.length === 0) {
                    logger.warn('No forecast data found during prefetch');
                    return;
                }

                const predictions = forecastData[0].predictions.map(pred => pred[0]); // Flattening predictions if necessary
                const dates = forecastData[0].dates;
                const data = { dates, predictions };

                await redis.set('forecast_data', JSON.stringify(data), 'EX', 3600); // Cache for 1 hour
                logger.info('Forecast data prefetched and cached in Redis');
            } catch (error) {
                logger.error('Error prefetching forecast data', error);
            }
        }

        // Prefetch rune names with the specified query
        async function prefetchRuneNames() {
            try {
                const filter = {};
                const projection = { 'rune_name': 1, 'price_sats': 1, 'volume_1d_btc': 1, 'holders': 1, '_id': 0 };
                const sort = { 'rune_name': 1 };
                const limit = 1000;
                const cursor = runes_collection.find(filter).project(projection).sort(sort).limit(limit);
                const runeNames = await cursor.toArray();

                await redis.set('rune_names', JSON.stringify(runeNames), 'EX', 3600); // Cache for 1 hour
                logger.info('Rune names prefetched and cached in Redis');
            } catch (error) {
                logger.error('Error prefetching rune names', error);
            }
        }

        // Prefetch log data
        async function prefetchLogData() {
            try {
                const filter = {};
                const sort = { '_id': -1 };
                const limit = 50;
                const cursor = logs_collection.find(filter).sort(sort).limit(limit);
                const logData = await cursor.toArray();

                await redis.set('log_data', JSON.stringify(logData), 'EX', 3600); // Cache for 1 hour
                logger.info('Log data prefetched and cached in Redis');
            } catch (error) {
                logger.error('Error prefetching log data', error);
            }
        }

        async function prefetchRuneLogData() {
            try {
                const filter = {};
                const sort = { '_id': -1 };
                const limit = 50;
                const cursor = rune_logs_collection.find(filter).sort(sort).limit(limit);
                const logData = await cursor.toArray();

                await redis.set('rune_logs', JSON.stringify(logData), 'EX', 3600); // Cache for 1 hour
                logger.info('Rune log data prefetched and cached in Redis');
            } catch (error) {
                logger.error('Error prefetching rune log data', error);
            }
        }

        // Write an async function to prefetch runeData 
        async function prefetchRuneData(runeName) {
            try {
                const filter = { 'rune_name': runeName };
                const project = { 'rune_name': 1, 'timestamp': 1, 'price_sats': 1, 'volume_1d_btc': 1 };
                const cursor = runes_collection.find(filter).project(project);
                let data = await cursor.toArray();

                if (data.length === 0) {
                    return;
                }

                data = preprocessData(data);

                await redis.set(`rune_data_${runeName}`, JSON.stringify(data), 'EX', 3600); // Cache for 1 hour
                logger.info(`Data for rune ${runeName} prefetched and cached in Redis`);
            } catch (error) {
                logger.error(`Error prefetching data for rune ${runeName}`, error);
            }
        }

        // Call prefetch functions on server start
        await prefetchForecastData();
        await prefetchRuneNames();
        await prefetchLogData();
        await prefetchRuneLogData();
        await prefetchRuneData("BILLION•DOLLAR•CAT");
        
        // Routes
        app.get('/', (req, res) => {
            res.send('Welcome to the Rune API');
        });

        app.get('/rune-logs', async (req, res) => {
            logger.info('Fetching rune logs');
            try {
                const cachedData = await redis.get('rune_logs');
                if (cachedData) {
                    logger.info('Rune logs retrieved from Redis cache');
                    return res.json(JSON.parse(cachedData));
                }

                const filter = {};
                const sort = { '_id': -1 };
                const limit = 50;
                const cursor = rune_logs_collection.find(filter).sort(sort).limit(limit);
                const logData = await cursor.toArray();

                await redis.set('rune_logs', JSON.stringify(logData), 'EX', 3600); // Cache for 1 hour
                logger.info('Rune logs fetched from MongoDB and cached in Redis');
                res.json(logData);
            } catch (error) {
                logger.error('Error fetching rune logs', error);
                res.status(500).json({ error: 'Internal Server Error' });
            }
        });
/// add new route for runelogdata
        app.get('/rune-log-data', async (req, res) => {
            const runeName = req.query.rune_name;
            logger.info(`Fetching data for rune: ${runeName}`);
            try {
                const cachedData = await redis.get(`rune_data_${runeName}`);
                if (cachedData) {
                    logger.info(`Data for rune ${runeName} retrieved from Redis cache`);
                    return res.json(JSON.parse(cachedData));
                }

                const filter = { 'rune_name': runeName };
                const project = { 'rune_name': 1, 'timestamp': 1, 'price_sats': 1, 'volume_1d_btc': 1 };
                const cursor = runes_collection.find(filter).project(project);
                let data = await cursor.toArray();

                if (data.length === 0) {
                    return res.status(404).json({ error: `No data found for rune ${runeName}` });
                }

                data = preprocessData(data);

                await redis.set(`rune_data_${runeName}`, JSON.stringify(data), 'EX', 3600); // Cache for 1 hour
                logger.info(`Data for rune ${runeName} fetched from MongoDB and cached in Redis`);
                res.json(data);
            } catch (error) {
                logger.error(`Error fetching data for rune ${runeName}`, error);
                res.status(500).json({ error: 'Internal Server Error' });
            }
        });

        app.get('/forecast', async (req, res) => {
            logger.info('Fetching forecast data');
            try {
                const filter = {};
                const sort = { 'dates': -1 };
                const limit = 1;
                const cursor = forecast_collection.find(filter).sort(sort).limit(limit);
                const forecastData = await cursor.toArray();
                if (forecastData.length === 0) {
                    return res.status(404).json({ error: 'No forecast data found' });
                }
        
                const predictions = forecastData[0].predictions.map(pred => pred[0]); // Flattening predictions if necessary
                const dates = forecastData[0].dates;
                const data = { dates, predictions };
        
                logger.info('Forecast data fetched from MongoDB');
                res.json(data);
            } catch (error) {
                logger.error('Error fetching forecast data', error);
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

                const filter = {
                    'holders': { '$gte': 1000 }  // for rune names with 1000 holders or more
                };
                const projection = {
                    'rune_name': 1,
                    'price_sats': 1,
                    'volume_1d_btc': 1,
                    'timestamp': 1,
                    '_id': 0
                };
                const sort = { 'rune_name': 1 };
                const limit = 1000;

                const cursor = runes_collection.find(filter).project(projection).sort(sort).limit(limit);
                const runeNames = await cursor.toArray();

                await redis.set('rune_names', JSON.stringify(runeNames), 'EX', 3600); // Cache for 1 hour
                logger.info('Rune names fetched from MongoDB and cached in Redis');
                res.json(runeNames);
            } catch (error) {
                logger.error('Error fetching rune names', error);
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
                    const parsedData = JSON.parse(cachedData);
                    await sendDataToAnotherAPI(parsedData);
                    return res.json(parsedData);
                }

                const filter = { 'rune_name': runeName };
                const project = { 'rune_name': 1, 'timestamp': 1, 'price_sats': 1, 'volume_1d_btc': 1 };
                const cursor = runes_collection.find(filter).project(project);
                let data = await cursor.toArray();

                if (data.length === 0) {
                    return res.status(404).json({ error: `No data found for rune ${runeName}` });
                }

                data = preprocessData(data);

                await redis.set(`rune_data_${runeName}`, JSON.stringify(data), 'EX', 3600); // Cache for 1 hour
                logger.info(`Data for rune ${runeName} fetched from MongoDB and cached in Redis`);
                
                await sendDataToAnotherAPI(data);
                res.json(data);
            } catch (error) {
                logger.error(`Error fetching data for rune ${runeName}`, error);
                res.status(500).json({ error: 'Internal Server Error' });
            }
        });

        async function sendDataToAnotherAPI(data) {
            try {
                const response = await axios.post('http://localhost:5000', data);
                logger.info(`Data sent to another API: ${response.status}`);
            } catch (error) {
                logger.error('Error sending data to another API', error);
            }
        }

        app.get('/log-data', async (req, res) => {
            logger.info('Fetching log data');
            try {
                const cachedData = await redis.get('log_data');
                if (cachedData) {
                    logger.info('Log data retrieved from Redis cache');
                    return res.json(JSON.parse(cachedData));
                }

                const filter = {};
                const sort = { '_id': -1 };
                const limit = 50;
                const cursor = logs_collection.find(filter).sort(sort).limit(limit);
                const logData = await cursor.toArray();

                await redis.set('log_data', JSON.stringify(logData), 'EX', 600); // Cache for 1 hour
                logger.info('Log data fetched from MongoDB and cached in Redis');
                res.json(logData);
            } catch (error) {
                logger.error('Error fetching log data', error);
                res.status(500).json({ error: 'Internal Server Error' });
            }
        });

        const PORT = process.env.PORT || 3030;
        app.listen(PORT, () => {
            logger.info(`Server running on port ${PORT}`);
        });
    }
});
