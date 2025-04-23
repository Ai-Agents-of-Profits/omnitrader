import os
from dotenv import load_dotenv
load_dotenv()
import logging
import ccxt
import pandas as pd
import pandas_ta as ta  # switched from talib to pandas_ta
from typing import List

# Note: pandas-ta is used for all technical indicators

def fetch_ohlcv(symbol: str, timeframe: str, limit: int) -> list:
    if limit is None:
        limit = 100
    exchange_config = {
        'enableRateLimit': True,
        'options': {'defaultType': 'linear'},
        'recvWindow': 60000,  # Increased recvWindow to 60 seconds
    }
    USE_PROXY = os.getenv('USE_PROXY', 'false').lower() == 'true'
    if USE_PROXY:
        logging.info("Using custom proxy for connection")
        exchange_config['proxies'] = {
            'http': 'http://14a72d94fa368:6d4cde2dfa@181.214.172.24:12323/',
            'https': 'http://14a72d94fa368:6d4cde2dfa@181.214.172.24:12323/'
        }
    else:
        logging.info("Connecting directly without proxy")
    api_key = os.getenv("BYBIT_API_KEY")
    api_secret = os.getenv("BYBIT_API_SECRET")
    if api_key and api_secret:
        exchange_config['apiKey'] = api_key
        exchange_config['secret'] = api_secret
    exchange = ccxt.bybit(exchange_config)
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit, params={"recvWindow": 60000})
    return ohlcv

def is_bullish_engulfing(df):
    # Bullish Engulfing: previous red, current green, current body engulfs previous
    prev = df.iloc[-2]
    curr = df.iloc[-1]
    return (prev['close'] < prev['open'] and curr['close'] > curr['open'] and
            curr['close'] > prev['open'] and curr['open'] < prev['close'])

def is_bearish_engulfing(df):
    # Bearish Engulfing: previous green, current red, current body engulfs previous
    prev = df.iloc[-2]
    curr = df.iloc[-1]
    return (prev['close'] > prev['open'] and curr['close'] < curr['open'] and
            curr['open'] > prev['close'] and curr['close'] < prev['open'])

def is_hammer(df):
    # Hammer: small body, long lower wick, at bottom of a move
    curr = df.iloc[-1]
    body = abs(curr['close'] - curr['open'])
    lower_wick = curr['open'] - curr['low'] if curr['close'] > curr['open'] else curr['close'] - curr['low']
    upper_wick = curr['high'] - curr['close'] if curr['close'] > curr['open'] else curr['high'] - curr['open']
    return (body < (curr['high'] - curr['low']) * 0.3 and lower_wick > body * 2 and upper_wick < body)

def is_doji(df):
    # Doji: open and close very close
    curr = df.iloc[-1]
    return abs(curr['close'] - curr['open']) <= 0.1 * (curr['high'] - curr['low'])

def is_morning_star(df):
    # Morning Star: red candle, small body, green candle
    if len(df) < 3:
        return False
    prev2, prev1, curr = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    return (
        prev2['close'] < prev2['open'] and
        abs(prev1['close'] - prev1['open']) < 0.3 * (prev1['high'] - prev1['low']) and
        curr['close'] > curr['open'] and
        curr['close'] > ((prev2['open'] + prev2['close']) / 2)
    )

def is_evening_star(df):
    # Evening Star: green candle, small body, red candle
    if len(df) < 3:
        return False
    prev2, prev1, curr = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    return (
        prev2['close'] > prev2['open'] and
        abs(prev1['close'] - prev1['open']) < 0.3 * (prev1['high'] - prev1['low']) and
        curr['close'] < curr['open'] and
        curr['close'] < ((prev2['open'] + prev2['close']) / 2)
    )

def is_bullish_harami(df):
    # Bullish Harami: red candle, then small green inside
    prev = df.iloc[-2]
    curr = df.iloc[-1]
    return (prev['close'] < prev['open'] and curr['close'] > curr['open'] and
            curr['open'] > prev['close'] and curr['close'] < prev['open'])

def is_bearish_harami(df):
    # Bearish Harami: green candle, then small red inside
    prev = df.iloc[-2]
    curr = df.iloc[-1]
    return (prev['close'] > prev['open'] and curr['close'] < curr['open'] and
            curr['close'] > prev['open'] and curr['open'] < prev['close'])

def is_shooting_star(df):
    # Shooting Star: small body, long upper wick, at top of a move
    curr = df.iloc[-1]
    body = abs(curr['close'] - curr['open'])
    upper_wick = curr['high'] - max(curr['close'], curr['open'])
    lower_wick = min(curr['close'], curr['open']) - curr['low']
    return (body < (curr['high'] - curr['low']) * 0.3 and upper_wick > body * 2 and lower_wick < body)

def is_three_white_soldiers(df):
    # Three White Soldiers: three consecutive green candles
    if len(df) < 3:
        return False
    last3 = df.iloc[-3:]
    return all(row['close'] > row['open'] for _, row in last3.iterrows())

def is_three_black_crows(df):
    # Three Black Crows: three consecutive red candles
    if len(df) < 3:
        return False
    last3 = df.iloc[-3:]
    return all(row['close'] < row['open'] for _, row in last3.iterrows())

def is_three_inside_up(df):
    # Three Inside Up: red candle, small green inside, next green closes above first open
    if len(df) < 3:
        return False
    prev2, prev1, curr = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    return (
        prev2['close'] < prev2['open'] and
        prev1['close'] > prev1['open'] and
        prev1['open'] > prev2['close'] and prev1['close'] < prev2['open'] and
        curr['close'] > curr['open'] and curr['close'] > prev2['open']
    )

def is_three_inside_down(df):
    # Three Inside Down: green candle, small red inside, next red closes below first open
    if len(df) < 3:
        return False
    prev2, prev1, curr = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    return (
        prev2['close'] > prev2['open'] and
        prev1['close'] < prev1['open'] and
        prev1['close'] > prev2['open'] and prev1['open'] < prev2['close'] and
        curr['close'] < curr['open'] and curr['close'] < prev2['open']
    )

def compute_indicators(ohlcv: List[List[float]]) -> dict:
    df = pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
    close = df['close'].astype(float)
    high = df['high'].astype(float)
    low = df['low'].astype(float)
    volume = df['volume'].astype(float)
    # EMA
    ema = ta.ema(close, length=21).iloc[-1]
    # SMA
    sma = ta.sma(close, length=21).iloc[-1]
    # RSI
    rsi = ta.rsi(close, length=14).iloc[-1]
    # ATR
    atr = ta.atr(high, low, close, length=14).iloc[-1]
    # MACD
    macd_df = ta.macd(close, fast=12, slow=26, signal=9)
    macd_val = macd_df['MACD_12_26_9'].iloc[-1]
    macdsignal_val = macd_df['MACDs_12_26_9'].iloc[-1]
    macdhist_val = macd_df['MACDh_12_26_9'].iloc[-1]
    # Bollinger Bands
    bb_df = ta.bbands(close, length=20, std=2)
    bb_upper = bb_df['BBU_20_2.0'].iloc[-1]
    bb_middle = bb_df['BBM_20_2.0'].iloc[-1]
    bb_lower = bb_df['BBL_20_2.0'].iloc[-1]
    # Stochastic Oscillator
    stoch_df = ta.stoch(high, low, close)
    stoch_k = stoch_df['STOCHk_14_3_3'].iloc[-1]
    stoch_d = stoch_df['STOCHd_14_3_3'].iloc[-1]
    # ADX
    adx = ta.adx(high, low, close, length=14)['ADX_14'].iloc[-1]
    # CCI
    cci = ta.cci(high, low, close, length=20).iloc[-1]
    # OBV
    obv = ta.obv(close, volume).iloc[-1]
    # VWAP (manual, as pandas-ta does not have VWAP)
    typical_price = (high + low + close) / 3
    vwap = (typical_price * volume).sum() / volume.sum() if volume.sum() != 0 else float('nan')
    # Simple momentum logic: price above EMA and RSI > 55 = bullish, below/RSI < 45 = bearish
    if close.iloc[-1] > ema and rsi > 55:
        momentum = 'bullish'
    elif close.iloc[-1] < ema and rsi < 45:
        momentum = 'bearish'
    else:
        momentum = 'neutral'

    # Fast/Slow EMA for cross
    ema_fast = ta.ema(close, length=8).iloc[-1]
    ema_slow = ta.ema(close, length=21).iloc[-1]
    if close.size > 1:
        ema_fast_prev = ta.ema(close, length=8).iloc[-2]
        ema_slow_prev = ta.ema(close, length=21).iloc[-2]
        if ema_fast_prev < ema_slow_prev and ema_fast > ema_slow:
            ema_cross = "bullish"
        elif ema_fast_prev > ema_slow_prev and ema_fast < ema_slow:
            ema_cross = "bearish"
        else:
            ema_cross = "none"
    else:
        ema_cross = "none"

    # Swing high/low (simple: last N bars)
    N = 10
    swing_high = high.rolling(N).max().iloc[-1]
    swing_low = low.rolling(N).min().iloc[-1]

    # Volume context
    volume_avg_20 = volume.rolling(20).mean().iloc[-1]
    volume_spike = float(volume.iloc[-1] / volume_avg_20) if volume_avg_20 != 0 else float('nan')

    # ATR percent
    atr_pct = float(atr / close.iloc[-1] * 100) if close.iloc[-1] != 0 else float('nan')

    # BB width
    bb_width = float(bb_upper - bb_lower)

    # OBV/ADX slopes
    obv_hist = ta.obv(close, volume)
    obv_slope = float(obv_hist.iloc[-1] - obv_hist.iloc[-2]) if obv_hist.size > 1 else float('nan')
    adx_hist = ta.adx(high, low, close, length=14)['ADX_14']
    adx_slope = float(adx_hist.iloc[-1] - adx_hist.iloc[-2]) if adx_hist.size > 1 else float('nan')

    # Manual candle pattern detection
    detected_patterns = []
    # Engulfing
    if len(df) > 1:
        if is_bullish_engulfing(df):
            detected_patterns.append('bullish_engulfing')
        if is_bearish_engulfing(df):
            detected_patterns.append('bearish_engulfing')
        if is_hammer(df):
            detected_patterns.append('hammer')
        if is_doji(df):
            detected_patterns.append('doji')
        if is_bullish_harami(df):
            detected_patterns.append('bullish_harami')
        if is_bearish_harami(df):
            detected_patterns.append('bearish_harami')
        if is_shooting_star(df):
            detected_patterns.append('shooting_star')
    if len(df) > 2:
        if is_morning_star(df):
            detected_patterns.append('morning_star')
        if is_evening_star(df):
            detected_patterns.append('evening_star')
        if is_three_white_soldiers(df):
            detected_patterns.append('three_white_soldiers')
        if is_three_black_crows(df):
            detected_patterns.append('three_black_crows')
        if is_three_inside_up(df):
            detected_patterns.append('three_inside_up')
        if is_three_inside_down(df):
            detected_patterns.append('three_inside_down')
    candle_pattern = detected_patterns if detected_patterns else None

    # Price near BB upper
    near_bb_upper = abs(close.iloc[-1] - bb_upper) < 0.1 * atr

    return {
        'ema': float(ema),
        'sma': float(sma),
        'ema_fast': float(ema_fast),
        'ema_slow': float(ema_slow),
        'ema_cross': ema_cross,
        'rsi': float(rsi),
        'atr': float(atr),
        'atr_pct': atr_pct,
        'macd': float(macd_val),
        'macdsignal': float(macdsignal_val),
        'macdhist': float(macdhist_val),
        'bb_upper': float(bb_upper),
        'bb_middle': float(bb_middle),
        'bb_lower': float(bb_lower),
        'bb_width': bb_width,
        'stoch_k': float(stoch_k),
        'stoch_d': float(stoch_d),
        'adx': float(adx),
        'adx_slope': adx_slope,
        'cci': float(cci),
        'obv': float(obv),
        'obv_slope': obv_slope,
        'vwap': float(vwap),
        'momentum': momentum,
        'last_close': float(close.iloc[-1]),
        'swing_high': float(swing_high),
        'swing_low': float(swing_low),
        'volume_avg_20': float(volume_avg_20),
        'volume_spike': float(volume_spike),
        'timestamp': int(df['ts'].iloc[-1]),
        'candle_pattern': candle_pattern,
        'near_bb_upper': bool(near_bb_upper)
    }
