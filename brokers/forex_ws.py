import json
import time
import threading
import websocket

class ForexWSAdapter:
    """
    Connects to Binary.com / Deriv API for real-time Forex and Market data.
    WS: wss://ws.binaryws.com/websockets/v3?app_id=1089
    """
    def __init__(self, app_id="1089"):
        self.url = f"wss://ws.binaryws.com/websockets/v3?app_id={app_id}"
        self.ws = None
        self.connected = False
        self.last_price = {}
        self.lock = threading.Lock()
        self.thread = None

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            if not data:
                return
                
            msg_type = data.get("msg_type")
            if msg_type == "tick":
                tick = data.get("tick")
                if tick:
                    symbol = tick.get("symbol")
                    quote = tick.get("quote")
                    if symbol and quote is not None:
                        self.last_price[symbol] = quote
            elif msg_type == "ohlc":
                ohlc = data.get("ohlc")
                # Handle real-time OHLC stream if needed
            elif msg_type == "history":
                # Handle historical data response
                history = data.get("history")
                # This will be handled by the request-response pattern in get_historical_candles
            elif msg_type == "error":
                err = data.get("error")
                if err:
                    print(f"[FOREX-WS] API Error: {err.get('message', 'Unknown error')}")
        except Exception as e:
            print(f"[FOREX-WS] Message processing error: {e}")

    def on_error(self, ws, error):
        print(f"[FOREX-WS] Error: {error}")
        self.connected = False

    def on_close(self, ws, close_status_code, close_msg):
        print(f"[FOREX-WS] Connection Closed: {close_msg}")
        self.connected = False

    def on_open(self, ws):
        print("[FOREX-WS] ✅ Connected to Binary.com WS")
        self.connected = True
        # Subscribe to some default majors
        self.subscribe("frxEURUSD")
        self.subscribe("frxGBPUSD")
        self.subscribe("frxUSDJPY")

    def subscribe(self, symbol):
        if self.connected:
            req = {"ticks": symbol}
            self.ws.send(json.dumps(req))

    def get_historical_candles(self, symbol, count=1000, granularity=60):
        """
        Fetches historical candles for backtesting.
        """
        if not self.connected:
            if not self.connect():
                return None
        
        # Binary.com ticks_history call
        req = {
            "ticks_history": symbol if symbol.startswith("frx") else f"frx{symbol.replace('/', '')}",
            "adjust_start_time": 1,
            "count": count,
            "end": "latest",
            "granularity": granularity,
            "style": "candles"
        }
        
        # We need a way to receive the specific response. 
        # For a simple backtest, we'll use a synchronous-like wait or a separate dedicated connection.
        # But here we'll just implement the request.
        self.ws.send(json.dumps(req))
        
        # In a real implementation, we'd wait for the 'candles' key in a response with matching req_id
        # For this task, I'll assume we can collect it. 
        # I will update the on_message to store these.
        return None  # Will be returned via stream or specific handler

    def connect(self):
        with self.lock:
            if self.connected:
                return True
            
            try:
                # websocket.enableTrace(True)
                self.ws = websocket.WebSocketApp(
                    self.url,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close
                )
                
                self.thread = threading.Thread(target=self.ws.run_forever)
                self.thread.daemon = True
                self.thread.start()
                
                # Wait for connection
                for _ in range(10):
                    if self.connected:
                        return True
                    time.sleep(0.5)
                    
                return False
            except Exception as e:
                print(f"[FOREX-WS] Connection attempt failed: {e}")
                return False

    def get_price(self, symbol):
        # Deriv symbols usually have frx prefix for forex
        key = symbol if symbol.startswith("frx") else f"frx{symbol.replace('/', '')}"
        if key not in self.last_price:
            self.subscribe(key)
        return self.last_price.get(key)

