import os
from dotenv import load_dotenv
load_dotenv()
from agents import Agent, Runner, function_tool
from timescaledb_tools import get_latest_indicators
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX
import ccxt
import asyncio
import time

# Execution Agent
@function_tool
def execute_trade(
    signal: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    symbol: str,
    amount: float
) -> str:
    try:
        # Provide defaults internally if needed
        if not symbol:
            symbol = "CORE/USDT:USDT"
        if not amount:
            amount = float(os.getenv("ORDER_SIZE", 1))
        api_key = os.getenv("BYBIT_API_KEY")
        api_secret = os.getenv("BYBIT_API_SECRET")
        exchange_config = {
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "future"}
        }
        USE_PROXY = os.getenv('USE_PROXY', 'false').lower() == 'true'
        if USE_PROXY:
            # Use the same proxy settings as in fetch_core_5m.py
            exchange_config['proxies'] = {
                'http': 'http://14a72d94fa368:6d4cde2dfa@181.214.172.24:12323/',
                'https': 'http://14a72d94fa368:6d4cde2dfa@181.214.172.24:12323/'
            }
        exchange = ccxt.bybit(exchange_config)
        side = "buy" if signal == "BUY" else "sell"
        # Place a LIMIT order at entry_price
        order = exchange.create_order(symbol, "limit", side, amount, entry_price)
        results = [f"Limit order placed: {order['id']} at {entry_price}"]
        position_side = "sell" if side == "buy" else "buy"
        # Set triggerDirection for TP/SL
        if side == "buy":
            tp_trigger = 1  # TP triggers above for long
            sl_trigger = 2  # SL triggers below for long
        else:
            tp_trigger = 2  # TP triggers below for short
            sl_trigger = 1  # SL triggers above for short
        # Place Take Profit (TP) order
        try:
            tp_order = exchange.create_order(
                symbol,
                "TAKE_PROFIT_MARKET",
                position_side,
                amount,
                None,
                {
                    "stopPrice": take_profit,
                    "reduceOnly": True,
                    "triggerDirection": tp_trigger,
                    "category": "linear",
                    "orderType": "Market",
                    "triggerBy": "MarkPrice"
                }
            )
            results.append(f"Take Profit order placed: {tp_order['id']} at {take_profit}")
        except Exception as e:
            results.append(f"TP order error: {str(e)}")
        # Place Stop Loss (SL) order
        try:
            sl_order = exchange.create_order(
                symbol,
                "STOP_MARKET",
                position_side,
                amount,
                None,
                {
                    "stopPrice": stop_loss,
                    "reduceOnly": True,
                    "triggerDirection": sl_trigger,
                    "category": "linear",
                    "orderType": "Market",
                    "triggerBy": "MarkPrice"
                }
            )
            results.append(f"Stop Loss order placed: {sl_order['id']} at {stop_loss}")
        except Exception as e:
            results.append(f"SL order error: {str(e)}")
        return " | ".join(results)
    except Exception as e:
        return f"Execution failed: {str(e)}"

# Sub-agent: Technical Analyst
technical_analyst = Agent(
    name="TechnicalAnalyst",
   instructions = (
    "### ROLE\n"
    "You are **TechnicalAnalyst-v2.1**, an institutional-grade signal engine. "
    "Emit exactly one actionable signal (BUY, SELL, or WAIT) for CORE/USDT:USDT.\n\n"

    "### DATA ACCESS\n"
    "When asked, call **get_latest_indicators** with the mandatory timeframes: '1m', '5m', '15m'.\n"
    "Returned fields (per timeframe): EMA, SMA, fast EMA, slow EMA, EMA cross, EMA slope, RSI, ATR, ATR %, "
    "MACD, MACD signal, MACD histogram, Bollinger Bands (upper/mid/lower/width), Stochastic %K/%D, ADX, ADX slope, "
    "CCI, OBV, OBV slope, VWAP, momentum, last close, swing high/low, volume avg, volume spike, timestamp, "
    "candle pattern, nearUpperBand flag.\n\n"

    "### DECISION LOGIC\n"
    "1️⃣ **Primary Trend Filter** – 15 m & 5 m must match\n"
    "   • Bull = EMA > SMA **and** EMA slope > 0 **and** MACD hist > 0 **and** ADX ≥ 20.\n"
    "   • Bear = inverse.\n"
    "   • If states differ ⇒ **WAIT**.\n\n"

    "2️⃣ **Entry Timing (1 m window ≤ 2 candles)**\n"
    "   • BUY: price tags lower BB **or** fast EMA crosses above slow EMA ≤ 2 candles ago while RSI < 45.\n"
    "   • SELL: price tags upper BB **or** fast EMA crosses below slow EMA ≤ 2 candles ago while RSI > 55.\n"
    "   • Confirm Stoch %K/%D cross in same direction within last 3 candles.\n\n"

    "3️⃣ **Volume & Order-Flow**\n"
    "   • OBV slope must agree with signal and VWAP distance ≤ 0.5 %.\n"
    "   • If OBV diverges **and** ADX < 25 ⇒ downgrade; if ADX ≥ 25, subtract only half penalty.\n\n"

    "4️⃣ **Risk Management**\n"
    "   • stop_loss.level = entry_price ± 1.5 × ATR(15 m).\n"
    "   • take_profit.level = entry_price ± min(2 × ATR(15 m), distance to nearest BB).\n"
    "   • Include concise rationale citing exact values.\n\n"

    "5️⃣ **Confidence Scoring (deterministic)**\n"
    "   • Start at **55**.\n"
    "   • **+8** for each confirming element: (trend match, EMA slope sign, MACD hist sign, OBV slope alignment, "
    "Stoch confirmation).\n"
    "   • **−5** per conflict: low ADX (<20), OBV divergence, RSI neutral 45-55, candle pattern contradiction.\n"
    "   • Clamp 0-100.\n"
    "   • Map: **High ≥ 75**, **Medium 45-74**, **Low < 45**. Numeric score **must** match label.\n\n"

    "### OUTPUT RULES\n"
    "• **STRICT RAW JSON** (no markdown, no code fence). Float precision ≤ 4 decimals.\n"
    "• Schema:\n"
    "{\n"
    "  'signal'        : 'BUY'|'SELL'|'WAIT',\n"
    "  'confidence'    : 'High'|'Medium'|'Low',\n"
    "  'confidence_score': int 0-100,\n"
    "  'entry_price'   : number|null,\n"
    "  'stop_loss'     : {'level': number, 'rationale': str}|null,\n"
    "  'take_profit'   : {'level': number, 'rationale': str}|null,\n"
    "  'reasoning'     : str\n"
    "}\n"
    "• For **WAIT**, only signal, confidence, confidence_score, reasoning (others = null).\n\n"

    "### EXECUTION\n"
    "If signal ≠ WAIT, immediately call **execute_trade** with "
    "signal, entry_price, stop_loss.level, take_profit.level, symbol, amount, "
    "and append the broker response to reasoning."
)
,
    tools=[get_latest_indicators, execute_trade],
    model="gpt-4.1"
)

# Main agent
main_agent = Agent(
    name="TradeDecisionAgent",
    instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
STRICT OUTPUT: Raw JSON only (no markdown, no code fences).
Think silently; do NOT reveal chain-of-thought.

Tool usage rules:
• Call the handoff to TechnicalAnalyst exactly once, and only after you have determined which indicator timeframes are needed.
• If get_latest_indicators fails, respond with signal="WAIT" and explain the failure in the reasoning field.

You are a trading decision coordination agent tasked with producing actionable signals for CORE/USDT:USDT using multi‑timeframe technical analysis.

Handoff to TechnicalAnalyst to generate the trading decision.
""",
    handoffs=[technical_analyst],
    model="gpt-4.1"
)

def get_current_position(symbol="CORE/USDT:USDT"):
    """
    Returns True if there is an open position (long or short) on Bybit for the given symbol.
    """
    api_key = os.getenv("BYBIT_API_KEY")
    api_secret = os.getenv("BYBIT_API_SECRET")
    exchange_config = {
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
        'options': {'defaultType': 'linear'},
    }
    exchange = ccxt.bybit(exchange_config)
    try:
        positions = exchange.fetch_positions([symbol])
        for pos in positions:
            size = pos.get('contracts') or pos.get('size', 0)
            if abs(float(size)) > 0:
                return True  # In position
    except Exception as e:
        print(f"Error checking position: {e}")
        # Fail-safe: if cannot check, assume in position to avoid duplicate signals
        return True
    return False  # No open position

INTERVAL_SECONDS = 60  # Run every 60 seconds

async def periodic_agent_run():
    while True:
        if not get_current_position():
            result = await Runner.run(main_agent, input="Analyze CORE/USDT:USDT and provide a unified trading decision using 1m, 5m, and 15m timeframes.")
            print(result.final_output)
        else:
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | In position – skipping signal generation.")
        await asyncio.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    asyncio.run(periodic_agent_run())
