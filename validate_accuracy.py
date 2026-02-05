import os
import sys
import asyncio
import time
from dotenv import load_dotenv

# Enhance path to find local modules
sys.path.append(os.path.join(os.path.dirname(__file__), "pyquotex"))
from brokers.quotex_pyquotex import QuotexPyQuotexAdapter
from engine.enhanced import EnhancedEngine

# Load ENV for Credentials
load_dotenv()

async def run_backtest():
    print("="*60)
    print("🚀 QUANTUM X PRO - ACCURACY VALIDATION SYSTEM")
    print("="*60)
    
    # 1. Initialize Adapter
    print("[INIT] Connecting to Quotex Broker...")
    adapter = QuotexPyQuotexAdapter() # Reads from os.getenv
    
    start_conn = time.time()
    connected = await adapter.connect()
    conn_time = time.time() - start_conn
    
    if not connected:
        print("[ERROR] ❌ Could not connect to Quotex. Check credentials in .env or internet.")
        return

    print(f"[SUCCESS] ✅ Connected in {conn_time:.2f}s")
    print(f"[ACCOUNT] Balance: ${adapter.balance} ({adapter.account_type})")
    
    # 2. Setup Engine
    engine = EnhancedEngine()
    
    # 3. Define Test Assets (Comprehensive List)
    assets = [
        "EUR/USD", "GBP/USD", "USD/JPY", 
        "EUR/USD (OTC)", "GBP/USD (OTC)", "USD/JPY (OTC)",
        "AUD/CAD (OTC)", "NZD/USD (OTC)", "USD/HKD (OTC)", 
        "USD/BRL (OTC)"
    ]
    
    results = []
    
    print("\n[TEST] Starting Analysis on 100 Candles per Asset...")
    
    for asset in assets:
        print(f"\n🔹 Analyzing {asset}...")
        
        # Speed Test: Fetching
        t0 = time.time()
        candles = await adapter.get_candles(asset, 60, 400) # 400 candles, 1 min
        fetch_time = time.time() - t0
        
        if not candles or len(candles) < 50:
            print(f"   ⚠️  Failed to fetch sufficient data for {asset} (Time: {fetch_time:.2f}s)")
            continue
            
        print(f"   ✅ Fetched {len(candles)} candles in {fetch_time:.2f}s")
        
        wins = 0
        losses = 0
        draws = 0
        skipped = 0
        
        # Backtest Logic:
        print("   ⏳ Running Engine Simulation...")
        
        for i in range(30, len(candles)-1):
            history_slice = candles[:i+1]
            actual_next_candle = candles[i+1]
            
            # Predict
            direction, confidence, strategy = engine.analyze(
                broker="QUOTEX", 
                market=asset, 
                timeframe=60, 
                candles=history_slice, 
                entry_time=None
            )
            
            # STRICT FILTER: Only count high confidence signals
            if direction in ["CALL", "PUT"] and confidence >= 80: 
                open_p = actual_next_candle['open']
                close_p = actual_next_candle['close']
                
                outcome = "DRAW"
                if direction == "CALL":
                    if close_p > open_p: outcome = "WIN"
                    elif close_p < open_p: outcome = "LOSS"
                elif direction == "PUT":
                    if close_p < open_p: outcome = "WIN"
                    elif close_p > open_p: outcome = "LOSS"
                
                if outcome == "WIN": wins += 1
                elif outcome == "LOSS": losses += 1
                else: draws += 1
            else:
                skipped += 1
                
        total_trades = wins + losses + draws
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        print(f"   📊 Result for {asset}:")
        print(f"      Signals: {total_trades} (Skipped {skipped} neutral/low conf)")
        print(f"      Wins:    {wins}")
        print(f"      Losses:  {losses}")
        print(f"      Draws:  {draws}")
        print(f"      Accuracy: {win_rate:.2f}%")
        
        results.append({
            "asset": asset,
            "accuracy": win_rate,
            "trades": total_trades,
            "fetch_time": fetch_time
        })

    # 4. Final Summary
    print("\n" + "="*60)
    print("   GENOME ACCURACY REPORT (AT THIS MOMENT)")
    print("="*60)
    
    avg_acc = 0
    if results:
        avg_acc = sum(r['accuracy'] for r in results) / len(results)
    
    for res in results:
        status = "EXCELLENT" if res['accuracy'] > 80 else ("GOOD" if res['accuracy'] > 60 else "POOR")
        print(f"Asset: {res['asset']:<15} | Acc: {res['accuracy']:.2f}% ({res['trades']} trades) | {status}")
        
    print("-" * 60)
    print(f"OVERALL SYSTEM ACCURACY: {avg_acc:.2f}%")
    print(f"SIGNAL SPEED STATUS: {'FAST' if all(r['fetch_time'] < 5 for r in results) else 'SLOW'}")
    print("="*60)
    
    await adapter.disconnect()

if __name__ == "__main__":
    asyncio.run(run_backtest())
