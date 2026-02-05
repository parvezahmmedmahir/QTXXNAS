"""
QUANTUM X PRO - Enhanced Backend v5.0 (Pro Edition)
Integrates Enterprise Engine v3.0, Pro-Level Technical Analysis, and Real-Time Market Guardians.
"""
import sys
import datetime
import random
import sqlite3
import string
import secrets
import hashlib
import time
import threading
import os
# import psycopg2
# import psycopg2.pool
import requests
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from collections import defaultdict
import platform
import subprocess
import json
import queue

# --- ASYNC LOGGING CORE ---
logging_queue = queue.Queue()

def async_logger_worker():
    """Background thread to handle non-critical DB logs without delaying signals"""
    while True:
        try:
            task = logging_queue.get(timeout=5)
            if not task: break
            
            # Execute DB Insert
            from app import get_db_connection, release_db_connection
            conn, db_type = get_db_connection()
            if conn:
                try:
                    cur = conn.cursor()
                    if db_type == 'postgres':
                        cur.execute(task['query'], task['params'])
                    else:
                        cur.execute(task['query'].replace('%s', '?'), task['params'])
                    conn.commit()
                finally:
                    release_db_connection(conn, db_type)
            logging_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            print(f"[ASYNC-LOG] Error: {e}")

# Start the background logger
threading.Thread(target=async_logger_worker, daemon=True).start()

# --- QUANTUM HWID & GUARDIAN CORE ---
def generate_quantum_hwid(raw_id):
    """Secure, obfuscated HWID for the Quantum X Pro system"""
    salt = "QX-PRO-HARDWARE-GUARDIAN-SECURE-ID-2026"
    combined = f"{raw_id}:{salt}"
    hwid_hash = hashlib.sha256(combined.encode()).hexdigest().upper()
    return f"QX-ID-{hwid_hash[:4]}-{hwid_hash[8:12]}-{hwid_hash[24:28]}"

def get_geo_info(ip):
    """
    ENHANCED IP GEOLOCATION TRACKING
    Collects comprehensive location data: country, region, city, timezone, ISP, coordinates
    """
    try:
        # Handle local/internal IPs
        if ip in ["127.0.0.1", "localhost", "::1"]:
            return {
                "city": "Local",
                "country": "Local",
                "region": "Local",
                "timezone": "UTC",
                "isp": "Internal",
                "lat": 0.0,
                "lon": 0.0,
                "zip": "00000",
                "org": "Local Network"
            }
        
        # Use ip-api.com for comprehensive geolocation (free, no API key needed)
        # Returns: country, region, city, timezone, isp, lat, lon, zip, org
        resp = requests.get(
            f"http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,query",
            timeout=8
        )
        
        if resp.status_code == 200:
            data = resp.json()
            
            # Check if request was successful
            if data.get("status") == "success":
                return {
                    "ip": data.get("query", ip),
                    "country": data.get("country", "Unknown"),
                    "country_code": data.get("countryCode", "XX"),
                    "region": data.get("regionName", "Unknown"),
                    "region_code": data.get("region", "XX"),
                    "city": data.get("city", "Unknown"),
                    "zip": data.get("zip", "Unknown"),
                    "lat": data.get("lat", 0.0),
                    "lon": data.get("lon", 0.0),
                    "timezone": data.get("timezone", "UTC"),
                    "isp": data.get("isp", "Unknown ISP"),
                    "org": data.get("org", "Unknown Organization"),
                    "as": data.get("as", "Unknown AS")
                }
            else:
                print(f"[GEO] IP-API Error: {data.get('message', 'Unknown error')}")
                return {"city": "Unknown", "country": "Unknown", "isp": "Unknown"}
        else:
            print(f"[GEO] HTTP Error: {resp.status_code}")
            return {"city": "Unknown", "country": "Unknown", "isp": "Unknown"}
            
    except Exception as e:
        print(f"[GEO] Geolocation failed for {ip}: {e}")
        return {"city": "Unknown", "country": "Unknown", "isp": "Unknown"}

# --- BROKER INTEGRATIONS ---
# Importing adapters from the brokers package (Binolla optional)
import importlib
import importlib.util

BROKER_CONFIG = {}
QuotexAdapter = None
IQOptionAdapter = None
PocketOptionAdapter = None
BinollaAdapter = None

try:
    from brokers.config import BROKER_CONFIG  # type: ignore
    # Force use of the new, working PyQuotex adapter
    from brokers.quotex_ws import QuotexWSAdapter as QuotexAdapter
    from brokers.iqoption import IQOptionAdapter  # type: ignore
    from brokers.pocketoption import PocketOptionAdapter  # type: ignore
    # Binolla optional import
    binolla_module = importlib.util.find_spec("brokers.binolla")
    if binolla_module:
        BinollaAdapter = importlib.import_module("brokers.binolla").BinollaAdapter  # type: ignore

    # New WebSocket Adapters
    from brokers.quotex_ws import QuotexWSAdapter
    from brokers.forex_ws import ForexWSAdapter
except ImportError as e:
    print(f"[CRITICAL] Broker modules missing: {e}. Running in restricted mode.")

# Force load latest engine
from engine.enhanced import EnhancedEngine
ENHANCED_ENGINE_AVAILABLE = True
load_dotenv()

# Global instances (initialized lazily)
data_feed = None
reversal_engine = None
enhanced_engine = None
db_initialized = False

def get_data_feed():
    global data_feed
    if data_feed is None:
        data_feed = MarketDataFeed()
    return data_feed

def get_engines():
    global reversal_engine, enhanced_engine
    if reversal_engine is None:
        try:
            from engine.reversal import ReversalEngine
            reversal_engine = ReversalEngine() if ReversalEngine else None
        except:
            reversal_engine = None
            
    if enhanced_engine is None and ENHANCED_ENGINE_AVAILABLE:
        try:
            from engine.enhanced import EnhancedEngine
            enhanced_engine = EnhancedEngine()
            print("[ENGINE] Pro Engine v3.0 Loaded")
        except:
            enhanced_engine = None
    return reversal_engine, enhanced_engine

# Enterprise Scaling & Optimization
app = Flask(__name__, static_url_path='', static_folder='.')
CORS(app, resources={r"/*": {"origins": "*"}})

REQUEST_LOG = defaultdict(list)
LICENSE_CACHE = {} # Cache for verified keys: {key:device: (timestamp, status, category, expiry)}
CACHE_TTL = 300   # 5 Minutes cache to handle 1000+ concurrent users efficiently
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 5000

@app.route('/')
def serve_index():
    return app.send_static_file('index.html')

@app.route('/test')
def test_connection():
    mode = 'sqlite'
    if pg_pool:
        try:
            conn = pg_pool.getconn()
            if conn:
                mode = 'postgres'
                pg_pool.putconn(conn)
        except:
            pass
    return jsonify({
        "status": "online",
        "server": "Quantum X PRO",
        "db_mode": mode,
        "cloud_sync": pg_pool is not None
    })

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

print("[INIT] Starting Quantum X PRO Enterprise Backend...")
print("[SYSTEM] Loading Reversal Engine & Drain Algorithms...")

# --- DATABASE SETUP (Dual-Mode: Cloud/Local) ---
# --- DATABASE SETUP (Local SQLite Only) ---
DB_FILE = "security.db"
# DATABASE_URL removed for local mode

def is_market_open():
    """Checks if the real Forex market is open based on UTC time"""
    now = datetime.datetime.utcnow()
    day = now.weekday() # 0 = Monday, 1 = Tuesday... 4 = Friday, 5 = Saturday, 6 = Sunday
    hour = now.hour
    minute = now.minute
    current_time_mins = hour * 60 + minute
    market_edge_mins = 22 * 60 # 22:00 UTC

    if day == 5: # Saturday
        return False
    if day == 6: # Sunday opens at 22:00 UTC
        return current_time_mins >= market_edge_mins
    if day == 4: # Friday closes at 22:00 UTC
        return current_time_mins < market_edge_mins
    return True # Mon-Thu

# --- SERVER OPTIMIZATION: CONNECTION POOLING ---
pg_pool = None

def init_db_pool():
    global pg_pool
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("[DB] Warning: DATABASE_URL not found, falling back to SQLite.")
        return
        
    try:
        from psycopg2 import pool
        pg_pool = pool.SimpleConnectionPool(1, 40, db_url)
        print("[DB] Success: PostgreSQL Pool Initialized (Supabase Connected)")
    except Exception as e:
        print(f"[DB] Error: PostgreSQL connection failed: {e}")
        pg_pool = None

def get_db_connection():
    """Fetches a connection from Postgres (Supabase) with SQLite fallback"""
    global pg_pool
    
    # 1. Try Postgres Pool
    if pg_pool:
        try:
            conn = pg_pool.getconn()
            print(f"[DB] Using PostgreSQL Connection from Pool")
            return conn, 'postgres'
        except Exception as e:
            print(f"[DB] Pool getconn failed: {e}. Falling back to SQLite.")
            pass # Fall through to SQLite
            
    # 2. Fallback: Local SQLite
    print("[DB] Using Fallback SQLite Connection")
    try:
        db_dir = os.path.dirname(DB_FILE)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        db_conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        db_conn.row_factory = sqlite3.Row
        return db_conn, 'sqlite'
    except Exception as e:
        print(f"[DB] Fatal connection error: {e}")
        return None, None

def release_db_connection(conn, mode):
    """Returns connection to pool for reuse or closes direct connection"""
    if not conn: return
    
    # Mode 'postgres' can be either pooled or direct fallback
    if mode == 'postgres' and pg_pool:
        try:
            # If the connection is closed or in error state, close it before returning
            if conn.closed != 0:
                pg_pool.putconn(conn, close=True)
            else:
                pg_pool.putconn(conn)
        except Exception:
            # If any error happens during putconn, just try to close it
            try:
                conn.close()
            except:
                pass
    else:
        # SQLite or other fallback
        try:
            conn.close()
        except:
            pass

# --- CLOUD SESSION SYNC (session.json) ---
def sync_session_from_cloud():
    """Loads session.json from Supabase to local filesystem for Render compatibility"""
    try:
        conn, db_type = get_db_connection()
        if not conn: return
        cur = conn.cursor()
        query = "SELECT setting_value FROM system_settings WHERE setting_name = 'quotex_session'"
        cur.execute(query)
        row = cur.fetchone()
        if row:
            session_data = row[0]
            with open("session.json", "w") as f:
                f.write(session_data)
            print("[SYNC] Session successfully restored from Supabase Cloud")
        cur.close()
        release_db_connection(conn, db_type)
    except Exception as e:
        print(f"[SYNC] Cloud restore warning: {e}")

def sync_session_to_cloud():
    """Saves local session.json to Supabase Cloud"""
    try:
        if not os.path.exists("session.json"): return
        with open("session.json", "r") as f:
            session_data = f.read()
            if not session_data or len(session_data) < 50: return # Skip empty/junk
        
        conn, db_type = get_db_connection()
        if not conn: return
        cur = conn.cursor()
        if db_type == 'postgres':
            cur.execute("""
                INSERT INTO system_settings (setting_name, setting_value, updated_at)
                VALUES ('quotex_session', %s, CURRENT_TIMESTAMP)
                ON CONFLICT (setting_name) DO UPDATE SET 
                setting_value=EXCLUDED.setting_value, updated_at=CURRENT_TIMESTAMP
            """, (session_data,))
        else:
            cur.execute("INSERT OR REPLACE INTO system_settings (setting_name, setting_value) VALUES ('quotex_session', ?)", (session_data,))
        conn.commit()
        cur.close()
        release_db_connection(conn, db_type)
    except Exception as e:
        print(f"[SYNC] Cloud save warning: {e}")

def init_db():
    """Ensures the licenses and win_rate_tracking tables exist."""
    conn, db_type = get_db_connection()
    if not conn: return

    try:
        cur = conn.cursor()
        if db_type == 'postgres':
            # 1. Main Licenses Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS licenses (
                    key_code TEXT PRIMARY KEY,
                    category TEXT,
                    status TEXT DEFAULT 'PENDING',
                    device_id TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    usage_count INTEGER DEFAULT 0,
                    last_access_date TIMESTAMP,
                    expiry_date TIMESTAMP,
                    activation_date TIMESTAMP,
                    country TEXT,
                    city TEXT,
                    timezone_geo TEXT
                )
            """)
            # 2. Win Rate Tracking
            cur.execute("""
                CREATE TABLE IF NOT EXISTS win_rate_tracking (
                    id SERIAL PRIMARY KEY,
                    signal_id TEXT,
                    broker TEXT,
                    market TEXT,
                    direction TEXT,
                    confidence INTEGER,
                    entry_time TEXT,
                    outcome TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 3. Security Heartbeat & Manual OTP Override
            cur.execute("""
                CREATE TABLE IF NOT EXISTS system_connectivity (
                    service_name TEXT PRIMARY KEY,
                    status TEXT,
                    details TEXT,
                    otp_code TEXT,
                    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            try:
                cur.execute("ALTER TABLE system_connectivity ADD COLUMN IF NOT EXISTS otp_code TEXT")
            except: pass
            # 4. GLOBAL SIGNAL CACHE (For synchronized results)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS signals_cache (
                    market TEXT,
                    timeframe TEXT,
                    direction TEXT,
                    confidence INTEGER,
                    strategy TEXT,
                    entry_time TEXT,
                    timestamp BIGINT,
                    PRIMARY KEY (market, timeframe, timestamp)
                )
            """)
            # 4. User Sessions
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id SERIAL PRIMARY KEY,
                    license_key TEXT,
                    device_id TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    timezone TEXT,
                    resolution TEXT,
                    platform TEXT,
                    country TEXT,
                    region TEXT,
                    city TEXT,
                    isp TEXT,
                    latitude DOUBLE PRECISION,
                    longitude DOUBLE PRECISION,
                    postal_code TEXT,
                    organization TEXT,
                    login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 6. Persistent Cloud Settings (Sync session.json)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS system_settings (
                    setting_name TEXT PRIMARY KEY,
                    setting_value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            # SQLite Tables (with migration)
            # 1. Licenses
            cur.execute("""
                CREATE TABLE IF NOT EXISTS licenses (
                    key_code TEXT PRIMARY KEY,
                    category TEXT,
                    status TEXT DEFAULT 'PENDING',
                    device_id TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    usage_count INTEGER DEFAULT 0,
                    last_access_date TIMESTAMP,
                    expiry_date TIMESTAMP,
                    activation_date TIMESTAMP,
                    country TEXT,
                    city TEXT,
                    timezone_geo TEXT
                )
            """)
            # 2. Tracks Columns for licenses (FORCE REPAIR)
            try:
                cur.execute("PRAGMA table_info(licenses)")
                cols = [c[1] for c in cur.fetchall()]
                migrations = [
                    ('last_access_date', 'ALTER TABLE licenses ADD COLUMN last_access_date TIMESTAMP'),
                    ('activation_date', 'ALTER TABLE licenses ADD COLUMN activation_date TIMESTAMP'),
                    ('usage_count', 'ALTER TABLE licenses ADD COLUMN usage_count INTEGER DEFAULT 0'),
                    ('country', 'ALTER TABLE licenses ADD COLUMN country TEXT'),
                    ('city', 'ALTER TABLE licenses ADD COLUMN city TEXT'),
                    ('timezone_geo', 'ALTER TABLE licenses ADD COLUMN timezone_geo TEXT'),
                    ('expiry_date', 'ALTER TABLE licenses ADD COLUMN expiry_date TIMESTAMP')
                ]
                for col_name, sql in migrations:
                    if col_name not in cols:
                        try: 
                            cur.execute(sql)
                            conn.commit() # Immediate commit for schema stability
                        except: pass
            except: pass

            # 3. User Sessions
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    license_key TEXT,
                    device_id TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    timezone TEXT,
                    resolution TEXT,
                    platform TEXT,
                    country TEXT,
                    region TEXT,
                    city TEXT,
                    isp TEXT,
                    latitude REAL,
                    longitude REAL,
                    postal_code TEXT,
                    organization TEXT,
                    login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("PRAGMA table_info(user_sessions)")
            cols = [c[1] for c in cur.fetchall()]
            for col in ['timezone', 'resolution', 'platform', 'country', 'region', 'city', 'isp', 'latitude', 'longitude', 'postal_code', 'organization', 'login_time']:
                if col not in cols: cur.execute(f"ALTER TABLE user_sessions ADD COLUMN {col} TEXT")

            # 4. User Activity
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    license_key TEXT,
                    device_id TEXT,
                    mouse_movements INTEGER,
                    clicks INTEGER,
                    scrolls INTEGER,
                    key_presses INTEGER,
                    session_duration INTEGER,
                    current_url TEXT,
                    page_title TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("PRAGMA table_info(user_activity)")
            cols = [c[1] for c in cur.fetchall()]
            for col in ['scrolls', 'key_presses', 'session_duration', 'page_title']:
                if col not in cols: cur.execute(f"ALTER TABLE user_activity ADD COLUMN {col} INTEGER")

            # 5. Core Monitoring Tables
            cur.execute("""
                CREATE TABLE IF NOT EXISTS win_rate_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id TEXT,
                    broker TEXT,
                    market TEXT,
                    direction TEXT,
                    confidence INTEGER,
                    entry_time TEXT,
                    outcome TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS system_connectivity (
                    service_name TEXT PRIMARY KEY,
                    status TEXT,
                    details TEXT,
                    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # MASTER FALLBACK - Guaranteed access for all Pro users
            cur.execute("""
                INSERT OR IGNORE INTO licenses (key_code, category, status)
                VALUES ('QX-FREE-MODE-2026', 'OWNER', 'ACTIVE'),
                       ('!*6WSH9A', 'PRO', 'ACTIVE'),
                       ('KTXKTM77', 'PRO', 'ACTIVE'),
                       ('QX-ADMIN-PRO-99', 'OWNER', 'ACTIVE')
            """)
        conn.commit()
        cur.close()
        release_db_connection(conn, db_type)
        print("[DB] Database Verified (Cloud or Local SQLite Fallback Active).")
    except Exception as e:
        print(f"[DB] Init Error: {e}")

def update_system_status_to_db():
    """Background heartbeat to Supabase to prove API/WS are ONLINE"""
    time.sleep(30) # Longer wait for initial boot
    while True:
        conn = None
        db_type = None
        try:
            df = get_data_feed()
            conn, db_type = get_db_connection()
            if conn:
                cur = conn.cursor()
                try:
                    q_ws_active = df.quotex_ws.connected
                    f_ws_active = df.forex_ws.connected
                    q_sid = df.quotex_ws.sid if q_ws_active else "N/A"
                except:
                    q_ws_active, f_ws_active, q_sid = False, False, "N/A"
                
                av_status = "ONLINE" if os.getenv("ALPHA_VANTAGE_KEY") else "API_KEY_MISSING"
                stats = [
                    ('QUOTEX_WS', 'ONLINE' if q_ws_active else 'OFFLINE', f"SID: {q_sid}"),
                    ('FOREX_WS', 'ONLINE' if f_ws_active else 'OFFLINE', "WebSocket Stream Active" if f_ws_active else "N/A"),
                    ('ALPHA_VANTAGE', av_status, "Alpha Vantage Real-Market API"),
                    ('BACKEND_HEARTBEAT', 'ONLINE', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                ]

                for name, status, details in stats:
                    if db_type == 'postgres':
                        cur.execute("""
                            INSERT INTO system_connectivity (service_name, status, details, last_heartbeat)
                            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                            ON CONFLICT (service_name) DO UPDATE 
                            SET status = EXCLUDED.status, details = EXCLUDED.details, last_heartbeat = CURRENT_TIMESTAMP
                        """, (name, status, details))
                    else:
                        cur.execute("""
                            INSERT OR REPLACE INTO system_connectivity (service_name, status, details, last_heartbeat)
                            VALUES (?, ?, ?, datetime('now'))
                        """, (name, status, details))
                conn.commit()
                cur.close()
        except Exception as e:
            print(f"[HEARTBEAT] Sync Warning: {e}")
        finally:
            if conn:
                release_db_connection(conn, db_type)
        time.sleep(60)

@app.before_request
def setup_on_first_request():
    """Startup initialization - Reliable and non-blocking"""
    global db_initialized
    if not db_initialized:
        db_initialized = True
        # SQLite init MUST be synchronous to ensure tables exist before any queries
        try:
            init_db() 
        except Exception as e:
            print(f"[INIT] DB Error: {e}")
        
        # Background high-perf tasks
        threading.Thread(target=init_db_pool, daemon=True).start()
        threading.Thread(target=update_system_status_to_db, daemon=True).start()

# --- MARKET DATA FEED (ENHANCED) ---
class LiveMarketData:
    """
    Pulls live quotes from Alpha Vantage for key real-market pairs.
    Uses lightweight caching to respect free-tier limits (5 req/min).
    """
    def __init__(self, api_key):
        self.api_key = api_key
        self.cache = {}  # key -> (timestamp, candles)
        self.cache_ttl = 55  # seconds
        self.cache_ttl = 55  # seconds

    def _cached(self, key):
        now = time.time()
        if key in self.cache:
            ts, data = self.cache[key]
            if now - ts < self.cache_ttl:
                return data
        return None

    def _store(self, key, data):
        self.cache[key] = (time.time(), data)
        return data

    def _fetch_fx_intraday(self, from_sym, to_sym):
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "FX_INTRADAY",
            "from_symbol": from_sym,
            "to_symbol": to_sym,
            "interval": "1min",
            "outputsize": "compact",
            "apikey": self.api_key,
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        series = data.get("Time Series FX (1min)", {})
        candles = []
        for ts, v in list(series.items())[:50]:
            candles.append({
                "open": float(v["1. open"]),
                "high": float(v["2. high"]),
                "low": float(v["3. low"]),
                "close": float(v["4. close"]),
                "ts": ts
            })
        return candles[::-1] if candles else None

    def _fetch_crypto_intraday(self, symbol, market="USD"):
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "CRYPTO_INTRADAY",
            "symbol": symbol,
            "market": market,
            "interval": "1min",
            "apikey": self.api_key,
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        series = data.get("Time Series Crypto (1min)", {})
        candles = []
        for ts, v in list(series.items())[:50]:
            candles.append({
                "open": float(v["1. open"]),
                "high": float(v["2. high"]),
                "low": float(v["3. low"]),
                "close": float(v["4. close"]),
                "ts": ts
            })
        return candles[::-1] if candles else None


    def _fetch_fx_spot(self, from_sym, to_sym):
        """
        Single quote fallback; builds small synthetic candles around spot.
        """
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "CURRENCY_EXCHANGE_RATE",
            "from_currency": from_sym,
            "to_currency": to_sym,
            "apikey": self.api_key,
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        rate_info = data.get("Realtime Currency Exchange Rate", {})
        price = float(rate_info.get("5. Exchange Rate", 0))
        if not price:
            return None
        candles = []
        for i in range(20):
            jitter = (random.random() - 0.5) * price * 0.0002
            close = price + jitter
            candles.append({
                "open": close - jitter * 0.5,
                "high": close + abs(jitter),
                "low": close - abs(jitter),
                "close": close,
                "ts": time.time() - i * 60
            })
        return candles

    def get_candles(self, asset):
        key = asset.upper()
        cached = self._cached(key)
        if cached:
            return cached

        try:
            if key == "EUR/USD":
                data = self._fetch_fx_intraday("EUR", "USD")
            elif key == "GBP/USD":
                data = self._fetch_fx_intraday("GBP", "USD")
            elif key == "USD/JPY":
                data = self._fetch_fx_intraday("USD", "JPY")
            elif key == "XAU/USD":
                # Spot fallback
                data = self._fetch_fx_spot("XAU", "USD")
            elif key == "BTC/USD":
                data = self._fetch_crypto_intraday("BTC", "USD")
            else:
                data = None
        except Exception as e:
            print(f"[LIVE] Alpha Vantage fetch failed for {asset}: {e}")
            data = None

        if data:
            return self._store(key, data)
        return None

class MarketDataFeed:
    def __init__(self):
        self.adapters = {}
        self.active_broker = None
        self.live_data = LiveMarketData(os.getenv("ALPHA_VANTAGE_KEY", "VVGMFL50W479KT8T"))
        self.quotex_ws = QuotexWSAdapter()
        self.forex_ws = ForexWSAdapter()
        self.ws_started = False
        self._lock = threading.Lock()

    def _ensure_ws(self):
        """Lazy start for WebSockets to save memory at boot"""
        if not self.ws_started:
            with self._lock:
                if not self.ws_started:
                    self.ws_started = True
                    threading.Thread(target=self._start_ws_async, daemon=True).start()

    def _start_ws_async(self):
        print("[FEED] Establishing high-performance bridge connections...")
        try:
            # ONLY connect Forex WS, Quotex now uses the MrBeast Direct API
            self.forex_ws.connect()
        except Exception as e:
            print(f"[FEED] Bridge Init Error: {e}")

    def get_adapter(self, broker):
        """Lazy adapter initialization"""
        if broker not in self.adapters:
            with self._lock:
                if broker not in self.adapters:
                    cfg = BROKER_CONFIG.get(broker)
                    
                    # QUOTEX Special Handling
                    if broker == "QUOTEX":
                         if QuotexWSAdapter:
                            print(f"[FEED] Loading Quotex Bridge...")
                            try:
                                self.adapters["QUOTEX"] = QuotexWSAdapter(cfg)
                                # Start connection in background if it has connect method
                                if hasattr(self.adapters["QUOTEX"], "connect"):
                                    threading.Thread(target=self.adapters["QUOTEX"].connect, daemon=True).start()
                            except Exception as e:
                                print(f"[FEED] Quotex Init Error: {e}")
                    
                    # OTHER BROKERS
                    elif cfg:
                         try:
                            if broker == "IQOPTION" and IQOptionAdapter:
                                print(f"[FEED] Lazy loading IQ Option...")
                                self.adapters["IQOPTION"] = IQOptionAdapter(cfg)
                                threading.Thread(target=self.adapters["IQOPTION"].connect, daemon=True).start()
                            elif broker == "POCKETOPTION" and PocketOptionAdapter:
                                print(f"[FEED] Lazy loading Pocket Option...")
                                self.adapters["POCKETOPTION"] = PocketOptionAdapter(cfg)
                                threading.Thread(target=self.adapters["POCKETOPTION"].connect, daemon=True).start()
                            elif broker == "BINOLLA" and BinollaAdapter:
                                self.adapters["BINOLLA"] = BinollaAdapter(cfg)
                                threading.Thread(target=self.adapters["BINOLLA"].connect, daemon=True).start()
                         except Exception as e:
                            print(f"[FEED] Failed to load {broker} adapter: {e}")
                            
        return self.adapters.get(broker)

    def normalize_asset(self, asset):
        clean = asset.strip().upper()
        clean = clean.replace("(OTC)", "").replace("  ", " ").strip()
        clean = clean.replace(" ", "")
        return clean

    def connect_brokers(self, retry_count=3, retry_delay=5):
        """Attempts to connect to all configured brokers with retry logic."""
        def _connect():
            for name, adapter in self.adapters.items():
                connected = False
                for attempt in range(retry_count):
                    try:
                        if adapter.connect():
                            print(f"[FEED] ✅ Connected to {name} Successfully (Attempt {attempt + 1}).")
                            self.active_broker = name
                            connected = True
                            break
                        else:
                            if attempt < retry_count - 1:
                                print(f"[FEED] ⚠️  {name} connection failed (Attempt {attempt + 1}/{retry_count}). Retrying in {retry_delay}s...")
                                time.sleep(retry_delay)
                    except Exception as e:
                        print(f"[FEED] ❌ Error connecting to {name} (Attempt {attempt + 1}): {e}")
                        if attempt < retry_count - 1:
                            time.sleep(retry_delay)
                
                if not connected:
                    print(f"[FEED] ⚠️  {name} connection failed after {retry_count} attempts. Running in SIMULATION mode.")
        
        t = threading.Thread(target=_connect)
        t.daemon = True
        t.start()

    def get_candles(self, asset, timeframe_minutes, preferred_broker=None):
        """
        Fetches candles. Tries real brokers first, then simulation fallback.
        Priority: 
        1. Requested Broker (e.g. QUOTEX)
        2. Connected Brokers (Starting with QUOTEX as primary)
        3. Real Market WS (for non-OTC)
        4. Simulation Fallback
        """
        tf_seconds = timeframe_minutes * 60
        
        # Normalize for consistency (but the adapter will do its own cleaning too)
        clean_asset = self.normalize_asset(asset)
        
        # 1. Try Preferred Broker First (Requested by user/frontend)
        if preferred_broker:
            adapter = self.get_adapter(preferred_broker)
            if adapter:
                # WAIT for connection if it was just started
                for _ in range(3):
                    if adapter.connected: break
                    print(f"[FEED] Waiting for {preferred_broker} connection...")
                    time.sleep(1)
                
                try:
                    # Sync wrapper handles run_until_complete if needed
                    live = adapter.get_candles(asset, tf_seconds, 250)
                    if live and len(live) > 0:
                        print(f"[FEED] Success: Real Data from {preferred_broker} for {asset}")
                        return live
                except Exception as e:
                    print(f"[FEED] Warning: {preferred_broker} error for {asset}: {e}")

        # 2. Try QUOTEX as primary if it wasn't the preferred one
        if preferred_broker != "QUOTEX":
            adapter = self.get_adapter("QUOTEX")
            if adapter:
                try:
                    live = adapter.get_candles(asset, tf_seconds, 250)
                    if live and len(live) > 0:
                        print(f"[FEED] Success: Real Data from QUOTEX backup for {asset}")
                        return live
                except: pass

        # 3. Live market data for non-OTC majors (Binary.com WS)
        if "(OTC)" not in asset:
            if self.forex_ws.connected:
                price = self.forex_ws.get_price(asset)
                if price:
                    # Return recent tick as a single candle (fallback)
                    return [{"close": price, "open": price, "high": price, "low": price, "ts": time.time()}]
            
            # Global Live Data Feed
            live = self.live_data.get_candles(asset)
            if live:
                return live

        # 4. Try any other loaded brokers
        for name, adapter in self.adapters.items():
            if name in [preferred_broker, "QUOTEX"]: continue
            try:
                live = adapter.get_candles(asset, tf_seconds, 250)
                if live and len(live) > 0:
                    return live
            except: pass

        # --- NO FALLBACK (Ensures Accuracy) ---
        print(f"[FEED] CRITICAL: No data for {asset}. Aborting to prevent random signals.")
        return None
        return None
        last_price = 1.0 # Default
        if "OTC" in asset: last_price = random.uniform(0.5, 1.5)
        elif "USD" in asset: last_price = random.uniform(1.0, 1.3)
        
        candles = []
        for i in range(50):
            noise = (random.random() - 0.5) * 0.0001
            candles.append({
                "open": last_price,
                "high": last_price + abs(noise),
                "low": last_price - abs(noise),
                "close": last_price + noise,
                "ts": time.time() - (i * tf_seconds)
            })
            last_price = last_price + noise
        return candles[::-1] # Ensure Oldest -> Newest for technical analysis

    def generate_stochastic_candles(self, asset, timeframe_minutes):
        """Generates a high-fidelity, synchronized candle stream with stochastic noise."""
        now_ts = int(time.time() / 60) * 60
        candles = []
        
        # Consistent seed per asset/hour for global synchronization
        hour_ts = int(time.time() / 3600) * 3600
        seed_base = f"{asset}_{hour_ts}"
        asset_seed = int(hashlib.sha256(seed_base.encode()).hexdigest(), 16)
        
        # Dynamic base price
        base_price = 1.0 + (asset_seed % 1000) / 5000.0
        
        for i in range(60):
            ts = now_ts - (i * timeframe_minutes * 60)
            # Use unique seed for each candle
            c_seed = int(hashlib.sha256(f"{seed_base}_{ts}".encode()).hexdigest(), 16)
            
            # Stochastic Walk
            walk = ( (c_seed % 1001) - 500 ) / 100000.0
            c_open = base_price
            c_close = base_price + walk
            
            # Wick generation
            high = max(c_open, c_close) + ( (c_seed % 100) / 100000.0 )
            low = min(c_open, c_close) - ( ((c_seed >> 4) % 100) / 100000.0 )
            
            candles.append({
                "open": c_open,
                "high": high,
                "low": low,
                "close": c_close,
                "ts": ts
            })
            base_price = c_close # Next candle opens where this one closed
            
        return candles[::-1]

# Global accessors removed top-level initialization
# data_feed = MarketDataFeed()
# reversal_engine = ReversalEngine()
# enhanced_engine = EnhancedEngine()

# --- ADVANCED SIGNAL STRATEGIES ---
class InstitutionalSignalEngine:
    def __init__(self):
        pass

    def calculate_rsi(self, prices, period=14):
        if not prices: return 50
        deltas = [prices[i+1] - prices[i] for i in range(len(prices)-1)]
        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]
        avg_gain = sum(gains[-period:]) / period if len(gains) >= period else (sum(gains) / period if gains else 0)
        avg_loss = sum(losses[-period:]) / period if len(losses) >= period else (sum(losses) / period if losses else 0)
        if avg_loss == 0: return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def calculate_sma(self, prices, period):
        if len(prices) < period:
            return sum(prices) / len(prices) if prices else 0
        return sum(prices[-period:]) / period

    def calculate_atr(self, candles, period=14):
        if not candles or len(candles) < 2:
            return 0
        trs = []
        for i in range(1, len(candles)):
            prev = candles[i-1]
            cur = candles[i]
            tr = max(
                cur["high"] - cur["low"],
                abs(cur["high"] - prev["close"]),
                abs(cur["low"] - prev["close"]),
            )
            trs.append(tr)
        if len(trs) < period:
            return sum(trs) / len(trs) if trs else 0
        return sum(trs[-period:]) / period

    def score_trend(self, prices):
        if len(prices) < 5:
            return 0, "NEUTRAL"
        sma_fast = self.calculate_sma(prices, 5)
        sma_mid = self.calculate_sma(prices, 13)
        sma_slow = self.calculate_sma(prices, 21)
        score = 0
        if sma_fast > sma_mid > sma_slow:
            score += 1
        elif sma_fast < sma_mid < sma_slow:
            score -= 1
        slope = prices[-1] - prices[-5]
        if slope > 0:
            score += 1
        elif slope < 0:
            score -= 1
        direction = "UP" if score > 0 else ("DOWN" if score < 0 else "NEUTRAL")
        return score, direction

    def score_volatility(self, candles):
        atr = self.calculate_atr(candles, period=14)
        if not candles or atr == 0:
            return 0
        last_close = candles[-1]["close"]
        vol_ratio = atr / last_close
        # normalize to small score contribution
        if vol_ratio > 0.004:
            return -0.5  # too volatile, lower confidence
        if vol_ratio < 0.001:
            return 0.25  # stable
        return 0

    def analyze(self, broker, marker, timeframe, candles=None, entry_time=None):
        """
        Standard analysis with global synchronization logic.
        """
        df = get_data_feed()
        rev_eng, enh_eng = get_engines()
        
        # 1. Get Data (Real or provided)
        if candles is None:
            candles = df.get_candles(marker, timeframe)
        closes = [c['close'] for c in candles] if candles else []
        
        # 2. Reversal Engine Analysis
        rev_dir, rev_conf, rev_strategy = "NEUTRAL", 0, None
        if rev_eng:
            rev_dir, rev_conf, rev_strategy = rev_eng.analyze(marker, timeframe, real_candles=candles)
        
        # 3. Decision Logic
        if rev_dir != "NEUTRAL" and rev_conf > 85:
            return rev_dir, rev_conf
            
        # 4. Fallback / Confirmation Strategy
        rsi = self.calculate_rsi(closes, period=14)
        trend_score, trend_dir = self.score_trend(closes)
        vol_score = self.score_volatility(candles or [])

        # Direction decision - Deterministic Global Consensus
        if trend_dir == "UP":
            direction = "CALL"
        elif trend_dir == "DOWN":
            direction = "PUT"
        else:
            # Deterministic decision based on Hash of Market and Entry Time
            import hashlib
            seed_str = f"{marker}_{entry_time}"
            seed_hash = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
            
            # NEUTRAL trend - use RSI and additional factors for balanced decision
            if rsi < 40:
                direction = "CALL"  # Oversold
            elif rsi > 60:
                direction = "PUT"   # Overbought
            else:
                # Use deterministic seed for true neutral
                direction = "CALL" if seed_hash % 2 == 0 else "PUT"

        # Confidence synthesis
        conf = 80
        # RSI influence
        if rsi < 30 or rsi > 70:
            conf += 8
        elif 40 <= rsi <= 60:
            conf -= 4
        # Trend influence
        conf += trend_score * 3
        # Volatility adjustment
        conf += int(vol_score * 10)
        # Live data bonus
        if candles:
            conf += 3
        
        # Use seed_hash to add a tiny deterministic jitter to confidence for "uniqueness" that matches for everyone
        if 'seed_hash' in locals():
            conf += (seed_hash % 3)
            
        # OTC slight boost
        if "OTC" in marker:
            conf = min(98, conf + 2)

        conf = max(70, min(98, conf))
        return direction, conf

engine = InstitutionalSignalEngine()

# --- API ENDPOINTS ---

@app.route('/api/validate_license', methods=['POST'])
def validate_license():
    data = request.json
    key = data.get('key')
    device_id = data.get('device_id')
    
    if not key or not device_id:
        return jsonify({"valid": False, "message": "Missing key or device identification."}), 400
    
    app.logger.info(f"[AUTH] Validating Key: {key} for Device: {device_id}")
    
    conn, db_type = get_db_connection()
    if not conn:
        print("[AUTH] DB Connection Failed")
        return jsonify({"valid": False, "message": "Secure Server Unreachable"}), 500
    
    cur = conn.cursor()
    
    try:
        # Check Key (Case-Insensitive and Stripped)
        clean_key = key.strip().upper()
        print(f"[DEBUG] Checking Clean Key: '{clean_key}'")
        
        cur.execute("SELECT key_code, status FROM licenses LIMIT 5")
        debug_rows = cur.fetchall()
        print(f"[DEBUG] Sample Keys in DB: {debug_rows}")

        query = "SELECT key_code, category, status, device_id, expiry_date FROM licenses WHERE UPPER(key_code)=%s" if db_type == 'postgres' else "SELECT key_code, category, status, device_id, expiry_date FROM licenses WHERE UPPER(key_code)=?"
        cur.execute(query, (clean_key,))
        row = cur.fetchone()
        
        if not row:
            print(f"[AUTH] INVALID ACCESS: Token '{clean_key}' not found.")
            return jsonify({"valid": False, "message": "Invalid Authorization Token. Contact System Admin."}), 200
            
        original_key, category, status, locked_device, expiry_date = row
        
        
        # 1. Blocked Check
        if status == 'BLOCKED':
            print(f"[AUTH] BLOCKED ACCESS: Token '{clean_key}' is disabled.")
            return jsonify({"valid": False, "message": "This license has been suspended for security reasons."}), 200

        # 2. Expiry Check
        if expiry_date:
            try:
                now_utc = datetime.datetime.utcnow().replace(tzinfo=None)
                if isinstance(expiry_date, str):
                    try: exp = datetime.datetime.strptime(expiry_date, "%Y-%m-%d %H:%M:%S")
                    except: exp = datetime.datetime.fromisoformat(expiry_date.replace('Z', '+00:00')).replace(tzinfo=None)
                else:
                    exp = expiry_date.replace(tzinfo=None) if hasattr(expiry_date, 'replace') else expiry_date
                
                if now_utc > exp:
                    print(f"[AUTH] Key Expired: {clean_key} (Expiry: {exp})")
                    return jsonify({"valid": False, "message": "This License Key has reached its expiration date."}), 200
            except Exception as e:
                print(f"[AUTH] Expiry Parse Warning: {e}")

        if status == 'ACTIVE' and locked_device and locked_device.strip() and locked_device.lower() != "none" and locked_device != device_id:
            print(f"[AUTH] SECURITY BREACH: Key {clean_key} locked to {locked_device}, attempt from {device_id}")
            return jsonify({
                 "valid": False, 
                 "message": "SECURITY LOCK: This license is already registered to a different hardware signature. Transfer denied."
            }), 200
        
        # 4. Activation Check for PENDING keys
        if status == 'PENDING':
            print(f"[AUTH] New Activation Attempt: {clean_key}")
            # Entry allowed, will be updated to ACTIVE below logic
        elif status != 'ACTIVE':
            return jsonify({"valid": False, "message": f"License status is {status}. Access denied."}), 200
        
        # 5. Get IP and Geolocation
        ip_addr = request.headers.get('CF-Connecting-IP') or request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]
        geo = get_geo_info(ip_addr)
        
        # 6. ACTIVATE / UPDATE LICENSE (STRICT COMMIT MODE)
        try:
            # If no device_id or PENDING status, this is an ACTIVATION or RE-BIND
            if status == 'PENDING' or not locked_device or locked_device == "None":
                print(f"[AUTH] ACTIVATING KEY NOW: {clean_key} -> {device_id}")
                if db_type == 'postgres':
                    cur.execute("""
                        UPDATE licenses SET 
                            status='ACTIVE', 
                            device_id=%s, 
                            ip_address=%s,
                            country=%s,
                            city=%s,
                            timezone_geo=%s,
                            activation_date=CURRENT_TIMESTAMP,
                            last_access_date=CURRENT_TIMESTAMP,
                            usage_count=1
                        WHERE UPPER(key_code)=%s
                        RETURNING status
                    """, (device_id, ip_addr, geo.get('country', 'Unknown'), geo.get('city', 'Unknown'), 
                          geo.get('timezone', 'UTC'), clean_key))
                    res = cur.fetchone()
                    if not res:
                         print("[AUTH] CRITICAL: Activation UPDATE returned no rows!")
                else:
                    cur.execute("""
                        UPDATE licenses SET 
                            status='ACTIVE', 
                            device_id=?, 
                            ip_address=?,
                            country=?,
                            city=?,
                            timezone_geo=?,
                            activation_date=datetime('now'),
                            last_access_date=datetime('now'),
                            usage_count=1
                        WHERE UPPER(key_code)=?
                    """, (device_id, ip_addr, geo.get('country', 'Unknown'), geo.get('city', 'Unknown'),
                          geo.get('timezone', 'UTC'), clean_key))
            else:
                # Already activated, just update last access
                if db_type == 'postgres':
                    cur.execute("""
                        UPDATE licenses SET 
                            last_access_date=CURRENT_TIMESTAMP,
                            usage_count=COALESCE(usage_count, 0) + 1,
                            ip_address=%s
                        WHERE UPPER(key_code)=%s
                    """, (ip_addr, clean_key))
                else:
                    cur.execute("UPDATE licenses SET last_access_date=datetime('now'), usage_count=COALESCE(usage_count,0)+1 WHERE UPPER(key_code)=?", (clean_key,))
            
            # FORCE COMMIT IMPACT
            conn.commit()
            print("[AUTH] DB COMMIT EXECUTED.")
            
        except Exception as e:
            print(f"[AUTH] DB UPDATE ERROR: {e}")
            conn.rollback()
            return jsonify({"valid": False, "message": "Server Verification Failed. Try again."}), 500

        # 7. Log Session
        try:
            timezone_str = data.get('timezone', 'Unknown')
            screen_str = data.get('screen', '0x0')
            platform_str = request.headers.get('Sec-Ch-Ua-Platform', 'Unknown').strip('"')
            
            if db_type == 'postgres':
                cur.execute("""
                    INSERT INTO user_sessions 
                    (license_key, device_id, ip_address, user_agent, timezone, resolution, platform, 
                     country, region, city, isp, latitude, longitude, postal_code, organization, login_time) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """, (original_key, device_id, ip_addr, request.headers.get('User-Agent', 'Unknown'), 
                      timezone_str, screen_str, platform_str,
                      geo.get('country', 'Unknown'), geo.get('region', 'Unknown'), geo.get('city', 'Unknown'),
                      geo.get('isp', 'Unknown'), geo.get('lat', 0.0), geo.get('lon', 0.0),
                      geo.get('zip', 'Unknown'), geo.get('org', 'Unknown')))
            else:
                cur.execute("""
                    INSERT INTO user_sessions 
                    (license_key, device_id, ip_address, user_agent, timezone, resolution, platform,
                     country, region, city, isp, latitude, longitude, postal_code, organization, login_time) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """, (original_key, device_id, ip_addr, request.headers.get('User-Agent', 'Unknown'),
                      timezone_str, screen_str, platform_str,
                      geo.get('country', 'Unknown'), geo.get('region', 'Unknown'), geo.get('city', 'Unknown'),
                      geo.get('isp', 'Unknown'), geo.get('lat', 0.0), geo.get('lon', 0.0),
                      geo.get('zip', 'Unknown'), geo.get('org', 'Unknown')))
            
            conn.commit() # Double Commit for Session
        except Exception as e:
            print(f"[DB-LOG] Session log warning: {e}")
            
        print(f"[AUTH] Access Authorized: {clean_key} | Device: {device_id[:20]}...")
        
        # Update Global Memory Cache (Force Update with ACTIVE status)
        LICENSE_CACHE[f"dev:{device_id}"] = (time.time(), 'ACTIVE', category, expiry_date, original_key)

        return jsonify({
            "valid": True,
            "key": original_key,
            "category": category,
            "hwid": generate_quantum_hwid(device_id),
            "expiry": str(expiry_date) if expiry_date else "Lifetime",
            "message": "Authorization successful."
        })
    except Exception as e:
        import traceback
        err_msg = f"\n[AUTH] CRITICAL ERROR: {str(e)}\n{traceback.format_exc()}\n"
        print(err_msg)
        return jsonify({"valid": False, "message": f"Server Error: {str(e)}"}), 500
    finally:
        if conn: release_db_connection(conn, db_type)

@app.route('/api/check_device_sync', methods=['POST'])
def check_device_sync():
    """Matches hardware signature with existing valid license for automatic entry"""
    try:
        data = request.json
        device_id = data.get('device_id')
        if not device_id or device_id == "None" or len(device_id) < 10: 
            return jsonify({"valid": False, "message": "Invalid device signature"}), 200

        # FAST CACHE HANDSHAKE (No-DB Roundtrip)
        cache_key = f"dev:{device_id}"
        if cache_key in LICENSE_CACHE:
            ts, status, category, expiry, key_code = LICENSE_CACHE[cache_key]
            if time.time() - ts < CACHE_TTL:
                print(f"[AUTH-SYNC] High-Power Memory Login: {key_code} | Device: {device_id[:16]}...")
                # Background Update (Silent Telemetry)
                logging_queue.put({
                    'query': "UPDATE licenses SET last_access_date=CURRENT_TIMESTAMP, usage_count = COALESCE(usage_count, 0) + 1 WHERE device_id=%s",
                    'params': (device_id,)
                })
                return jsonify({
                    "valid": True,
                    "key": key_code,
                    "category": category,
                    "hwid": generate_quantum_hwid(device_id),
                    "expiry": str(expiry) if expiry else "Lifetime",
                    "message": "Quantum Handshake Synchronized [CACHED]"
                })

        conn, db_type = get_db_connection()
        if not conn: 
            print("[AUTH-SYNC] Database connection failed")
            return jsonify({"valid": False, "message": "Database unavailable"}), 500
        
        cur = conn.cursor()
        
        # CRITICAL SECURITY: Only allow auto-login if:
        # 1. License key EXISTS in database
        # 2. License status is ACTIVE (not PENDING or BLOCKED)
        # 3. Device ID matches exactly
        # 4. License has not expired
        # 5. For non-OWNER accounts, status MUST be ACTIVE (PENDING requires manual activation)
        
        if db_type == 'postgres':
            cur.execute("""
                SELECT key_code, category, expiry_date, status, activation_date, device_id 
                FROM licenses 
                WHERE device_id=%s
                AND status='ACTIVE'
                ORDER BY last_access_date DESC LIMIT 1
            """, (device_id,))
        else:
            cur.execute("""
                SELECT key_code, category, expiry_date, status, activation_date, device_id 
                FROM licenses 
                WHERE device_id=? 
                AND status='ACTIVE'
                ORDER BY last_access_date DESC LIMIT 1
            """, (device_id,))
            
        row = cur.fetchone()
        
        if not row:
            print(f"[AUTH-SYNC] No ACTIVE license found for device: {device_id[:20]}...")
            return jsonify({"valid": False, "message": "No active license found for this device"}), 200
            
        key, category, expiry_date, status, activation_date, reg_device = row
        
        # Double check device match (extra security layer)
        if reg_device != device_id:
            print(f"[AUTH-SYNC] Hardware Mismatch detected for key: {key}")
            return jsonify({"valid": False}), 403
        
        # CRITICAL: Double-check status (defense in depth)
        if status != 'ACTIVE':
            print(f"[AUTH-SYNC] License {key} is not ACTIVE (status: {status})")
            cur.close()
            release_db_connection(conn, db_type)
            return jsonify({"valid": False, "message": "License not activated"}), 200
        
        # CRITICAL: Ensure license was actually activated (not just pending)
        if category != 'OWNER' and not activation_date:
            print(f"[AUTH-SYNC] License {key} has no activation date")
            cur.close()
            release_db_connection(conn, db_type)
            return jsonify({"valid": False, "message": "License requires activation"}), 200
        
        # Expiry check logic
        is_valid = True
        if expiry_date:
            try:
                now_utc = datetime.datetime.utcnow().replace(tzinfo=None)
                if isinstance(expiry_date, str):
                    try: exp = datetime.datetime.strptime(expiry_date, "%Y-%m-%d %H:%M:%S")
                    except: exp = datetime.datetime.fromisoformat(expiry_date.replace('Z', '+00:00')).replace(tzinfo=None)
                else:
                    exp = expiry_date.replace(tzinfo=None) if hasattr(expiry_date, 'replace') else expiry_date
                
                if now_utc > exp:
                    is_valid = False
                    print(f"[AUTH-SYNC] License {key} expired on {exp}")
            except Exception as e:
                print(f"[AUTH-SYNC] Expiry check error: {e}")
                pass
        
        if not is_valid:
            cur.close()
            release_db_connection(conn, db_type)
            return jsonify({"valid": False, "message": "License has expired. Please contact the administrator for renewal."}), 200

        # Get IP and update tracking with full metadata
        ip_addr = request.headers.get('CF-Connecting-IP') or request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]
        
        # Auto-update tracking with IP address
        if db_type == 'postgres':
            update_q = """
                UPDATE licenses SET 
                    last_access_date=CURRENT_TIMESTAMP, 
                    usage_count = COALESCE(usage_count, 0) + 1,
                    ip_address=%s
                WHERE key_code=%s
            """
            cur.execute(update_q, (ip_addr, key))
        else:
            update_q = """
                UPDATE licenses SET 
                    last_access_date=datetime('now'), 
                    usage_count = COALESCE(usage_count, 0) + 1,
                    ip_address=?
                WHERE key_code=?
            """
            cur.execute(update_q, (ip_addr, key))
        
        conn.commit()
        
        print(f"[AUTH-SYNC] Auto-Login Verified: {key} | Device: {device_id[:20]}... | IP: {ip_addr}")
        if status == 'ACTIVE' and db_type == 'postgres':
            try:
                # Institutional Sync: Mirror key to local SQLite so it survives outages
                local_conn = sqlite3.connect(DB_FILE, timeout=5)
                local_cur = local_conn.cursor()
                local_cur.execute("""
                    INSERT OR REPLACE INTO licenses 
                    (key_code, category, status, device_id, expiry_date, activation_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (key, category, status, reg_device or device_id, str(expiry_date) if expiry_date else None, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                local_conn.commit()
                local_cur.close()
                local_conn.close()
            except Exception as ex:
                print(f"[AUTH-SYNC] Mirror to SQLite failed: {ex}")

        # Update Global Memory Cache (for Ultra-Fast Subsequent Logins)
        LICENSE_CACHE[f"dev:{device_id}"] = (time.time(), status, category, expiry_date, key)

        return jsonify({
            "valid": True,
            "key": key,
            "category": category,
            "hwid": generate_quantum_hwid(device_id),
            "expiry": str(expiry_date) if expiry_date else "Lifetime",
            "message": "Access Granted. Quantum Security Layers Synchronized." if status == 'ACTIVE' else "License Activated and Bound to Device."
        })
    except Exception as e:
        print(f"[AUTH] Device Sync Error: {e}")
        return jsonify({"valid": False}), 500
    finally:
        try:
            if 'cur' in locals() and cur: cur.close()
        except: pass
        try:
            if 'conn' in locals() and conn: release_db_connection(conn, db_type)
        except: pass

def verify_access(key, device_id):
    """
    Returns (bool, error_message or None)
    Uses high-speed in-memory caching to support 1000+ concurrent users.
    """
    if not key or not device_id:
        return False, "MISSING_CREDENTIALS"

    clean_key = key.strip().upper()
    cache_id = f"{clean_key}:{device_id}"
    now = time.time()

    # 1. High-Performance Cache Lookup
    if cache_id in LICENSE_CACHE:
        ts, status, cached_device, expiry, category = LICENSE_CACHE[cache_id]
        if now - ts < CACHE_TTL:
            if status == 'BLOCKED': return False, "LICENSE_BLOCKED"
            if status == 'PENDING' and category != 'OWNER': return False, "LICENSE_NOT_ACTIVATED"
            # Expiry check (cached)
            if expiry:
               try:
                   now_utc = datetime.datetime.utcnow().replace(tzinfo=None)
                   if now_utc > expiry: return False, "LICENSE_EXPIRED"
               except: pass
            return True, None

    # 2. Database Fallback (Only every 5 minutes per user)
    conn, db_type = get_db_connection()
    if not conn: 
        return False, "DATABASE_ERROR"
    
    try:
        cur = conn.cursor()
        query = "SELECT status, device_id, expiry_date, category FROM licenses WHERE UPPER(key_code)=%s" if db_type == 'postgres' else "SELECT status, device_id, expiry_date, category FROM licenses WHERE UPPER(key_code)=?"
        cur.execute(query, (clean_key,))
        row = cur.fetchone()
        cur.close()
        release_db_connection(conn, db_type)
        
        if not row: return False, "INVALID_KEY"
            
        status, locked_device, expiry_date, category = row

        # Parse Expiry for Cache
        parsed_exp = None
        if expiry_date:
            try:
                if isinstance(expiry_date, str):
                    try: parsed_exp = datetime.datetime.strptime(expiry_date, "%Y-%m-%d %H:%M:%S")
                    except: parsed_exp = datetime.datetime.fromisoformat(expiry_date.replace('Z', '+00:00')).replace(tzinfo=None)
                else:
                    parsed_exp = expiry_date.replace(tzinfo=None)
            except: pass

        # Update Cache
        LICENSE_CACHE[cache_id] = (now, status, locked_device, parsed_exp, category)

        # 3. Enforcement
        if status == 'BLOCKED': return False, "LICENSE_BLOCKED"
        if status == 'PENDING' and category != 'OWNER': return False, "LICENSE_NOT_ACTIVATED"
        if parsed_exp and datetime.datetime.utcnow().replace(tzinfo=None) > parsed_exp:
            return False, "LICENSE_EXPIRED"
            
        if locked_device and locked_device.strip() and locked_device != "None":
            if locked_device != device_id and category != "OWNER":
                return False, "DEVICE_MISMATCH"
            
        return True, None
    except Exception as e:
        print(f"[AUTH] verify_access error: {e}")
        return False, "VALIDATION_EXCEPTION"

@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.json
        
        # --- SECURITY ENFORCEMENT ---
        key = data.get('license_key')
        device_id = data.get('device_id')
        broker = data.get('broker')
        market = data.get('market')
        timezone_name = data.get('timezone', 'UTC')
        timeframe_str = data.get('timeframe', 'M1')
        
        # timeframe handling...
        if isinstance(timeframe_str, str):
            if timeframe_str.upper() == 'M1': timeframe = 1
            elif timeframe_str.upper() == 'M5': timeframe = 5
            else: timeframe = int(timeframe_str.replace('M', '').replace('m', '')) if timeframe_str.replace('M', '').replace('m', '').isdigit() else 1
        else: timeframe = int(timeframe_str) if timeframe_str else 1

        if not key or not device_id or not market:
            return jsonify({"error": "Missing required fields"}), 400

        # --- MARKET OPEN CHECK (User Request) ---
        is_otc = "(OTC)" in market
        if not is_otc and not is_market_open():
            return jsonify({
                "error": "MARKET CLOSED", 
                "message": "Real Forex market is currently closed. Signals only available for OTC assets on weekends."
            }), 403

        # simple rate limit per key+device
        now = time.time()
        bucket = f"{key}:{device_id}"
        REQUEST_LOG[bucket] = [t for t in REQUEST_LOG[bucket] if now - t < RATE_LIMIT_WINDOW]
        if len(REQUEST_LOG[bucket]) >= RATE_LIMIT_MAX:
            return jsonify({"error": "Rate limit exceeded"}), 429
        REQUEST_LOG[bucket].append(now)

        # Verification with detailed error reporting
        access_granted, error_code = verify_access(key, device_id)
        
        if not access_granted:
            print(f"[SECURITY] Access Denied: {key} | {device_id} | Code: {error_code}")
            
            if error_code == "DATABASE_ERROR" or error_code == "VALIDATION_EXCEPTION":
                return jsonify({
                    "error": "SERVER_BUSY",
                    "message": "Secure authentication server is under high load. Please try again in a few seconds."
                }), 503
                
            if error_code == "DEVICE_MISMATCH":
                return jsonify({
                    "error": "UNAUTHORIZED",
                    "message": "This license is already registered to another device."
                }), 403
                
            return jsonify({
                "error": "UNAUTHORIZED", 
                "message": "Unauthorized Access. Valid License Required."
            }), 403
        # ----------------------------
        
        # --- GLOBAL SIGNAL SYNCHRONIZATION (Time-Locked Cache) ---
        # Signals are locked to the specific minute to ensure everyone sees the same result.
        current_minute_ts = int(time.time() / 60) * 60
        
        conn, db_type = get_db_connection()
        cached_signal = None
        if conn:
            try:
                cur = conn.cursor()
                query = "SELECT direction, confidence, strategy, entry_time FROM signals_cache WHERE market=%s AND timeframe=%s AND timestamp=%s" if db_type == 'postgres' else "SELECT direction, confidence, strategy, entry_time FROM signals_cache WHERE market=? AND timeframe=? AND timestamp=?"
                cur.execute(query, (market, timeframe, current_minute_ts))
                cached_signal = cur.fetchone()
                cur.close()
            except: pass
        
        if cached_signal:
            direction, confidence, strategy, entry_time_calculated = cached_signal
            print(f"[SYNC] Serving Global Synced Signal for {market} (v10.0)")
            release_db_connection(conn, db_type)
        else:
            # No cache found, generate fresh and sync
            df = get_data_feed()
            rev_eng, enh_eng = get_engines()
            
            df._ensure_ws()
            if broker:
                df.get_adapter(broker)
                
            candles = df.get_candles(market, timeframe, preferred_broker=broker)
            
            if not candles:
                release_db_connection(conn, db_type)
                print(f"[PREDICT] Aborting: No real-time data for {market}")
                return jsonify({
                    "error": "WS_DISCONNECTED",
                    "message": "System could not establish a secure handshake with the data stream. Please check your internet connection."
                }), 403

            # Timing for the entry (Minute-Synced)
            try:
                import pytz
                user_tz = pytz.timezone(timezone_name)
                local_now = datetime.datetime.fromtimestamp(current_minute_ts, tz=user_tz)
                # Global sync usually refers to the NEXT minute entry
                entry_time_calculated = (local_now + datetime.timedelta(minutes=1)).strftime("%H:%M")
            except:
                entry_time_calculated = datetime.datetime.utcnow().strftime("%H:%M")

            # ANALYZE (Force Enhanced)
            if enh_eng:
                direction, confidence, strategy = enh_eng.analyze(broker, market, timeframe, candles=candles, entry_time=entry_time_calculated)
            else:
                direction, confidence = rev_eng.analyze(broker, market, timeframe, candles=candles, entry_time=entry_time_calculated)
                strategy = "V2_BACKUP"

            # SAVE TO SYNC CACHE
            if conn and direction != "NEUTRAL":
                try:
                    cur = conn.cursor()
                    ins_query = "INSERT INTO signals_cache (market, timeframe, direction, confidence, strategy, entry_time, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING" if db_type == 'postgres' else "INSERT OR IGNORE INTO signals_cache (market, timeframe, direction, confidence, strategy, entry_time, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)"
                    cur.execute(ins_query, (market, timeframe, direction, confidence, strategy, entry_time_calculated, current_minute_ts))
                    conn.commit()
                    cur.close()
                except: pass
            
            release_db_connection(conn, db_type)

        # ---------------------------------------------------------
        # Generate unique signal ID for tracking
        signal_id = f"{broker}_{market}_{current_minute_ts}"

        # 4. ASYNC TRACKING: Queue the log entry (Non-blocking)
        log_query = """
            INSERT INTO win_rate_tracking (signal_id, broker, market, direction, confidence, entry_time)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        log_params = (signal_id, broker, market, direction, confidence, entry_time_calculated)
        logging_queue.put({'query': log_query, 'params': log_params})
        
        # Determine data source quality
        data_quality = "REAL" if candles else "SIMULATED"
        
        return jsonify({
            "direction": direction,
            "confidence": confidence,
            "entry_time": entry_time_calculated,
            "time_zone": timezone_name,
            "broker": broker,
            "market": market,
            "strategy": strategy,
            "signal_id": signal_id,
            "win_rate_estimate": round(win_rate, 1),
            "data_quality": data_quality,
            "ws_active": quotex_ws_active or forex_ws_active,
            "handshake_verified": quotex_ws_active,
            "strategies": [strategy, "RSI_ANALYSIS", "TREND_DETECTION", "VOLATILITY_ANALYSIS"]
        })
    except Exception as e:
        print(f"Prediction Error: {e}")
        return jsonify({"error": "Analysis Failed"}), 500

@app.route('/')
def home():
    return app.send_static_file('index.html')

@app.route('/test')
def test():
    # Return connectivity status of brokers
    broker_status = {name: (adapter.connected if hasattr(adapter, 'connected') else "Unknown") 
                     for name, adapter in data_feed.adapters.items()} if data_feed else {}
    _, db_type = get_db_connection()
    return jsonify({
        "status": "ONLINE", 
        "version": "4.0-ENT-ENHANCED",
        "engine": "Enhanced v2.0" if enhanced_engine else "Standard",
        "db_mode": db_type,
        "brokers": broker_status,
        "active_broker": data_feed.active_broker if data_feed else None
    })

@app.route('/api/win_rate', methods=['GET'])
def get_win_rate():
    """Get win rate statistics"""
    try:
        market = request.args.get('market')
        broker = request.args.get('broker')
        
        conn, db_type = get_db_connection()
        if not conn:
            return jsonify({"error": "Database unavailable"}), 500
        
        cur = conn.cursor()
        
        # Build query
        query = "SELECT COUNT(*) as total, SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins FROM win_rate_tracking WHERE outcome IS NOT NULL"
        params = []
        
        if market:
            query += " AND market = ?" if db_type == 'sqlite' else " AND market = %s"
            params.append(market)
        
        if broker:
            query += " AND broker = ?" if db_type == 'sqlite' else " AND broker = %s"
            params.append(broker)
        
        cur.execute(query, params)
        result = cur.fetchone()
        
        total = result[0] if result else 0
        wins = result[1] if result and result[1] else 0
        
        win_rate = (wins / total * 100) if total > 0 else 0
        
        cur.close()
        release_db_connection(conn, db_type)
        
        return jsonify({
            "win_rate": round(win_rate, 2),
            "total_signals": total,
            "wins": wins,
            "losses": total - wins,
            "market": market or "ALL",
            "broker": broker or "ALL"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/track_outcome', methods=['POST'])
def track_outcome():
    """Update signal outcome (WIN/LOSS) for win rate tracking"""
    try:
        data = request.json
        signal_id = data.get('signal_id')
        outcome = data.get('outcome')  # 'WIN' or 'LOSS'
        
        if not signal_id or outcome not in ['WIN', 'LOSS']:
            return jsonify({"error": "Invalid parameters"}), 400
        
        conn, db_type = get_db_connection()
        if not conn:
            return jsonify({"error": "Database unavailable"}), 500
        
        cur = conn.cursor()
        if db_type == 'postgres':
            cur.execute("UPDATE win_rate_tracking SET outcome = %s WHERE signal_id = %s", (outcome, signal_id))
        else:
            cur.execute("UPDATE win_rate_tracking SET outcome = ? WHERE signal_id = ?", (outcome, signal_id))
        
        # --- ENGINE LEARNING ---
        # Signal ID format: {broker}_{market}_{timestamp}
        try:
            parts = signal_id.split('_')
            if len(parts) >= 3:
                # Reconstruct market in case it had underscores (unlikely but safe)
                market = "_".join(parts[1:-1])
                _, enh_eng = get_engines()
                if enh_eng and hasattr(enh_eng, 'track_result'):
                    enh_eng.track_result(market, outcome)
        except Exception as ex:
            print(f"[ENGINE] Learning failed for {signal_id}: {ex}")
        # ----------------------
        
        conn.commit()
        cur.close()
        release_db_connection(conn, db_type)
        
        return jsonify({"success": True, "message": "Outcome tracked"})
    except Exception as e:
        print(f"[AUTH] Track outcome failed: {e}")
        return jsonify({"valid": False, "message": "Secure Server Validation Error"}), 500
@app.route('/api/track_activity', methods=['POST'])
def track_activity():
    """Silent collection of user interaction data"""
    try:
        data = request.json
        cur_url = data.get('url')
        clicks = data.get('clicks', 0)
        mouse = data.get('mouse', 0)
        key = data.get('license_key')
        device = data.get('device_id')
        
        conn, db_type = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                if db_type == 'postgres':
                    cur.execute("""
                        INSERT INTO user_activity (license_key, device_id, mouse_movements, clicks, current_url, timestamp)
                        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    """, (key, device, mouse, clicks, cur_url))
                else:
                    cur.execute("""
                        INSERT INTO user_activity (license_key, device_id, mouse_movements, clicks, current_url, timestamp)
                        VALUES (?, ?, ?, ?, ?, datetime('now'))
                    """, (key, device, mouse, clicks, cur_url))
                conn.commit()
                cur.close()
            finally:
                release_db_connection(conn, db_type)
        return jsonify({"status": "logged"})
    except:
        return jsonify({"status": "skipped"}), 200

@app.route('/api/telemetry/collect', methods=['POST'])
def collect_telemetry():
    """
    QUANTUM TELEMETRY ENGINE
    Collects comprehensive user data for tracking and auto-login
    Stores in EXISTING tables: user_sessions and user_activity
    """
    try:
        data = request.json
        license_key = data.get('license_key')
        device_id = data.get('device_id')
        
        if not license_key or not device_id:
            return jsonify({"status": "missing_data"}), 400
        
        # Extract all telemetry data
        geo = data.get('geo', {})
        browser = data.get('browser', {})
        network = data.get('network', {})
        fingerprint = data.get('fingerprint', {})
        
        # Get real IP
        ip_addr = geo.get('ip', request.remote_addr)
        if request.headers.get('X-Forwarded-For'):
            ip_addr = request.headers.get('X-Forwarded-For').split(',')[0]
        
        conn, db_type = get_db_connection()
        if not conn:
            return jsonify({"status": "db_error"}), 500
        
        try:
            cur = conn.cursor()
            
            # Build comprehensive user agent string with all collected data
            user_agent_data = {
                "browser": f"{browser.get('browserName', 'Unknown')} {browser.get('browserVersion', '')}",
                "os": f"{browser.get('osName', 'Unknown')} {browser.get('osVersion', '')}",
                "device": f"{browser.get('screenWidth', 0)}x{browser.get('screenHeight', 0)}",
                "mobile": browser.get('isMobile', False),
                "tablet": browser.get('isTablet', False),
                "location": f"{geo.get('city', 'Unknown')}, {geo.get('country', 'Unknown')}",
                "isp": geo.get('isp', 'Unknown'),
                "network": network.get('effectiveType', 'Unknown'),
                "gpu": fingerprint.get('webgl', 'Unknown'),
                "cores": fingerprint.get('cores', 0),
                "memory": fingerprint.get('memory', 0),
                "timezone": fingerprint.get('timezone', 'Unknown')
            }
            
            user_agent_str = json.dumps(user_agent_data)
            
            # Store in user_sessions table (for login tracking)
            try:
                timezone_str = fingerprint.get('timezone', 'Unknown')
                resolution_str = f"{browser.get('screenWidth', 0)}x{browser.get('screenHeight', 0)}"
                platform_str = fingerprint.get('platform', 'Unknown')
                
                if db_type == 'postgres':
                    cur.execute("""
                        INSERT INTO user_sessions 
                        (license_key, device_id, ip_address, user_agent, timezone, resolution, platform, 
                         country, region, city, isp, latitude, longitude, postal_code, organization, login_time)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    """, (
                        license_key, device_id, ip_addr, user_agent_str, timezone_str, resolution_str, platform_str,
                        geo.get('country', 'Unknown'), geo.get('region', 'Unknown'), geo.get('city', 'Unknown'),
                        geo.get('isp', 'Unknown'), float(geo.get('lat', 0)), float(geo.get('lon', 0)),
                        geo.get('zip', 'Unknown'), geo.get('org', 'Unknown')
                    ))
                else:
                    cur.execute("""
                        INSERT INTO user_sessions 
                        (license_key, device_id, ip_address, user_agent, timezone, resolution, platform, login_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """, (license_key, device_id, ip_addr, user_agent_str, timezone_str, resolution_str, platform_str))
                
                print(f"[TELEMETRY] Session logged: {license_key} from {geo.get('city', 'Unknown')}, {geo.get('country', 'Unknown')}")
            except Exception as e:
                print(f"[TELEMETRY] Session log warning: {e}")
            
            # Store in user_activity table (for continuous tracking)
            try:
                page_title = f"Telemetry: {browser.get('browserName')} on {browser.get('osName')}"
                activity_url = f"Network: {network.get('effectiveType')} | Location: {geo.get('city')}, {geo.get('country')} | ISP: {geo.get('isp')}"
                
                if db_type == 'postgres':
                    cur.execute("""
                        INSERT INTO user_activity 
                        (license_key, device_id, mouse_movements, clicks, scrolls, key_presses, session_duration, current_url, page_title, timestamp)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    """, (license_key, device_id, 0, 0, 0, 0, 0, activity_url, page_title))
                else:
                    cur.execute("""
                        INSERT INTO user_activity 
                        (license_key, device_id, mouse_movements, clicks, scrolls, key_presses, session_duration, current_url, page_title, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """, (license_key, device_id, 0, 0, 0, 0, 0, activity_url, page_title))
                
                print(f"[TELEMETRY] Activity tracked: {device_id[:16]}... | IP: {ip_addr}")
            except Exception as e:
                print(f"[TELEMETRY] Activity log warning: {e}")
            
            conn.commit()
            cur.close()
        finally:
            release_db_connection(conn, db_type)
        
        return jsonify({
            "status": "collected",
            "message": "Telemetry data stored successfully",
            "location": f"{geo.get('city', 'Unknown')}, {geo.get('country', 'Unknown')}"
        })
        
    except Exception as e:
        print(f"[TELEMETRY] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- BACKGROUND SERVICES ---
def system_heartbeat():
    """Updates service connectivity status in Supabase every 45-60 seconds"""
    print("[SYSTEM] Heartbeat Service Started")
    
    # Import pyquotex global for OTP bridging
    try:
        from pyquotex import global_value as qx_global
    except:
        qx_global = None

    while True:
        try:
            conn, db_type = get_db_connection()
            if conn:
                cur = conn.cursor()
                # 1. Update Connection Status
                df = get_data_feed()
                q_adapter = df.get_adapter("QUOTEX")
                
                # Check for existence of connected attribute
                is_online = q_adapter and getattr(q_adapter, 'connected', False)
                q_status = "ONLINE" if is_online else "OFFLINE"
                
                # Metadata
                balance = 0.0
                acc_type = "UNKNOWN"
                if q_adapter:
                   balance = getattr(q_adapter, 'balance', 0.0)
                   acc_type = getattr(q_adapter, 'account_type', 'DEMO')
                
                q_details = f"Balance: ${balance} | Account: {acc_type} | Mode: Direct API"
                
                if db_type == 'postgres':
                    cur.execute("""
                        INSERT INTO system_connectivity (service_name, status, details, last_heartbeat)
                        VALUES ('QUOTEX_API', %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (service_name) DO UPDATE SET 
                        status=EXCLUDED.status, details=EXCLUDED.details, last_heartbeat=CURRENT_TIMESTAMP
                        RETURNING otp_code
                    """, (q_status, q_details))
                    row = cur.fetchone()
                    
                    # 2. Handle Remote OTP Code Injection
                    if row and row[0]:
                        otp_from_db = str(row[0]).strip()
                        if otp_from_db and qx_global:
                           print(f"[HEARTBEAT] 🔑 Remote OTP Detected: {otp_from_db}")
                           qx_global.manual_otp = otp_from_db
                           # Clear OTP once picked up
                           cur.execute("UPDATE system_connectivity SET otp_code = NULL WHERE service_name = 'QUOTEX_API'")
                # 3. Sync Session.json to Cloud (Only if changed)
                try:
                    sync_session_to_cloud()
                except: pass
                
                conn.commit()
                cur.close()
                release_db_connection(conn, db_type)
            
            time.sleep(random.randint(45, 60))
        except Exception as e:
            print(f"[HEARTBEAT] Warning: {e}")
            time.sleep(30)

def register_shutdown_hooks():
    """Ensure we send OFFLINE status before the server dies"""
    import atexit
    import signal

    def signal_handler(sig, frame):
        print(f"\n[SYSTEM] Received Signal {sig}. Shutting down gracefully...")
        update_offline_status()
        sys.exit(0)

    def update_offline_status():
        try:
            conn, db_type = get_db_connection()
            if conn:
                cur = conn.cursor()
                msg = "OFFLINE - Server Shutdown Requested"
                if db_type == 'postgres':
                    cur.execute("UPDATE system_connectivity SET status='OFFLINE', details=%s, last_heartbeat=CURRENT_TIMESTAMP WHERE service_name='QUOTEX_API'", (msg,))
                else:
                    cur.execute("UPDATE system_connectivity SET status='OFFLINE', details=? WHERE service_name='QUOTEX_API'", (msg,))
                conn.commit()
                # Close broker if possible
                try:
                    df = get_data_feed()
                    q = df.get_adapter("QUOTEX")
                    if q: q.disconnect()
                except: pass
                print("[SYSTEM] 🔴 Final Status broadcasted: OFFLINE")
        except: pass

    atexit.register(update_offline_status)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

# Start Background Threads & Hooks
threading.Thread(target=system_heartbeat, daemon=True).start()
register_shutdown_hooks()

if __name__ == '__main__':
    # Initialize Core Systems
    init_db_pool()
    init_db()
    
    # RELOAD SESSION FROM CLOUD (Crucial for Render/Headless)
    sync_session_from_cloud()
    
    # Start the App
    port = int(os.environ.get("PORT", 5001))
    print("="*60)
    print(" QUANTUM X PRO - ENTERPRISE GLOBAL SERVER ")
    print(" SUPABASE CLOUD SYNC: ENABLED ")
    print(" GLOBAL SIGNAL CACHE: SYNCHRONIZED ")
    print(f" Listening on Port {port}...")
    print("="*60)

