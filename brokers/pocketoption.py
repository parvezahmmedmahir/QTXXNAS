import threading
import time
from functools import wraps

try:
    import websocket
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
                        print(f"[POCKET] {func.__name__} failed after {max_retries} attempts: {e}")
                        raise
                    time.sleep(delay * (attempt + 1))
            return None
        return wrapper
    return decorator

class PocketOptionAdapter:
    def __init__(self, config):
        self.config = config
        self.ws = None
        self.connected = False
        self.mode = "SIMULATION"
        self.last_connection_attempt = 0
        self.connection_lock = threading.Lock()
        self.ws_thread = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5

    def on_open(self, ws):
        """WebSocket connection opened"""
        try:
            ssid = self.config.get("ssid", "")
            if ssid:
                auth_payload = f'42["auth", {{"session": "{ssid}", "userAgent": "Mozilla/5.0"}}]'
                ws.send(auth_payload)
                print("[POCKET] Authentication sent")
        except Exception as e:
            print(f"[POCKET] Auth error: {e}")

    def on_error(self, ws, error):
        """WebSocket error handler"""
        print(f"[POCKET] WebSocket error: {error}")
        self.connected = False

    def on_close(self, ws, close_status_code, close_msg):
        """WebSocket close handler with auto-reconnect"""
        print(f"[POCKET] WebSocket closed: {close_status_code}")
        self.connected = False
        
        # Auto-reconnect logic
        if self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            print(f"[POCKET] Attempting reconnect ({self.reconnect_attempts}/{self.max_reconnect_attempts})...")
            time.sleep(5)
            self.connect()

    def connect(self, retry_count=3):
        """Enhanced connection with retry and auto-reconnect"""
        with self.connection_lock:
            if time.time() - self.last_connection_attempt < 5:
                return self.connected
            
            self.last_connection_attempt = time.time()

            # 1. Try Real Connection if SSID exists
            if self.config.get("ssid") and LIB_AVAILABLE:
                for attempt in range(retry_count):
                    try:
                        print(f"[POCKET] Connecting... (Attempt {attempt + 1}/{retry_count})")
                        
                        def run_socket():
                            try:
                                self.ws = websocket.WebSocketApp(
                                    self.config.get("platform_url", "wss://api-fin.pocketoption.com/socket.io/?EIO=3&transport=websocket"),
                                    on_open=self.on_open,
                                    on_error=self.on_error,
                                    on_close=self.on_close
                                )
                                self.connected = True
                                self.mode = "REAL"
                                self.reconnect_attempts = 0
                                print("[POCKET] ✅ WebSocket connected!")
                                self.ws.run_forever()
                            except Exception as e:
                                print(f"[POCKET] WebSocket error: {e}")
                                self.connected = False
                        
                        if not self.ws_thread or not self.ws_thread.is_alive():
                            self.ws_thread = threading.Thread(target=run_socket, daemon=True)
                            self.ws_thread.start()
                            time.sleep(2)  # Wait for connection
                            
                            if self.connected:
                                return True
                                
                    except Exception as e:
                        print(f"[POCKET] Connection attempt {attempt + 1} failed: {e}")
                        if attempt < retry_count - 1:
                            time.sleep(2 * (attempt + 1))

            # 2. Fallback to Guest/Simulation Mode
            print("[POCKET] SSID missing or connection failed. Activating Guest Simulation Mode.")
            self.connected = True
            self.mode = "SIMULATION"
            return True

    def get_candles(self, asset, timeframe_seconds=60, count=20):
        """
        Enhanced candle fetching.
        Note: PocketOption uses WebSocket streams, so this is a placeholder.
        Real implementation would require WebSocket message handling.
        """
        if not self.connected:
            return None

        if self.mode == "REAL" and self.ws:
            # WebSocket-based data fetching would go here
            # This requires implementing WebSocket message handlers
            # For now, return None to trigger fallback
            return None

        return None

    def disconnect(self):
        """Clean disconnect"""
        try:
            if self.ws:
                self.ws.close()
        except:
            pass
        finally:
            self.connected = False
            self.mode = "SIMULATION"
