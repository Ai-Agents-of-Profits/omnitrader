import os
import ccxt
from dotenv import load_dotenv

load_dotenv()

SYMBOL = 'CORE/USDT:USDT'
ORDER_SIZE_USD = 10  # Use a small test size

def get_amount(symbol, usd_size):
    exchange = ccxt.bybit({
        'enableRateLimit': True,
        'options': {'defaultType': 'linear'},
        'apiKey': os.getenv('BYBIT_API_KEY'),
        'secret': os.getenv('BYBIT_API_SECRET'),
    })
    exchange.load_markets()
    price = exchange.fetch_ticker(symbol)['last']
    market = exchange.market(symbol)
    amount_precision = int(market['precision']['amount'])
    amount = round(usd_size / price, amount_precision)
    return amount, price

def test_execute_trade_logic(signal: str, entry_price: float, stop_loss: float, take_profit: float, symbol: str = "CORE/USDT:USDT", amount: float = None) -> str:
    api_key = os.getenv("BYBIT_API_KEY")
    api_secret = os.getenv("BYBIT_API_SECRET")
    try:
        # Get order size from environment variable if not provided
        if amount is None:
            env_amount = os.getenv("ORDER_SIZE")
            if not env_amount:
                return "Execution failed: ORDER_SIZE environment variable not set."
            try:
                amount = float(env_amount)
            except Exception:
                return f"Execution failed: ORDER_SIZE environment variable is not a valid float: {env_amount}"
        # Proxy configuration
        exchange_config = {
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "linear"}
        }
        USE_PROXY = os.getenv('USE_PROXY', 'false').lower() == 'true'
        if USE_PROXY:
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

def test_market_order():
    print("Testing market order execution...")
    amount, price = get_amount(SYMBOL, ORDER_SIZE_USD)
    try:
        exchange = ccxt.bybit({
            'enableRateLimit': True,
            'options': {'defaultType': 'linear'},
            'apiKey': os.getenv('BYBIT_API_KEY'),
            'secret': os.getenv('BYBIT_API_SECRET'),
        })
        USE_PROXY = os.getenv('USE_PROXY', 'false').lower() == 'true'
        if USE_PROXY:
            exchange.proxies = {
                'http': 'http://14a72d94fa368:6d4cde2dfa@181.214.172.24:12323/',
                'https': 'http://14a72d94fa368:6d4cde2dfa@181.214.172.24:12323/'
            }
        order = exchange.create_market_order(SYMBOL, 'buy', amount)
        print(f"Market buy order placed: {order.get('id', 'N/A')}")
        close = exchange.create_market_order(SYMBOL, 'sell', amount, params={'reduceOnly': True})
        print("Closed test market position.")
    except Exception as e:
        print(f"Market order test failed: {e}")

def test_limit_order():
    print("Testing limit order execution via test_execute_trade_logic()...")
    amount, price = get_amount(SYMBOL, ORDER_SIZE_USD)
    result = test_execute_trade_logic(
        signal='BUY',
        entry_price=price * 0.99,  # Slightly below market for test
        stop_loss=price * 0.97,
        take_profit=price * 1.03,
        symbol=SYMBOL,
        amount=amount
    )
    print("Limit order result:", result)

def test_sl_tp_only():
    print("Testing SL/TP order placement separately...")
    amount, price = get_amount(SYMBOL, ORDER_SIZE_USD)
    try:
        exchange = ccxt.bybit({
            'enableRateLimit': True,
            'options': {'defaultType': 'linear'},
            'apiKey': os.getenv('BYBIT_API_KEY'),
            'secret': os.getenv('BYBIT_API_SECRET'),
        })
        USE_PROXY = os.getenv('USE_PROXY', 'false').lower() == 'true'
        if USE_PROXY:
            exchange.proxies = {
                'http': 'http://14a72d94fa368:6d4cde2dfa@181.214.172.24:12323/',
                'https': 'http://14a72d94fa368:6d4cde2dfa@181.214.172.24:12323/'
            }
        # Place a market buy to open position
        entry = exchange.create_market_order(SYMBOL, 'buy', amount)
        print(f"Entry order placed: {entry.get('id', 'N/A')}")
        stop_loss_price = price * 0.98
        target_price = price * 1.02
        # Set triggerDirection for TP/SL (long)
        tp_trigger = 1  # TP triggers above for long
        sl_trigger = 2  # SL triggers below for long
        # Place SL
        sl_order = exchange.create_order(
            SYMBOL, 'STOP_MARKET', 'sell', amount, None,
            {
                'stopPrice': stop_loss_price,
                'reduceOnly': True,
                'orderType': 'Market',
                'triggerDirection': sl_trigger
            }
        )
        # Place TP
        tp_order = exchange.create_order(
            SYMBOL, 'TAKE_PROFIT_MARKET', 'sell', amount, None,
            {
                'stopPrice': target_price,
                'reduceOnly': True,
                'orderType': 'Market',
                'triggerDirection': tp_trigger
            }
        )
        print(f"SL order placed: {sl_order.get('id', 'N/A')} at {stop_loss_price}")
        print(f"TP order placed: {tp_order.get('id', 'N/A')} at {target_price}")
        # Cancel SL/TP and close position
        exchange.cancel_order(sl_order['id'], SYMBOL)
        exchange.cancel_order(tp_order['id'], SYMBOL)
        print("Cancelled SL/TP test orders.")
        close = exchange.create_market_order(SYMBOL, 'sell', amount, params={'reduceOnly': True})
        print("Closed test position.")
    except Exception as e:
        print(f"SL/TP test failed: {e}")

if __name__ == '__main__':
    test_market_order()
    test_limit_order()
    test_sl_tp_only()
