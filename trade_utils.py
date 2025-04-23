import os
from dotenv import load_dotenv
load_dotenv()
import logging
import ccxt
import pandas as pd
import talib
from typing import List

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

def compute_indicators(ohlcv: List[List[float]]) -> dict:
    df = pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
    close = df['close'].astype(float)
    high = df['high'].astype(float)
    low = df['low'].astype(float)
    volume = df['volume'].astype(float)
    # EMA
    ema = talib.EMA(close, timeperiod=21).iloc[-1]
    # SMA
    sma = talib.SMA(close, timeperiod=21).iloc[-1]
    # RSI
    rsi = talib.RSI(close, timeperiod=14).iloc[-1]
    # ATR
    atr = talib.ATR(high, low, close, timeperiod=14).iloc[-1]
    # MACD
    macd, macdsignal, macdhist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
    macd_val = macd.iloc[-1]
    macdsignal_val = macdsignal.iloc[-1]
    macdhist_val = macdhist.iloc[-1]
    # Bollinger Bands
    upper, middle, lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
    bb_upper = upper.iloc[-1]
    bb_middle = middle.iloc[-1]
    bb_lower = lower.iloc[-1]
    # Stochastic Oscillator
    slowk, slowd = talib.STOCH(high, low, close)
    stoch_k = slowk.iloc[-1]
    stoch_d = slowd.iloc[-1]
    # ADX
    adx = talib.ADX(high, low, close, timeperiod=14).iloc[-1]
    # CCI
    cci = talib.CCI(high, low, close, timeperiod=20).iloc[-1]
    # OBV
    obv = talib.OBV(close, volume).iloc[-1]
    # VWAP (manual, as TA-Lib does not have VWAP)
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
    ema_fast = talib.EMA(close, timeperiod=8).iloc[-1]
    ema_slow = talib.EMA(close, timeperiod=21).iloc[-1]
    if close.size > 1:
        ema_fast_prev = talib.EMA(close, timeperiod=8).iloc[-2]
        ema_slow_prev = talib.EMA(close, timeperiod=21).iloc[-2]
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
    obv_hist = talib.OBV(close, volume)
    obv_slope = float(obv_hist.iloc[-1] - obv_hist.iloc[-2]) if obv_hist.size > 1 else float('nan')
    adx_hist = talib.ADX(high, low, close, timeperiod=14)
    adx_slope = float(adx_hist.iloc[-1] - adx_hist.iloc[-2]) if adx_hist.size > 1 else float('nan')

    # Advanced candle pattern detection using TA-Lib
    pattern_funcs = {
        'engulfing': talib.CDLENGULFING,
        'hammer': talib.CDLHAMMER,
        'doji': talib.CDLDOJI,
        'morning_star': talib.CDLMORNINGSTAR,
        'evening_star': talib.CDLEVENINGSTAR,
        'harami': talib.CDLHARAMI,
        'shooting_star': talib.CDLSHOOTINGSTAR,
        'three_white_soldiers': talib.CDL3WHITESOLDIERS,
        'three_black_crows': talib.CDL3BLACKCROWS,
        'three_inside': talib.CDL3INSIDE
    }
    detected_patterns = []
    for name, func in pattern_funcs.items():
        # Some TA-Lib patterns need all 4 OHLC, some only 3, but all accept 4
        try:
            val = func(df['open'], high, low, close).iloc[-1]
            if val > 0:
                detected_patterns.append(f"bullish_{name}")
            elif val < 0:
                detected_patterns.append(f"bearish_{name}")
        except Exception:
            continue
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
