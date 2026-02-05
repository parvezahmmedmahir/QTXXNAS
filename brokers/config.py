# ⚠️ IMPORTANT: CONFIGURE YOUR BROKER CREDENTIALS HERE
# Without valid credentials, the system runs in SIMULATION MODE (50% accuracy)

import os

BROKER_CONFIG = {
    "QUOTEX": {
        # Get these from your Quotex account
        "email": os.getenv("QUOTEX_EMAIL", "immahir01@gmail.com"),
        "password": os.getenv("QUOTEX_PASSWORD", "MAHIR1122"),
        "live_account": True  # False = Practice, True = Real Money
    },
    "IQOPTION": {
        # Get these from your IQ Option account
        "email": "",  # Example: "your_email@gmail.com"
        "password": "",  # Your IQ Option password
        "live_account": False  # RECOMMENDED: Start with Practice (False)
    },
    "POCKETOPTION": {
        # User Provided Credentials (Note: PO usually requires SSID)
        "email": "ffbd8404@gmail.com",
        "password": "wXyFiAf2",
        "ssid": "",  # Still might be needed for websocket if API requires it
        "platform_url": "wss://api-fin.pocketoption.com/socket.io/?EIO=3&transport=websocket"
    },
    "BINOLLA": {
        # ADVANCED: Requires API token from Binolla dashboard
        "token": "",  # Get from Binolla API settings
        "platform_url": "wss://binolla.com/api/v1/socket"
    }
}

# HOW TO GET YOUR CREDENTIALS:
# 1. QUOTEX/IQ OPTION: Simply use your login email and password
# 2. POCKETOPTION: Follow browser cookie extraction steps above
# 3. BINOLLA: Generate API token from your account settings

# SECURITY WARNING:
# - Never share this file publicly
# - Use environment variables in production
# - Start with PRACTICE accounts first
