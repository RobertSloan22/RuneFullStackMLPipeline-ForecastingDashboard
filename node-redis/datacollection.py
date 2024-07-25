import requests
import psycopg2
from psycopg2 import sql
import time
import json
from dotenv import load_dotenv
import os

load_dotenv()  # take environment variables from .env.
AUTH_TOKEN = os.getenv('AUTH_TOKEN')

# Database connection details
conn_details = 



headers = {
    "Authorization": AUTH_TOKEN,
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-CH-UA": "\"Not A(Brand\";v=\"99\", \"Microsoft Edge\";v=\"121\", \"Chromium\";v=\"121\"",
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": "\"Windows\"",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "X-Debug-Options": "bugReporterEnabled",
    "X-Discord-Locale": "en-US",
    "X-Discord-Timezone": "America/Los_Angeles",
}

# Including all cookies as provided
cookies = {
    "__dcfduid": "0eb87a805e3611eeb0c5172c1d8a127e",
    "__sdcfduid": "0eb87a815e3611eeb0c5172c1d8a127eadb7421d9c4263db5c5f3860808fba5aa656ebd00291ecba4038993fd706d963",
    "_ga_XXP2R74F46": "GS1.2.1699745291.1.0.1699745291.0.0.0",
    "__cfruid": "275cd80707867f0c5915cff170cd9c0104c38228-1707796659",
    "_cfuvid": "XBQT9C_CZO1rFrgQgSFTDzAvLPu0QX90XJXXJmJTOes-1707796659923-0-604800000",
    "locale": "en-US",
    "cf_clearance": "ol0n0Ip0uXf3UnxtWjYf673qt_55MUuTqhzep7MorJA-1707796660-1-AUVYoky4MnxZYXLIBPVzztudKlJIHkn0yKshrAyM+MXLmoMm3wQMm8T9gOhqsHjrj3SxPYVoOJRSTmGg+/hJ8Zs=",
    "_gcl_au": "1.1.1857939141.1707796660",
    "OptanonConsent": "isIABGlobal=false&datestamp=Mon+Feb+13+2024+01%3A57%3A40+GMT-0800+(Pacific+Standard+Time)&version=6.33.0&hosts=&landingPath=https%3A%2F%2Fdiscord.com%2F&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A1",
    "_ga": "GA1.1.1160875646.1699745291",
    "_ga_Q149DFWHT7": "GS1.1.1707796660.1.0.1707796662.0.0.0",
}

# List of channels to check


def fetch_discord_messages(channel_id):
    """Fetches messages from a specified Discord channel using Discord API."""
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages?limit=50"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to fetch messages for channel {channel_id}: HTTP {response.status_code} - {response.text}")
            return []
    except requests.exceptions.RequestException as e:
        print(f"Request exception for channel {channel_id}: {e}")
        return []

def insert_new_messages(messages, channel_id, nickname, conn):
    """Inserts new messages into the PostgreSQL database."""
    with conn.cursor() as cur:
        for message in messages:
            cur.execute(sql.SQL("SELECT 1 FROM discord_messages WHERE message_id = %s"), (message["id"],))
            if cur.fetchone() is None:
                # Handling message and author details
                content = message.get("content", None)
                timestamp = message.get("timestamp")
                author = message.get("author", {})
                author_id = author.get("id")
                author_username = author.get("username")
                author_global_name = author.get("global_name", None)

                # Handling referenced messages
                ref_msg = message.get("referenced_message", None)
                ref_msg_id = ref_msg.get("id") if ref_msg else None
                ref_msg_content = ref_msg.get("content") if ref_msg else None
                ref_author = ref_msg.get("author", {}) if ref_msg else {}
                ref_msg_username = ref_author.get("username", None)
                ref_msg_global_name = ref_author.get("global_name", None)

                # Handling attachments
                attachments = message.get("attachments", [])
                attachment_file_name = attachments[0].get("filename") if attachments else None
                attachment_url = attachments[0].get("url") if attachments else None

                # Insert the data into the database
                cur.execute(sql.SQL("""
                    INSERT INTO discord_messages (
                        message_id, channel_id, nickname, content, author_id, author_username,
                        author_global_name, timestamp, referenced_message_id, referenced_message_content,
                        referenced_message_username, referenced_message_global_name, attachment_file_name, attachment_url
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """), (
                    message["id"], channel_id, nickname, content, author_id, author_username,
                    author_global_name, timestamp, ref_msg_id, ref_msg_content,
                    ref_msg_username, ref_msg_global_name, attachment_file_name, attachment_url
                ))
        conn.commit()

def setup_database():
    """Ensures the necessary table exists in the database."""
    with psycopg2.connect(conn_details) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS discord_messages (
                    message_id VARCHAR(50) PRIMARY KEY,
                    channel_id VARCHAR(50),
                    nickname VARCHAR(100),
                    content TEXT,
                    author_id VARCHAR(50),
                    author_username VARCHAR(100),
                    author_global_name VARCHAR(100),
                    timestamp TIMESTAMP,
                    referenced_message_id VARCHAR(50),
                    referenced_message_content TEXT,
                    referenced_message_username VARCHAR(100),
                    referenced_message_global_name VARCHAR(100),
                    attachment_file_name VARCHAR(255),
                    attachment_url TEXT
                )
            """)
            conn.commit()

def main():
    """Main function to handle fetching and storing Discord messages."""
    setup_database()
    with psycopg2.connect(conn_details) as conn:
        while True:
            for channel in channels:
                print(f"Processing channel: {channel['nickname']} (ID: {channel['id']})")
                messages = fetch_discord_messages(channel["id"])
                if messages:
                    print(f"Fetched {len(messages)} messages for channel: {channel['nickname']}")
                    insert_new_messages(messages, channel["id"], channel["nickname"], conn)
                else:
                    print(f"No new messages or failed to fetch messages for channel: {channel['nickname']}")
                time.sleep(1.2)  # Respectful delay between requests
            print("Completed one loop through all channels. Restarting...")

if __name__ == "__main__":
    main()
