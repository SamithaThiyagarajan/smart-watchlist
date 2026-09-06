import random
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
import sys
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

# Opening prices (reset daily)
opening_prices = INITIAL_PRICES.copy()
current_prices = INITIAL_PRICES.copy()

# Market hours check
def is_market_open():
    """Check if market is currently open (9:15 AM - 3:30 PM IST, Mon-Fri)"""
    now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)  # Convert to IST
    weekday = now.weekday()
    minutes = now.hour * 60 + now.minute
    open_minutes = 9 * 60 + 15
    close_minutes = 15 * 60 + 30
    return weekday < 5 and open_minutes <= minutes <= close_minutes

# Mock events
EVENT_TYPES = [
    "earnings", "dividend", "acquisition", "management_change",
    "regulatory_action", "credit_rating_change", "stock_split",
    "bonus", "trading_halt", "insider_transaction"
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
        {"ratio": "3:1", "effective_date": str(datetime.now() + timedelta(days=45))}
    ],
    "bonus": [
        {"ratio": "1:1", "effective_date": str(datetime.now() + timedelta(days=20))},
        {"ratio": "2:1", "effective_date": str(datetime.now() + timedelta(days=30))}
    ],
    "trading_halt": [
        {"reason": "volatility", "duration": "30 minutes"},
        {"reason": "news_pending", "duration": "1 hour"}
    ],
    "insider_transaction": [
        {"insider": f"Person_{random.randint(1, 50)}", "type": "buy", "shares": random.randint(1000, 50000)},
        {"insider": f"Person_{random.randint(1, 50)}", "type": "sell", "shares": random.randint(1000, 50000)}
    ]
}

def generate_next_price(current_price, opening_price, daily_volatility=0.015):
    """Generate next price with mean reversion to prevent runaway drift"""
    # Random tick move (daily volatility)
    random_move = random.gauss(0, daily_volatility)
    # Mean reversion: pull back toward opening price
    reversion_strength = 0.05
    reversion = (opening_price - current_price) / opening_price * reversion_strength
    new_price = current_price * (1 + random_move + reversion)
    return round(new_price, 2)

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
    if random.random() < 0.05:
        volume = int(volume * random.uniform(3, 8))
    return volume

def generate_event():
    """Generate a mock market event"""
    symbol = random.choice(STOCKS)
    event_type = random.choice(EVENT_TYPES)
    payloads = EVENT_PAYLOADS.get(event_type, [{"detail": "Event occurred"}])
    payload = random.choice(payloads)
    return {
        "symbol": symbol,
        "type": event_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc)
    }

def generate_market_snapshot():
    """Generate a market snapshot with mean reversion"""
    global current_prices, opening_prices
    
    # Check if it's a new day (reset opening prices)
    current_hour = datetime.now(timezone.utc).hour
    if current_hour >= 3 and current_hour < 4:  # Around 9 AM IST
        opening_prices = INITIAL_PRICES.copy()
    
    snapshots = []
    for symbol in STOCKS:
        current_price = current_prices.get(symbol, 1000)
        opening_price = opening_prices.get(symbol, current_price)
        
        # Generate next price with mean reversion
        new_price = generate_next_price(current_price, opening_price)
        current_prices[symbol] = new_price
        
        snapshot = MarketSnapshot(
            symbol=symbol,
            price=new_price,
            volume=generate_volume(symbol),
            timestamp=datetime.now(timezone.utc),
            source="mock_feed"
        )
        snapshots.append(snapshot)
    
    return snapshots

def save_market_snapshots(db: Session, snapshots):
    for snapshot in snapshots:
        db.add(snapshot)
    db.commit()

def save_market_events(db: Session, events):
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
    
    while True:
        try:
            # Check if market is open
            if not is_market_open():
                print(f"Market closed at {datetime.now(timezone.utc)}. Waiting...")
                await asyncio.sleep(60)
                continue
            
            db = SessionLocal()
            
            # Generate snapshots
            snapshots = generate_market_snapshot()
            save_market_snapshots(db, snapshots)
            print(f"Generated {len(snapshots)} snapshots at {datetime.now(timezone.utc)}")
            
            # Generate events (10% chance)
            if random.random() < 0.1:
                num_events = random.randint(1, 3)
                events = [generate_event() for _ in range(num_events)]
                save_market_events(db, events)
                print(f"Generated {num_events} events at {datetime.now(timezone.utc)}")
                
                # Auto-score events
                try:
                    from app.significance_engine import process_events
                    process_events()
                    print(f"Scored events at {datetime.now(timezone.utc)}")
                except Exception as e:
                    print(f"Scoring error: {e}")
            
            db.close()
            
            # Wait 10-30 seconds
            await asyncio.sleep(random.randint(10, 30))
            
        except Exception as e:
            print(f"Error in market generator: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(run_market_generator())