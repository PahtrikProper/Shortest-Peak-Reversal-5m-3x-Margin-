from pybit.unified_trading import WebSocket
from time import sleep

ws = WebSocket(
    testnet=True,
    channel_type="linear",
)

def handle_message(message):
    print(message)

ws.orderbook_stream(50, "BTCUSDT", handle_message)

while True:
    sleep(1)
