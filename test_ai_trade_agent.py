import os
import logging
import pandas as pd
from trade_utils import fetch_ohlcv, compute_indicators

def test_fetch_ohlcv():
    """
    Test fetching OHLCV data from Bybit for CORE/USDT:USDT 1m and 5m.
    """
    print("Testing fetch_ohlcv for 1m...")
    ohlcv_1m = fetch_ohlcv('CORE/USDT:USDT', '1m', limit=20)
    assert isinstance(ohlcv_1m, list), "fetch_ohlcv should return a list"
    assert len(ohlcv_1m) > 0, "Should return at least one candle"
    assert len(ohlcv_1m[0]) == 6, "Each OHLCV entry should have 6 values"
    print("Sample 1m candle:", ohlcv_1m[-1])
    
    print("Testing fetch_ohlcv for 5m...")
    ohlcv_5m = fetch_ohlcv('CORE/USDT:USDT', '5m', limit=20)
    assert isinstance(ohlcv_5m, list), "fetch_ohlcv should return a list"
    assert len(ohlcv_5m) > 0, "Should return at least one candle"
    assert len(ohlcv_5m[0]) == 6, "Each OHLCV entry should have 6 values"
    print("Sample 5m candle:", ohlcv_5m[-1])

    return ohlcv_1m, ohlcv_5m

def test_compute_indicators():
    """
    Test computing indicators on OHLCV data.
    """
    ohlcv_1m, ohlcv_5m = test_fetch_ohlcv()
    print("Testing compute_indicators on 1m...")
    indicators_1m = compute_indicators(ohlcv_1m)
    assert isinstance(indicators_1m, dict), "compute_indicators should return a dict"
    for key in ['ema', 'rsi', 'atr', 'momentum', 'last_close']:
        assert key in indicators_1m, f"Missing key {key} in indicators"
    print("1m indicators:", indicators_1m)

    print("Testing compute_indicators on 5m...")
    indicators_5m = compute_indicators(ohlcv_5m)
    assert isinstance(indicators_5m, dict), "compute_indicators should return a dict"
    for key in ['ema', 'rsi', 'atr', 'momentum', 'last_close']:
        assert key in indicators_5m, f"Missing key {key} in indicators"
    print("5m indicators:", indicators_5m)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_compute_indicators()
