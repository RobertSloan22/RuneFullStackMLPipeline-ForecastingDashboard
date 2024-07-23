import time
import json
import logging
import cloudscraper
import psycopg2
from psycopg2 import sql
from logging.handlers import RotatingFileHandler

# Configure logging
LOG_FILE = 'app.log'
handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=2)  # 5 MB max size, 2 backups
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[handler])

# Constants
API_URL_RUN = "https://www.geniidata.com/api/dashboard/query/run"
API_URL_STATUS = "https://www.geniidata.com/api/dashboard/query/status"
API_URL_DATA = "https://www.geniidata.com/api/dashboard/chart/data"
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json;charset=UTF-8",
    "origin": "https://studio.geniidata.com",
    "referer": "https://studio.geniidata.com/",
    "sec-ch-ua": "\"Microsoft Edge\";v=\"125\", \"Chromium\";v=\"125\", \"Not.A/Brand\";v=\"24\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "x-csrf-token": "vACNHtxV-RXPmPf_n9dT0GU5inJhTK6zRa3A",
    "cookie": "geniidata.sid=s%3ARjPuTfc9BgJsxnNpBE-ujLretN7mkv24.xguP8Txh%2BO3%2BQF0sv4Oqx8fQNTJSRptJGxv7Ym%2Fhj%2Fw; theme=dark; _gcl_au=1.1.1524685981.1716595779.1126843500.1716595834.1716595833; _gid=GA1.2.1187319215.1717218055; _ga=GA1.1.1710745345.1711734543; _ga_3XP1XSS13R=GS1.1.1717716373.79.1.1717716376.0.0.0",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    "priority": "u=1, i"
}

SQL_QUERY = {
    "worksheetId": 127325,
    "sql": """
-- Common Table Expressions (CTEs) to aggregate data from runes.fact_listings
WITH latest_time AS (
    SELECT
        rune_name,
        marketplace,
        MAX(time) AS latest_time
    FROM runes.fact_listings
    GROUP BY rune_name, marketplace
),
latest_data AS (
    SELECT
        f.rune_name,
        f.marketplace,
        f.time AS latest_time,
        f.price_sats,
        f.quantity
    FROM runes.fact_listings f
    JOIN latest_time l ON f.rune_name = l.rune_name AND f.marketplace = l.marketplace AND f.time = l.latest_time
),
aggregated_data AS (
    SELECT
        rune_name,
        MIN(price_sats) AS min_price,
        MAX(price_sats) AS max_price,
        AVG(price_sats) AS avg_price,
        COUNT(price_sats) AS count_listings,
        SUM(quantity) AS total_quantity
    FROM latest_data
    GROUP BY rune_name
),
percentile_ranks AS (
    SELECT
        rune_name,
        price_sats,
        NTILE(4) OVER (PARTITION BY rune_name ORDER BY price_sats) AS price_ntile
    FROM latest_data
),
percentile_agg AS (
    SELECT
        rune_name,
        MAX(CASE WHEN price_ntile = 1 THEN price_sats END) AS percentile_25,
        MAX(CASE WHEN price_ntile = 2 THEN price_sats END) AS median_price,
        MAX(CASE WHEN price_ntile = 3 THEN price_sats END) AS percentile_75
    FROM percentile_ranks
    GROUP BY rune_name
),
final_aggregated_data AS (
    SELECT
        l.rune_name,
        MAX(l.latest_time) AS latest_time,
        a.min_price,
        a.max_price,
        a.avg_price,
        p.percentile_25,
        p.median_price,
        p.percentile_75,
        a.count_listings,
        a.total_quantity
    FROM latest_data l
    JOIN aggregated_data a ON l.rune_name = a.rune_name
    JOIN percentile_agg p ON l.rune_name = p.rune_name
    GROUP BY l.rune_name, a.min_price, a.max_price, a.avg_price, p.percentile_25, p.median_price, p.percentile_75, a.count_listings, a.total_quantity
),

-- Determine the maximum block height
MaxBlockHeight AS (
    SELECT MAX(block_height) AS max_block_height
    FROM runes.fact_balance_delta
),

-- Calculate the balance changes for the last 1 block, 3 blocks, and 10 blocks
RecentBalanceChanges AS (
    SELECT
        rune_name,
        SUM(CASE WHEN block_height >= (SELECT max_block_height FROM MaxBlockHeight) - 0 THEN abs(balance_delta) ELSE 0 END) AS balance_change_last_1_block,
        SUM(CASE WHEN block_height >= (SELECT max_block_height FROM MaxBlockHeight) - 2 THEN abs(balance_delta) ELSE 0 END) AS balance_change_last_3_blocks,
        SUM(CASE WHEN block_height >= (SELECT max_block_height FROM MaxBlockHeight) - 9 THEN abs(balance_delta) ELSE 0 END) AS balance_change_last_10_blocks
    FROM runes.fact_balance_delta
    GROUP BY rune_name
)


-- Final query combining data from runes.dim_tokens_info and the aggregated data
SELECT
    current_timestamp as timestamp,
    INFO.rune_id,
    INFO.rune_name,
    INFO.rune_number,
    INFO.symbol,
    INFO.etching_time,
    INFO.etching,
    INFO.inscription_id,
    INFO.turbo,
    INFO.amount,
    INFO.supply,
    INFO.burned,
    INFO.premine,
    INFO.minted,
    INFO.mints,
    INFO.holders,
    INFO.price_sats,
    INFO.price_usd,
    INFO.price_change,
    INFO.volume_1h_btc,
    INFO.volume_1d_btc,
    INFO.volume_7d_btc,
    INFO.volume_total_btc,
    INFO.sales_1h,
    INFO.sales_1d,
    INFO.sales_7d,
    INFO.sales_total,
    INFO.sellers_1h,
    INFO.sellers_1d,
    INFO.sellers_7d,
    INFO.buyers_1h,
    INFO.buyers_1d,
    INFO.buyers_7d,
    FAD.min_price as listings_min_price,
    FAD.max_price as listings_max_price,
    FAD.avg_price as listings_avg_price,
    FAD.percentile_25 as listings_percentile_25,
    FAD.median_price as listings_median_price,
    FAD.percentile_75 as listings_percentile_75,
    FAD.count_listings,
    FAD.total_quantity as listings_total_quantity,
    balance_change_last_1_block,
    balance_change_last_3_blocks,
    balance_change_last_10_blocks
FROM runes.dim_tokens_info AS INFO
LEFT JOIN final_aggregated_data AS FAD
ON INFO.rune_name = FAD.rune_name
LEFT JOIN RecentBalanceChanges
    on RecentBalanceChanges.rune_name = INFO.rune_name
ORDER BY INFO.supply * INFO.price_usd DESC;
    """,
    "debug": False
}

# Database connection details
DB_NAME = 'sandbox'
DB_USER = 'postgres'
DB_HOST = 'runes.csxbyr0egtki.us-east-1.rds.amazonaws.com'
DB_PASSWORD = 'uIPRefz6doiqQcbpM5po'
DB_PORT = '5432'

# Initialize the scraper
scraper = cloudscraper.create_scraper()

# Function to run the initial SQL query
def run_sql_query():
    try:
        response = scraper.post(API_URL_RUN, headers=HEADERS, data=json.dumps(SQL_QUERY).encode('utf-8'))
        response.raise_for_status()
        return response
    except Exception as e:
        logging.error(f"Error during SQL query request: {e}")
        return None

# Function to check the status of the query
def check_query_status(query_id):
    try:
        response = scraper.get(f"{API_URL_STATUS}?queryId={query_id}&checkNum={int(time.time()*1000)}", headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Error during status check request: {e}")
        return None

# Function to fetch the result data for a specific page
def fetch_query_data(page, page_size=100):
    body = json.dumps({
        "sort": None,
        "order": None,
        "pageSize": page_size,
        "page": page,
        "debug": False,
        "searchKey": "",
        "searchValue": "",
        "type": 1,
        "worksheetId": 127325
    }).encode('utf-8')
    try:
        response = scraper.post(API_URL_DATA, headers=HEADERS, data=body)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Error during data fetch request: {e}")
        return None

# Function to create the table if it doesn't exist
def create_table_if_not_exists():
    create_table_query = """
    CREATE TABLE IF NOT EXISTS runes_token_info_genii (
        timestamp TIMESTAMPTZ,
        rune_id TEXT,
        rune_name TEXT,
        rune_number TEXT,
        symbol TEXT,
        etching_time TEXT,
        etching TEXT,
        inscription_id TEXT,
        turbo TEXT,
        amount NUMERIC,
        supply NUMERIC,
        burned NUMERIC,
        premine NUMERIC,
        minted NUMERIC,
        mints NUMERIC,
        holders NUMERIC,
        price_sats NUMERIC,
        price_usd NUMERIC,
        price_change NUMERIC,
        volume_1h_btc NUMERIC,
        volume_1d_btc NUMERIC,
        volume_7d_btc NUMERIC,
        volume_total_btc NUMERIC,
        sales_1h NUMERIC,
        sales_1d NUMERIC,
        sales_7d NUMERIC,
        sales_total NUMERIC,
        sellers_1h NUMERIC,
        sellers_1d NUMERIC,
        sellers_7d NUMERIC,
        buyers_1h NUMERIC,
        buyers_1d NUMERIC,
        buyers_7d NUMERIC,
        listings_min_price NUMERIC,
        listings_max_price NUMERIC,
        listings_avg_price NUMERIC,
        listings_percentile_25 NUMERIC,
        listings_median_price NUMERIC,
        listings_percentile_75 NUMERIC,
        count_listings NUMERIC,
        listings_total_quantity NUMERIC,
        balance_change_last_1_block NUMERIC,
        balance_change_last_3_blocks NUMERIC,
        balance_change_last_10_blocks NUMERIC
    );
    """
    try:
        connection = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cursor = connection.cursor()
        cursor.execute(create_table_query)
        connection.commit()
        logging.info("Table created or already exists")
    except Exception as e:
        logging.error(f"Error creating table: {e}")
    finally:
        cursor.close()
        connection.close()

# Function to save data to the PostgreSQL database in batches
def save_to_database(data, batch_size=100):
    try:
        connection = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cursor = connection.cursor()

        insert_query = sql.SQL("""
        INSERT INTO runes_token_info_genii (
            timestamp, rune_id, rune_name, rune_number, symbol, etching_time, etching,
            inscription_id, turbo, amount, supply, burned, premine, minted, mints, holders,
            price_sats, price_usd, price_change, volume_1h_btc, volume_1d_btc, volume_7d_btc,
            volume_total_btc, sales_1h, sales_1d, sales_7d, sales_total, sellers_1h, sellers_1d,
            sellers_7d, buyers_1h, buyers_1d, buyers_7d, listings_min_price, listings_max_price,
            listings_avg_price, listings_percentile_25, listings_median_price, listings_percentile_75,
            count_listings, listings_total_quantity, balance_change_last_1_block,
            balance_change_last_3_blocks, balance_change_last_10_blocks
        ) VALUES (
            %(timestamp)s, %(rune_id)s, %(rune_name)s, %(rune_number)s, %(symbol)s, %(etching_time)s, %(etching)s,
            %(inscription_id)s, %(turbo)s, %(amount)s, %(supply)s, %(burned)s, %(premine)s, %(minted)s, %(mints)s, %(holders)s,
            %(price_sats)s, %(price_usd)s, %(price_change)s, %(volume_1h_btc)s, %(volume_1d_btc)s, %(volume_7d_btc)s,
            %(volume_total_btc)s, %(sales_1h)s, %(sales_1d)s, %(sales_7d)s, %(sales_total)s, %(sellers_1h)s, %(sellers_1d)s,
            %(sellers_7d)s, %(buyers_1h)s, %(buyers_1d)s, %(buyers_7d)s, %(listings_min_price)s, %(listings_max_price)s,
            %(listings_avg_price)s, %(listings_percentile_25)s, %(listings_median_price)s, %(listings_percentile_75)s,
            %(count_listings)s, %(listings_total_quantity)s, %(balance_change_last_1_block)s,
            %(balance_change_last_3_blocks)s, %(balance_change_last_10_blocks)s
        )
        """)

        # Batch processing
        for i in range(0, len(data), batch_size):
            batch = data[i:i+batch_size]
            cursor.executemany(insert_query, batch)
            connection.commit()
            logging.info(f"Batch {i//batch_size + 1} saved to database")
            if batch:  # Check if batch is not empty
                logging.info("First 10 entries of the batch: %s", json.dumps(batch[:10], indent=2))
                logging.info("Last 10 entries of the batch: %s", json.dumps(batch[-10:], indent=2))

    except Exception as e:
        logging.error(f"Error saving data to database: {e}")
        connection.rollback()  # Rollback in case of error
    finally:
        cursor.close()
        connection.close()

# Main function to run the SQL query and fetch results
def main():
    create_table_if_not_exists()  # Ensure the table exists before starting the loop
    while True:
        start_time = time.time()

        run_response = run_sql_query()
        if run_response is None or run_response.status_code != 201:
            logging.error(f"Error in running SQL query: {run_response.status_code if run_response else 'No response'}")
            if run_response:
                logging.error(run_response.json())
            time.sleep(300)  # Wait 5 minutes before retrying
            continue

        run_response_json = run_response.json()
        if 'data' not in run_response_json:
            logging.error("Error in running SQL query: %s", run_response_json)
            time.sleep(300)  # Wait 5 minutes before retrying
            continue

        query_id = run_response_json["data"]["queryId"]
        logging.info(f"Query ID: {query_id}")

        while True:
            status_response = check_query_status(query_id)
            if status_response is None or 'data' not in status_response:
                logging.error("Error in checking query status: %s", status_response)
                time.sleep(300)  # Wait 5 minutes before retrying
                continue

            query_status = status_response["data"]["queryStatus"]
            logging.info(f"Query Status: {query_status}")

            if query_status == 2:  # Status 2 means ready
                data_response = fetch_query_data(1)
                if data_response is None or 'data' not in data_response:
                    logging.error("Error in fetching query data: %s", data_response)
                    logging.error("Data response: %s", data_response)
                    time.sleep(300)  # Wait 5 minutes before retrying
                    continue

                results = data_response["data"]["list"]
                total_count = data_response["data"]["resultCnt"]

                if total_count is None:
                    logging.error("Error: 'resultCnt' not found in data response")
                    logging.error("Data response: %s", data_response)
                    time.sleep(300)  # Wait 5 minutes before retrying
                    continue

                page_size = 100
                total_pages = (total_count + page_size - 1) // page_size  # Calculate the number of pages

                for page in range(2, total_pages + 1):
                    time.sleep(0.5)  # Adjust sleep to avoid rate limiting
                    page_data = fetch_query_data(page, page_size)
                    if page_data and 'data' in page_data and 'list' in page_data["data"]:
                        results.extend(page_data["data"]["list"])
                    else:
                        logging.error(f"Error fetching data for page {page}: %s", page_data)
                        break

                logging.info("First 10 entries: %s", json.dumps(results[:10], indent=2))
                logging.info("Last 10 entries: %s", json.dumps(results[-10:], indent=2))

                save_to_database(results)
                logging.info("Data saved to the database")
                break

            time.sleep(1)  # Wait for 1 second before checking the status again

        end_time = time.time()
        run_duration = end_time - start_time
        logging.info(f"Run duration: {run_duration} seconds")
        time.sleep(max(0, 300 - run_duration))  # Adjust sleep to account for the script's run time

if __name__ == "__main__":
    from log_server import app
    main()
    app.run(host='0.0.0.0', port=6000, use_reloader=False)
