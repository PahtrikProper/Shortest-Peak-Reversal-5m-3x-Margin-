from pybit.unified_trading import HTTP


BYBIT_API_KEY = "api_key"
BYBIT_API_SECRET = "api_secret"
TESTNET = True  # True means your API keys were generated on testnet.bybit.com


# Create direct HTTP session instance

session = HTTP(
    api_key=BYBIT_API_KEY,
    api_secret=BYBIT_API_SECRET,
    testnet=TESTNET,
)

# Place order

response = session.place_order(
    category="spot",
    symbol="ETHUSDT",
    side="Sell",
    orderType="Market",
    qty="0.1",
    timeInForce="GTC",
)

# Example to cancel orders

response = session.get_open_orders(
    category="linear",
    symbol="BTCUSDT",
)

orders = response["result"]["list"]

for order in orders:
    if order["orderStatus"] == "Untriggered":
        session.cancel_order(
            category="linear",
            symbol=order["symbol"],
            orderId=order["orderId"],
        )


# Batch cancel orders

orders_to_cancel = [
    {"category": "option", "symbol": o["symbol"], "orderId": o["orderId"]}
    for o in response["result"]["list"]
    if o["orderStatus"] == "New"
]

response = session.cancel_batch_order(
    category="option",
    request=orders_to_cancel,
)
