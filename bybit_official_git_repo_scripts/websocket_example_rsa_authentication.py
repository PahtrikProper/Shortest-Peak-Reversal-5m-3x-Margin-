"""
RSA authentication is an alternative way to create your API key.
Learn about RSA authentication here:
https://www.bybit.com/en-US/help-center/bybitHC_Article?id=000001923&language=en_US
"""
from pybit.unified_trading import WebSocket
from time import sleep

# The API key is given to you by Bybit's API management page after inputting
# your RSA public key.
api_key = "xxxxxxxx"
# The API secret is your RSA generated private key. It begins with the line:
# -----BEGIN PRIVATE KEY-----
with open("my_rsa_private_key.pem", "r") as private_key_file:
    api_secret = private_key_file.read()

ws = WebSocket(
    testnet=True,
    channel_type="private",
    rsa_authentication=True,  # <-- Must be True.
    api_key=api_key,
    api_secret=api_secret,
    trace_logging=True,
)

def handle_message(message):
    print(message)

ws.order_stream(
    callback=handle_message
)

while True:
    sleep(1)
