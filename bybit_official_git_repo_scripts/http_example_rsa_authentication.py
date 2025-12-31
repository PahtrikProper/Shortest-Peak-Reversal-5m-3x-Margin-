"""
RSA authentication is an alternative way to create your API key.
Learn about RSA authentication here:
https://www.bybit.com/en-US/help-center/bybitHC_Article?id=000001923&language=en_US
"""
from pybit.unified_trading import HTTP

# The API key is given to you by Bybit's API management page after inputting
# your RSA public key.
api_key = "xxxxxxx"
# The API secret is your RSA generated private key. It begins with the line:
# -----BEGIN PRIVATE KEY-----
with open("my_rsa_private_key.pem", "r") as private_key_file:
    api_secret = private_key_file.read()

session = HTTP(
    testnet=True,
    rsa_authentication=True,  # <-- Must be True.
    api_key=api_key,
    api_secret=api_secret,
    log_requests=True,
)

print(session.get_positions(category="linear", symbol="BTCUSDT"))


