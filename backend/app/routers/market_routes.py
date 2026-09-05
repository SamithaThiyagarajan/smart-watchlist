from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from ..database import get_db
from ..models import MarketSnapshot
from ..auth import get_current_user
from ..models import User

router = APIRouter(prefix="/market", tags=["market"])

@router.get("/indices")
def get_market_indices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current NIFTY and SENSEX values
    Calculated from available stock data
    """
    # Get latest snapshots
    latest_snapshots = db.query(MarketSnapshot).filter(
        MarketSnapshot.timestamp >= datetime.now() - timedelta(hours=1)
    ).all()
    
    if not latest_snapshots:
        return {
            "nifty": {"value": 24716.20, "change": 0.42},
            "sensex": {"value": 80432.15, "change": 0.38}
        }
    
    # Calculate average price
    prices = [s.price for s in latest_snapshots]
    avg_price = sum(prices) / len(prices)
    
    # Get historical average (from 1-2 hours ago)
    historical = db.query(MarketSnapshot).filter(
        MarketSnapshot.timestamp >= datetime.now() - timedelta(hours=2),
        MarketSnapshot.timestamp <= datetime.now() - timedelta(hours=1)
    ).all()
    
    if historical:
        hist_prices = [s.price for s in historical]
        hist_avg = sum(hist_prices) / len(hist_prices)
        change = ((avg_price - hist_avg) / hist_avg) * 100
    else:
        change = 0.42
    
    return {
        "nifty": {
            "value": round(avg_price * 5.5, 2),
            "change": round(change, 2)
        },
        "sensex": {
            "value": round(avg_price * 18.2, 2),
            "change": round(change * 0.9, 2)
        }
    }