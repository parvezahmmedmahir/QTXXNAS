import sys
import os

# 1. Add current directory to sys.path so Python can find app.py
sys.path.insert(0, os.path.dirname(__file__))

# 2. Import the Flask 'app' object
# 'application' is the standard variable name Passenger looks for
from app import app as application

# 3. Optional: Set Environment Variables specifically for cPanel
# You can also set these in the cPanel "Setup Python App" dashboard
os.environ["RENDER"] = "false"  # We are NOT on Render anymore
os.environ["PORT"] = "8080"     # Internal port, cPanel handles the rest
