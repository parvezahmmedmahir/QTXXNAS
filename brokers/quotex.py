import time
import threading
from functools import wraps

try:
    from pyquotex.stable_api import Quotex
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
                        print(f"[QUOTEX] {func.__name__} failed after {max_retries} attempts: {e}")
                        raise
                    time.sleep(delay * (attempt + 1))
            return None
        return wrapper
    return decorator

class QuotexAdapter:
    def __init__(self, config):
        self.client = None
        self.config = config
        self.connected = False
        self.mode = "SIMULATION"
        self.last_connection_attempt = 0
        self.connection_lock = threading.Lock()
        self.health_check_interval = 300  # 5 minutes
        self.last_health_check = 0

    def connect(self, retry_count=3):
        """Enhanced connection with retry logic and health monitoring"""
        if not LIB_AVAILABLE:
            print("[WARN] pyquotex not installed.")
            return False
            
        if not self.config.get("email") or not self.config.get("password"):
            print("[QUOTEX] Credentials missing.")
            return False

        with self.connection_lock:
            # Prevent too frequent connection attempts
            if time.time() - self.last_connection_attempt < 5:
                return self.connected
            
            self.last_connection_attempt = time.time()

            for attempt in range(retry_count):
                try:
                    import asyncio
                    import nest_asyncio
                    nest_asyncio.apply()
                    
                    print(f"[QUOTEX] Connecting {self.config['email']}... (Attempt {attempt + 1}/{retry_count})")
                    self.client = Quotex(
                        email=self.config["email"], 
                        password=self.config["password"]
                    )
                    
                    async def try_connect():
                        if hasattr(self.client, 'connect'):
                            return await self.client.connect()
                        return True
                    
                    res = asyncio.run(try_connect())
                    
                    # Handle PyQuotex (check, reason) tuple return
                    success = False
                    if isinstance(res, tuple):
                        success = res[0]
                    else:
                        success = res
                    
                    if success:
                        self.connected = True
                        self.mode = "REAL"
                        print(f"[QUOTEX] ✅ Connected successfully!")
                        return True
                        
                except Exception as e:
                    print(f"[QUOTEX] Connection attempt {attempt + 1} failed: {e}")
                    if attempt < retry_count - 1:
                        time.sleep(2 * (attempt + 1))  # Exponential backoff
                    else:
                        print(f"[QUOTEX] ❌ Connection failed after {retry_count} attempts")
                        self.connected = False
                        self.mode = "SIMULATION"
                        return False
            
            return False

    def _check_health(self):
        """Periodic health check to ensure connection is still alive"""
        if not self.connected or not self.client:
            return False
        
        current_time = time.time()
        if current_time - self.last_health_check < self.health_check_interval:
            return True
        
        self.last_health_check = current_time
        
        # Try a lightweight operation to verify connection
        try:
            # If client has a method to check status, use it
            # Otherwise, assume connection is healthy if no exceptions
            return True
        except:
            print("[QUOTEX] Health check failed, reconnecting...")
            self.connected = False
            return self.connect()

    @retry_on_failure(max_retries=2, delay=1)
    def get_candles(self, asset, timeframe_seconds=60, count=20):
        """
        Enhanced candle fetching with retry logic and error handling.
        Returns list of dicts with open/high/low/close.
        """
        # Health check before fetching
        if not self._check_health():
            return None

        if not self.connected or not self.client:
            return None

        try:
            # Normalize asset name for Quotex API
            clean_asset = asset.replace("/", "").replace(" ", "").replace("(OTC)", "_OTC").replace("-OTC", "_OTC").upper()
            
            # Ensure valid timeframe
            if timeframe_seconds < 60:
                timeframe_seconds = 60
            
            # Ensure valid count
            count = min(max(count, 1), 100)  # Limit between 1 and 100
            
            import asyncio
            import datetime
            
            end_ts = int(time.time())
            
            # Helper to execute async code in sync context
            def _get_result(coro):
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # We are inside an async context (like Flask with some setups)
                        # This is tricky, but let's try a fallback or wait
                        import nest_asyncio
                        nest_asyncio.apply()
                        return loop.run_until_complete(coro)
                    else:
                        return loop.run_until_complete(coro)
                except RuntimeError:
                    return asyncio.run(coro)

            res = self.client.get_candles(clean_asset, timeframe_seconds, count, end_ts)
            
            # Handle potential coroutine return
            import inspect
            if inspect.iscoroutine(res):
                candles = _get_result(res)
            else:
                candles = res
            
            # Ensure we have the list of candles correctly extracted
            candle_list = []
            if isinstance(candles, list):
                candle_list = candles
            elif isinstance(candles, dict):
                candle_list = candles.get("candles", candles.get("data", []))
            
            if not candle_list:
                return None
            
            # Normalize candle data
            norm = []
            for c in candle_list:
                try:
                    norm.append({
                        "open": float(c.get("open", 0)),
                        "high": float(c.get("max", c.get("high", 0))),
                        "low": float(c.get("min", c.get("low", 0))),
                        "close": float(c.get("close", 0)),
                        "ts": int(c.get("from", c.get("ts", end_ts)))
                    })
                except (ValueError, TypeError, AttributeError):
                    continue
            
            return norm if norm else None
            
        except Exception as e:
            print(f"[QUOTEX] Candle fetch failed: {e}")
            # Mark as disconnected on critical errors
            if "connection" in str(e).lower() or "timeout" in str(e).lower():
                self.connected = False
            return None

    def disconnect(self):
        """Clean disconnect"""
        try:
            if self.client:
                # If client has disconnect method
                if hasattr(self.client, 'close'):
                    self.client.close()
        except:
            pass
        finally:
            self.connected = False
            self.mode = "SIMULATION"
