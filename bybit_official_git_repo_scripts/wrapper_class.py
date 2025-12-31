from pybit.unified_trading import HTTP


BYBIT_API_KEY = "api_key"
BYBIT_API_SECRET = "api_secret"
TESTNET = True  # True means your API keys were generated on testnet.bybit.com


class BybitWrapper:
    def __init__(
        self,
        api_key: str = None,
        api_secret: str = None,
        testnet: bool = None,
    ):
        self.instance = HTTP(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
            log_requests=True,
        )

    def get_max_leverage(self, category: str, symbol: str):
        """
        Get max leverage for symbol in category
        """
        symbols = self.instance.get_instruments_info(category=category)
        result = symbols["result"]["list"]
        return [d for d in result if d["symbol"] == symbol][0][
            "leverageFilter"
        ]["maxLeverage"]

    def get_kline_data(self, symbol: str = "BTCUSDT"):
        kline_data = self.instance.get_kline(
            category="linear",
            symbol=symbol,
            interval=60,
        )["result"]

        # Getting 0 element from list
        data_list = kline_data["list"][0]

        print(f"Open price: {data_list[1]}")
        print(f"High price: {data_list[2]}")
        print(f"Low price: {data_list[3]}")
        print(f"Close price: {data_list[4]}")

    def cancel_all_orders(
        self,
        category: str = "spot",
        symbol: str = "ETHUSDT",
    ) -> dict:
        """
        Cancel orders by category and symbol
        """
        return self.instance.cancel_all_orders(
            category=category, symbol=symbol
        )

    def get_realtime_orders(
        self,
        category: str,
        symbol: str = None,
    ) -> dict:
        """
        Get realtime orders
        """
        return self.instance.get_open_orders(
            category=category,
            symbol=symbol,
        )

    def get_order_history(self, **kwargs) -> dict:
        return self.instance.get_order_history(**kwargs)["result"]["list"]


# Initialize wrapper instance

wrapper = BybitWrapper(
    api_key=BYBIT_API_KEY,
    api_secret=BYBIT_API_SECRET,
    testnet=TESTNET,
)

# Actual usage
response = wrapper.get_realtime_orders(category="linear", symbol="ETHUSDT")
