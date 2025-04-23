import os
import json
import logging
from dotenv import load_dotenv
import psycopg2
from trade_utils import fetch_ohlcv, compute_indicators
import time
import ccxt

def get_timescaledb_conn():
    load_dotenv()
    db_url = os.getenv("TIMESCALEDB_URL")
    if db_url is None:
        raise ValueError("TIMESCALEDB_URL not set in environment.")
    return psycopg2.connect(db_url)

def ensure_table_exists():
    conn = get_timescaledb_conn()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS market_indicators (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            timestamp BIGINT NOT NULL,
            indicators JSONB NOT NULL,
            PRIMARY KEY (symbol, timeframe, timestamp)
        );
    ''')
    conn.commit()
    cur.close()
    conn.close()

def store_to_timescaledb(symbol, timeframe, indicators, timestamp):
    conn = get_timescaledb_conn()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO market_indicators (symbol, timeframe, timestamp, indicators)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (symbol, timeframe, timestamp) DO UPDATE
        SET indicators = EXCLUDED.indicators;
    ''', (symbol, timeframe, timestamp, json.dumps(indicators)))
    conn.commit()
    cur.close()
    conn.close()

def run_etl():
    symbol = "CORE/USDT:USDT"
    for timeframe in ["1m", "5m", "15m"]:
        for attempt in range(3):  # Try up to 3 times
            try:
                ohlcv = fetch_ohlcv(symbol, timeframe, 100)
                indicators = compute_indicators(ohlcv)
                timestamp = int(ohlcv[-1][0])
                store_to_timescaledb(symbol, timeframe, indicators, timestamp)
                print(f"Stored indicators for {symbol} {timeframe} at {timestamp}")
                break  # Success!
            except Exception as e:
                logging.exception(f"ETL failed for {symbol} {timeframe}: {e}")
                break  # Don't retry for other errors

if __name__ == "__main__":
    ensure_table_exists()
    run_etl()
