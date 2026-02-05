import time
import threading
from functools import wraps

try:
    from iqoptionapi.api import IQOptionAPI as IQ_Option
    LIB_AVAILABLE = True
except ImportError:
    LIB_AVAILABLE = False

def retry_on_failure(max_retries=3, delay=2):
    """Decorator for retrying failed operations"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        print(f"[IQ] {func.__name__} failed after {max_retries} attempts: {e}")
                        raise
                    time.sleep(delay * (attempt + 1))
            return None
        return wrapper
    return decorator

class IQOptionAdapter:
    def __init__(self, config):
        self.api = None
        self.config = config
        self.connected = False
        self.mode = "SIMULATION"
        self.last_connection_attempt = 0
        self.connection_lock = threading.Lock()
        self.health_check_interval = 300  # 5 minutes
        self.last_health_check = 0

    def connect(self, retry_count=3):
        """Enhanced connection with retry logic"""
        with self.connection_lock:
            # Prevent too frequent connection attempts
            if time.time() - self.last_connection_attempt < 5:
                return self.connected
            
            self.last_connection_attempt = time.time()

            # 1. Try Real Connection if credentials exist
            if self.config.get("email") and self.config.get("password") and LIB_AVAILABLE:
                for attempt in range(retry_count):
                    try:
                        print(f"[IQ] Connecting {self.config['email']}... (Attempt {attempt + 1}/{retry_count})")
                        self.api = IQ_Option(self.config["email"], self.config["password"])
                        check, reason = self.api.connect()
                        
                        if check:
                            self.connected = True
                            self.mode = "REAL"
                            balance_mode = "REAL" if self.config.get("live_account", False) else "PRACTICE"
                            try:
                                self.api.change_balance(balance_mode)
                            except:
                                pass  # Balance change is optional
                            print(f"[IQ] ✅ Connected successfully! Mode: {balance_mode}")
                            return True
                        else:
                            print(f"[IQ] Connection failed: {reason}")
                            
                    except Exception as e:
                        print(f"[IQ] Connection attempt {attempt + 1} failed: {e}")
                        if attempt < retry_count - 1:
                            time.sleep(2 * (attempt + 1))
            
            # 2. Fallback to Guest/Simulation Mode
            print("[IQ] Credentials missing or failed. Activating Guest Simulation Mode.")
            self.connected = True
            self.mode = "SIMULATION"
            return True

    def _check_health(self):
        """Periodic health check"""
        if not self.connected or not self.api:
            return False
        
        current_time = time.time()
        if current_time - self.last_health_check < self.health_check_interval:
            return True
        
        self.last_health_check = current_time
        
        try:
            # Check if API is still responsive
            if hasattr(self.api, 'check_connect'):
                return self.api.check_connect()
            return True
        except:
            print("[IQ] Health check failed, reconnecting...")
            self.connected = False
            return self.connect()

    @retry_on_failure(max_retries=2, delay=1)
    def get_candles(self, asset, timeframe_seconds=60, count=20):
        """
        Enhanced candle fetching with retry logic.
        Returns list of candles or None if unavailable.
        """
        # Health check
        if not self._check_health():
            return None

        if not self.connected:
            return None

        if self.mode == "REAL" and self.api:
            try:
                # Normalize asset name
                iq_asset = asset.replace("/", "").replace(" ", "").upper()
                if "OTC" in asset and "-OTC" not in iq_asset:
                    iq_asset += "-OTC"
                iq_asset = iq_asset.replace("(OTC)", "").replace("--", "-").strip()

                # Ensure valid parameters
                timeframe_seconds = max(timeframe_seconds, 60)
                count = min(max(count, 1), 100)

                candles = self.api.get_candles(iq_asset, timeframe_seconds, count, time.time())
                
                if not candles:
                    return None
                
                norm = []
                for c in candles:
                    try:
                        norm.append({
                            "open": float(c.get("open", 0)),
                            "high": float(c.get("max", c.get("high", 0))),
                            "low": float(c.get("min", c.get("low", 0))),
                            "close": float(c.get("close", 0)),
                            "ts": int(c.get("from", c.get("ts", time.time())))
                        })
                    except (ValueError, TypeError) as e:
                        print(f"[IQ] Error parsing candle: {e}")
                        continue
                
                return norm if norm else None
                
            except Exception as e:
                print(f"[IQ] Candle fetch failed: {e}")
                if "connection" in str(e).lower() or "timeout" in str(e).lower():
                    self.connected = False
                return None

        return None

    def disconnect(self):
        """Clean disconnect"""
        try:
            if self.api and hasattr(self.api, 'close'):
                self.api.close()
        except:
            pass
        finally:
            self.connected = False
            self.mode = "SIMULATION"
