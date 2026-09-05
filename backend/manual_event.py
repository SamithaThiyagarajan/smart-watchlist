
import random
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import MarketEvent
from worker.market_data_generator import STOCKS, EVENT_TYPES, EVENT_PAYLOADS, generate_event

def create_manual_events(count=5):
    """Manually create events for testing"""
    db = SessionLocal()
    
    for i in range(count):
        event_data = generate_event()
        event = MarketEvent(
            symbol=event_data["symbol"],
            type=event_data["type"],
            payload=event_data["payload"],
            timestamp=datetime.now()
        )
        db.add(event)
    
    db.commit()
    db.close()
    print(f"✅ Created {count} manual events!")

if __name__ == "__main__":
    create_manual_events(10)
    print("Check the database to see the events")