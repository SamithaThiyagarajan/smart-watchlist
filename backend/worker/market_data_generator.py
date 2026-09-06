import random
import asyncio
from sqlalchemy.orm import Session
import sys
from datetime import datetime, timedelta, timezone
import os

# Add parent directory to path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import MarketSnapshot, MarketEvent

# Mock stock symbols
STOCKS = [
    "RELIANCE", "TCS", "HDFC", "INFY", "HINDUNILVR", 
    "ICICIBANK", "KOTAKBANK", "SBIN", "BHARTIARTL", 
    "ITC", "LIC", "WIPRO", "HCLTECH", "SUNPHARMA"
]

# Initial prices (in rupees)
INITIAL_PRICES = {
    "RELIANCE": 2850.50,
    "TCS": 3950.00,
    "HDFC": 1650.75,
    "INFY": 1450.25,
    "HINDUNILVR": 2450.00,
    "ICICIBANK": 1120.50,
    "KOTAKBANK": 1850.30,
    "SBIN": 750.80,
    "BHARTIARTL": 1200.00,
    "ITC": 480.50,
    "LIC": 950.00,
    "WIPRO": 550.25,
    "HCLTECH": 1350.00,
    "SUNPHARMA": 1050.00
}

# Current prices (will be updated)
current_prices = INITIAL_PRICES.copy()

# Mock events to inject
EVENT_TYPES = [
    "earnings",
    "dividend", 
    "acquisition",
    "management_change",
    "regulatory_action",
    "credit_rating_change",
    "stock_split",
    "bonus",
    "trading_halt",
    "insider_transaction"
]

EVENT_PAYLOADS = {
    "earnings": [
        {"revenue": random.randint(10000, 50000), "profit": random.randint(1000, 10000), "beat_estimate": random.choice([True, False])},
        {"revenue": random.randint(8000, 40000), "profit": random.randint(500, 8000), "beat_estimate": random.choice([True, False])}
    ],
    "dividend": [
        {"amount": round(random.uniform(5, 50), 2), "ex_date": str(datetime.now() + timedelta(days=random.randint(10, 60)))},
        {"amount": round(random.uniform(2, 30), 2), "ex_date": str(datetime.now() + timedelta(days=random.randint(10, 60)))}
    ],
    "acquisition": [
        {"target": random.choice(STOCKS), "value": random.randint(500, 5000), "type": "stock"},
        {"target": random.choice(STOCKS), "value": random.randint(1000, 10000), "type": "cash"}
    ],
    "management_change": [
        {"position": "CEO", "new_appointee": f"Person_{random.randint(1, 100)}"},
        {"position": "CFO", "new_appointee": f"Person_{random.randint(1, 100)}"},
        {"position": "Board Member", "new_appointee": f"Person_{random.randint(1, 100)}"}
    ],
    "regulatory_action": [
        {"agency": "SEBI", "action": "investigation", "status": "ongoing"},
        {"agency": "RBI", "action": "compliance_issue", "status": "resolved"},
        {"agency": "SEBI", "action": "warning", "status": "pending"}
    ],
    "credit_rating_change": [
        {"agency": "CRISIL", "old_rating": "AAA", "new_rating": "AA+"},
        {"agency": "CRISIL", "old_rating": "AA", "new_rating": "AA+"},
        {"agency": "ICRA", "old_rating": "AAA", "new_rating": "AAA-"}
    ],
    "stock_split": [
        {"ratio": "2:1", "effective_date": str(datetime.now() + timedelta(days=30))},
        {"ratio": "3:1", "effective_date": str(datetime.now() + timedelta(days=45))},
        {"ratio": "5:1", "effective_date": str(datetime.now() + timedelta(days=60))}
    ],
    "bonus": [
        {"ratio": "1:1", "effective_date": str(datetime.now() + timedelta(days=20))},
        {"ratio": "2:1", "effective_date": str(datetime.now() + timedelta(days=30))}
    ],
    "trading_halt": [
        {"reason": "volatility", "duration": "30 minutes"},
        {"reason": "news_pending", "duration": "1 hour"},
        {"reason": "circuit_breaker", "duration": "15 minutes"}
    ],
    "insider_transaction": [
        {"insider": f"Person_{random.randint(1, 50)}", "type": "buy", "shares": random.randint(1000, 50000)},
        {"insider": f"Person_{random.randint(1, 50)}", "type": "sell", "shares": random.randint(1000, 50000)}
    ]
}

def generate_price_change(current_price):
    """Generate a random price change (random walk)"""
    # Daily volatility around 0.5-2%
    volatility = random.uniform(0.005, 0.02)
    change_percent = random.normalvariate(0, volatility)
    new_price = current_price * (1 + change_percent)
    
    # Occasionally add a larger move (1% chance)
    if random.random() < 0.01:
        large_move = random.uniform(-0.05, 0.05)
        new_price = current_price * (1 + large_move)
    
    # Ensure price doesn't go negative
    return max(new_price, 10)

def generate_volume(symbol):
    """Generate random volume"""
    base_volume = {
        "RELIANCE": 5000000,
        "TCS": 3000000,
        "HDFC": 4000000,
        "INFY": 2500000,
        "HINDUNILVR": 2000000,
        "ICICIBANK": 6000000,
        "KOTAKBANK": 3000000,
        "SBIN": 8000000,
        "BHARTIARTL": 2500000,
        "ITC": 3500000,
        "LIC": 1500000,
        "WIPRO": 2000000,
        "HCLTECH": 1800000,
        "SUNPHARMA": 2200000
    }.get(symbol, 2000000)
    
    volume = int(base_volume * random.uniform(0.5, 1.5))
    
    # Occasionally add volume spikes (5% chance)
    if random.random() < 0.05:
        volume = int(volume * random.uniform(3, 8))  # 3-8x normal volume
    
    return volume

def generate_event():
    """Generate a mock market event"""
    symbol = random.choice(STOCKS)
    event_type = random.choice(EVENT_TYPES)
    
    # Get random payload for event type
    payloads = EVENT_PAYLOADS.get(event_type, [{"detail": "Event occurred"}])
    payload = random.choice(payloads)
    
    return {
        "symbol": symbol,
        "type": event_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc)
    }

def generate_market_snapshot():
    """Generate a market snapshot for all stocks"""
    global current_prices
    
    snapshots = []
    for symbol in STOCKS:
        current_price = current_prices.get(symbol, 1000)
        new_price = generate_price_change(current_price)
        current_prices[symbol] = new_price
        
        snapshot = MarketSnapshot(
            symbol=symbol,
            price=round(new_price, 2),
            volume=generate_volume(symbol),
            timestamp=datetime.now(timezone.utc),
            source="mock_feed"
        )
        snapshots.append(snapshot)
    
    return snapshots

def save_market_snapshots(db: Session, snapshots):
    """Save snapshots to database"""
    for snapshot in snapshots:
        db.add(snapshot)
    db.commit()

def save_market_events(db: Session, events):
    """Save events to database"""
    for event_data in events:
        event = MarketEvent(
            symbol=event_data["symbol"],
            type=event_data["type"],
            payload=event_data["payload"],
            timestamp=event_data["timestamp"]
        )
        db.add(event)
    db.commit()
    
async def run_market_generator():
    """Main loop for generating mock market data"""
    print("Starting market data generator...")
    
    cycle_count = 0
    
    while True:
        try:
            db = SessionLocal()
            
            # Generate market snapshots
            snapshots = generate_market_snapshot()
            save_market_snapshots(db, snapshots)
            print(f"Generated {len(snapshots)} snapshots at {datetime.now()}")
            
            # Occasionally generate events (50% chance each cycle)
            if random.random() < 0.5:
                num_events = random.randint(1, 3)
                events = [generate_event() for _ in range(num_events)]
                save_market_events(db, events)
                print(f"Generated {num_events} events at {datetime.now()}")
                
                # 👇 NEW: Auto-score events right after generating them
                try:
                    from app.significance_engine import process_events
                    process_events()
                    print(f"✅ Scored events at {datetime.now()}")
                except Exception as e:
                    print(f"⚠️ Scoring error: {e}")
            
            db.close()
            
            # Wait 5-15 seconds before next update
            await asyncio.sleep(random.randint(5, 15))
            
        except Exception as e:
            print(f"Error in market generator: {e}")
            await asyncio.sleep(60)  # Wait a minute before retrying
if __name__ == "__main__":
    asyncio.run(run_market_generator())