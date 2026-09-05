from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from sqlalchemy.orm import Session
from .models import MarketSnapshot

FRESHNESS_THRESHOLD_MINUTES = 15  # Data older than 15 minutes is stale

def check_data_freshness(db: Session, symbol: str) -> Dict[str, Any]:
    """Check if data for a symbol is fresh or stale"""
    
    latest = db.query(MarketSnapshot).filter(
        MarketSnapshot.symbol == symbol
    ).order_by(MarketSnapshot.timestamp.desc()).first()
    
    if not latest:
        return {
            "symbol": symbol,
            "status": "no_data",
            "message": "No data available for this symbol"
        }
    
    # Use timezone-aware current time
    now = datetime.now(timezone.utc)
    
    # Ensure latest.timestamp is timezone-aware
    if latest.timestamp.tzinfo is None:
        # If naive, make it aware (assuming UTC)
        latest_timestamp = latest.timestamp.replace(tzinfo=timezone.utc)
    else:
        latest_timestamp = latest.timestamp
    
    age_seconds = (now - latest_timestamp).total_seconds()
    age_minutes = age_seconds / 60
    
    if age_minutes > FRESHNESS_THRESHOLD_MINUTES:
        return {
            "symbol": symbol,
            "status": "stale",
            "age_minutes": round(age_minutes, 1),
            "last_updated": latest_timestamp,
            "message": f"Data delayed — last updated {round(age_minutes)}m ago"
        }
    else:
        return {
            "symbol": symbol,
            "status": "fresh",
            "age_minutes": round(age_minutes, 1),
            "last_updated": latest_timestamp,
            "message": "Data is current"
        }

def get_watchlist_freshness(db: Session, user_id: int) -> Dict[str, Any]:
    """Check freshness for all stocks in user's watchlist"""
    
    from .models import Watchlist, WatchlistStock
    
    watchlist = db.query(Watchlist).filter(Watchlist.user_id == user_id).first()
    if not watchlist:
        return {"status": "no_watchlist", "stocks": []}
    
    stocks = db.query(WatchlistStock).filter(
        WatchlistStock.watchlist_id == watchlist.id
    ).all()
    
    results = {}
    for stock in stocks:
        results[stock.symbol] = check_data_freshness(db, stock.symbol)
    
    # Check if any data is stale
    has_stale = any(r.get("status") == "stale" for r in results.values())
    
    # Find the latest updated time
    last_updated = None
    for r in results.values():
        if r.get("last_updated"):
            if last_updated is None or r["last_updated"] > last_updated:
                last_updated = r["last_updated"]
    
    return {
        "status": "has_stale" if has_stale else "all_fresh",
        "last_updated": last_updated,
        "stocks": results
    }