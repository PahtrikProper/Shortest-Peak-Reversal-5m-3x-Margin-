from pybit.unified_trading import WebSocket
from pybit.unified_trading import WebsocketSpreadTrading
from pybit.unified_trading import SpreadHTTP
from time import sleep


# The public websocket for spread trading
ws = WebsocketSpreadTrading(
    testnet=True,
    trace_logging=True,
)

# The private websocket for spread trading (same connection as normal)
ws_private = WebSocket(
    testnet=True,
    trace_logging=True,
    channel_type="private",
    api_key="xxxxxxxxxxxxxxxxxx",
    api_secret="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
)

def handle_message(message):
    print(message)

ws.orderbook_stream(25, "SOLUSDT_SOL/USDT", handle_message)
ws.trade_stream("SOLUSDT_SOL/USDT", handle_message)
ws.ticker_stream("SOLUSDT_SOL/USDT", handle_message)

ws_private.spread_order_stream(handle_message)
ws_private.spread_execution_stream(handle_message)


session = SpreadHTTP(
    testnet=True,
    api_key="xxxxxxxxxxxxxxxxxx",
    api_secret="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
)

symbol = "BTCUSDT_BTC/USDT"
print(session.get_instruments_info(symbol=symbol))
print(session.place_order(
    symbol=symbol,
    side="Buy",
    orderType="Market",
    qty="0.001",
))


while True:
    sleep(1)