import ccxt
import pandas as pd
from datetime import datetime, timezone
import time
import os
import logging
from dotenv import load_dotenv
from pathlib import Path

script_run_dir = Path.cwd()
env_path = script_run_dir / 'rsi_divergence_bot' / '.env'

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    logging.info(f"Loaded environment variables from: {env_path}")
else:
    logging.warning(f".env file not found at {env_path}. Checking current directory or system environment.")
    load_dotenv()

# --- Configuration ---
SYMBOL = 'CORE/USDT:USDT'  # Bybit USDT Perpetual symbol
TIMEFRAMES = ['1d']
YEARS = [
    ('2023-01-01', '2025-04-20', '2023-2025_Apr20'),
]
OUTPUT_FOLDER = 'datas'
RATE_LIMIT_DELAY = 0.2
MAX_RETRIES = 5

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

logging.info("Initializing Bybit connection...")
# Use Bybit USDT Perpetual
exchange_config = {
    'enableRateLimit': True,
    'options': {
        'defaultType': 'linear',  # Bybit USDT Perpetual
    }
}

# Check if we should use the proxy based on environment variable
USE_PROXY = os.getenv('USE_PROXY', 'false').lower() == 'true'
if USE_PROXY:
    logging.info("Using custom proxy for connection")
    exchange_config['proxies'] = {
        'http': 'http://14a72d94fa368:6d4cde2dfa@181.214.172.24:12323/',
        'https': 'http://14a72d94fa368:6d4cde2dfa@181.214.172.24:12323/'
    }
else:
    logging.info("Connecting directly without proxy")

exchange = ccxt.bybit(exchange_config)

def fetch_paginated_ohlcv(symbol, timeframe, since, end_timestamp_ms, limit=1000):
    """Fetches historical OHLCV data in batches."""
    all_ohlcv = []
    current_since = since
    retries = 0

    logging.info(f"Starting fetch for {symbol} {timeframe} from {datetime.fromtimestamp(since/1000, tz=timezone.utc)} to {datetime.fromtimestamp(end_timestamp_ms/1000, tz=timezone.utc)}")
    while current_since < end_timestamp_ms:
        try:
            fetch_start_dt = datetime.fromtimestamp(current_since / 1000, tz=timezone.utc)
            logging.debug(f"Fetching {limit} candles for {symbol} {timeframe} starting from {fetch_start_dt}")
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=current_since, limit=limit)

            if not ohlcv:
                logging.debug(f"No more data returned from {fetch_start_dt}. Stopping pagination.")
                break

            all_ohlcv.extend(ohlcv)
            last_timestamp = ohlcv[-1][0]
            current_since = last_timestamp + exchange.parse_timeframe(timeframe) * 1000
            logging.info(f"Fetched up to {datetime.fromtimestamp(last_timestamp / 1000, tz=timezone.utc)} ({len(all_ohlcv)} total candles)")
            time.sleep(RATE_LIMIT_DELAY)
            retries = 0

        except ccxt.RateLimitExceeded as e:
            retries += 1
            if retries > MAX_RETRIES:
                logging.error(f"Rate limit exceeded too many times after fetching {len(all_ohlcv)} candles: {e}")
                raise
            wait_time = (2 ** retries) * 0.5
            logging.warning(f"Rate limit exceeded. Retrying in {wait_time:.2f} seconds... (Attempt {retries}/{MAX_RETRIES})")
            time.sleep(wait_time)
        except (ccxt.NetworkError, ccxt.ExchangeError) as e:
            retries += 1
            if retries > MAX_RETRIES:
                logging.error(f"Network/Exchange error after {len(all_ohlcv)} candles and multiple retries: {e}")
                raise
            wait_time = (2 ** retries) * 1.0
            logging.warning(f"Network/Exchange error: {e}. Retrying in {wait_time:.2f} seconds... (Attempt {retries}/{MAX_RETRIES})")
            time.sleep(wait_time)
        except Exception as e:
            logging.error(f"An unexpected error occurred after fetching {len(all_ohlcv)} candles: {e}", exc_info=True)
            raise

    logging.info(f"Finished fetching {len(all_ohlcv)} total candles for {symbol} {timeframe}.")
    return all_ohlcv

for start_date, end_date, year_str in YEARS:
    start_dt = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    start_timestamp_ms = int(start_dt.timestamp() * 1000)
    end_timestamp_ms = int(end_dt.timestamp() * 1000)
    for tf in TIMEFRAMES:
        logging.info(f"--- Starting download for {SYMBOL} - {tf} - {year_str} ---")
        try:
            ohlcv_data = fetch_paginated_ohlcv(SYMBOL, tf, start_timestamp_ms, end_timestamp_ms)
            if not ohlcv_data:
                logging.warning(f"No data fetched for {tf} {year_str}. Skipping file save.")
                continue
            df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['Date'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            df = df[(df['timestamp'] >= start_timestamp_ms) & (df['timestamp'] < end_timestamp_ms)]
            df = df.drop_duplicates(subset=['timestamp'])
            df_to_save = df[['Date', 'open', 'high', 'low', 'close', 'volume']].copy()
            df_to_save.set_index('Date', inplace=True)
            # Adjust filename for Bybit symbol format
            filename_symbol_part = SYMBOL.replace('/', '').replace(':', '')
            filename = f"{filename_symbol_part}_{tf}_{year_str}_bybit.csv"
            filepath = os.path.join(OUTPUT_FOLDER, filename)
            logging.info(f"Saving data for {tf} {year_str} to {filepath} ({len(df_to_save)} rows)...")
            df_to_save.to_csv(filepath)
            logging.info(f"Successfully saved {filepath}")
        except Exception as e:
            logging.error(f"Failed to download or process data for {tf} {year_str}: {e}", exc_info=True)

logging.info("--- Data download process finished ---")