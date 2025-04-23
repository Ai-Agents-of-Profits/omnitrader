import os
import psycopg2
import json
from dotenv import load_dotenv
from agents import function_tool

load_dotenv()

def get_timescaledb_conn():
    db_url = os.getenv("TIMESCALEDB_URL")
    if db_url is None:
        raise ValueError("TIMESCALEDB_URL not set in environment.")
    return psycopg2.connect(db_url)

@function_tool
def get_latest_indicators(symbol: str, timeframe: str) -> dict:
    """Fetch the latest precomputed indicators for a symbol and timeframe from TimescaleDB."""
    # Normalize timeframe input
    tf_map = {"1 m": "1m", "5 m": "5m", "15 m": "15m", "1m": "1m", "5m": "5m", "15m": "15m"}
    timeframe = tf_map.get(timeframe.strip(), timeframe.replace(" ", ""))
    conn = get_timescaledb_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT indicators FROM market_indicators
        WHERE symbol = %s AND timeframe = %s
        ORDER BY timestamp DESC LIMIT 1
    ''', (symbol, timeframe))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return row[0]  # Already a dict if using psycopg2 with jsonb
    else:
        return {"error": "No data found for this symbol/timeframe."}
