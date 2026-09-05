from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime  # ← ADD THIS
from ..database import get_db
from ..models import User, Watchlist, WatchlistStock, MarketSnapshot
from ..schemas import WatchlistStockAdd, WatchlistStockOut
from ..auth import get_current_user
from ..data_freshness import check_data_freshness, get_watchlist_freshness
from ..data_providers import DataPoint, DataConflictResolver, DataProvider
router = APIRouter(prefix="/watchlist", tags=["watchlist"])

@router.get("/{symbol}/price")
def get_stock_price(
    symbol: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    include_conflict: bool = Query(False, description="Include conflict resolution details")
):
    """
    Get stock price with conflict resolution from multiple sources
    """
    # Get snapshots from different sources
    sources = [DataProvider.MOCK.value, DataProvider.REUTERS.value, DataProvider.BLOOMBERG.value]
    
    data_points = []
    for source in sources:
        snapshot = db.query(MarketSnapshot).filter(
            MarketSnapshot.symbol == symbol.upper(),
            MarketSnapshot.source == source
        ).order_by(MarketSnapshot.timestamp.desc()).first()
        
        if snapshot:
            data_points.append(DataPoint(
                symbol=snapshot.symbol,
                price=snapshot.price,
                volume=snapshot.volume,
                timestamp=snapshot.timestamp,
                source=snapshot.source
            ))
    
    if not data_points:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No data found for {symbol}"
        )
    
    # Resolve conflicts
    resolver = DataConflictResolver()
    resolution = resolver.resolve(data_points)
    
    response = {
        "symbol": symbol.upper(),
        "price": round(resolution.resolved_price, 2),
        "primary_source": resolution.sources[0] if resolution.sources else None,
        "status": resolution.status,
        "message": resolution.message,
        "timestamp": datetime.now().isoformat()
    }
    
    if include_conflict and resolution.conflict:
        response["conflict"] = {
            "primary_price": round(resolution.primary_price, 2),
            "secondary_prices": {
                s: round(p, 2) for s, p in resolution.secondary_prices.items()
            },
            "confidence": resolution.confidence,
            "sources": resolution.sources
        }
    
    return response


@router.get("/{symbol}/sources")
def get_source_comparison(
    symbol: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Compare prices from all available sources for a symbol
    """
    snapshots = db.query(MarketSnapshot).filter(
        MarketSnapshot.symbol == symbol.upper()
    ).order_by(MarketSnapshot.source, MarketSnapshot.timestamp.desc()).all()
    
    # Get latest from each source
    sources = {}
    for snapshot in snapshots:
        if snapshot.source not in sources:
            sources[snapshot.source] = {
                "price": snapshot.price,
                "volume": snapshot.volume,
                "timestamp": snapshot.timestamp.isoformat()
            }
    
    return {
        "symbol": symbol.upper(),
        "sources": sources,
        "total_sources": len(sources)
    }


@router.options("/")
@router.options("/{symbol}")
def options_handler():
    """Handle CORS preflight requests"""
    return Response(status_code=200)

@router.get("/", response_model=List[WatchlistStockOut])
def get_watchlist(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all stocks in the user's watchlist"""
    watchlist = db.query(Watchlist).filter(Watchlist.user_id == current_user.id).first()
    if not watchlist:
        return []
    
    stocks = db.query(WatchlistStock).filter(WatchlistStock.watchlist_id == watchlist.id).all()
    return [WatchlistStockOut(
        symbol=stock.symbol,
        quantity=stock.quantity,
        reference_price=stock.reference_price,
        added_at=stock.added_at
    ) for stock in stocks]

@router.post("/", response_model=WatchlistStockOut, status_code=status.HTTP_201_CREATED)
def add_stock(
    stock_data: WatchlistStockAdd,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a stock to the user's watchlist with quantity"""
    # Get or create watchlist
    watchlist = db.query(Watchlist).filter(Watchlist.user_id == current_user.id).first()
    if not watchlist:
        watchlist = Watchlist(user_id=current_user.id)
        db.add(watchlist)
        db.commit()
        db.refresh(watchlist)
    
    # Check if stock already exists
    existing = db.query(WatchlistStock).filter(
        WatchlistStock.watchlist_id == watchlist.id,
        WatchlistStock.symbol == stock_data.symbol.upper()
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stock already in watchlist"
        )
    
    # Get reference price (if not provided, use latest snapshot)
    ref_price = stock_data.reference_price
    if ref_price is None:
        latest_snapshot = db.query(MarketSnapshot).filter(
            MarketSnapshot.symbol == stock_data.symbol.upper()
        ).order_by(MarketSnapshot.timestamp.desc()).first()
        if latest_snapshot:
            ref_price = latest_snapshot.price
    
    # Add stock with quantity
    new_stock = WatchlistStock(
        watchlist_id=watchlist.id,
        symbol=stock_data.symbol.upper(),
        quantity=stock_data.quantity or 100,  # Default 100 shares
        reference_price=ref_price
    )
    db.add(new_stock)
    db.commit()
    db.refresh(new_stock)
    
    return WatchlistStockOut(
        symbol=new_stock.symbol,
        quantity=new_stock.quantity,
        reference_price=new_stock.reference_price,
        added_at=new_stock.added_at
    )

@router.delete("/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
def remove_stock(
    symbol: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a stock from the user's watchlist"""
    watchlist = db.query(Watchlist).filter(Watchlist.user_id == current_user.id).first()
    if not watchlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist not found"
        )
    
    stock = db.query(WatchlistStock).filter(
        WatchlistStock.watchlist_id == watchlist.id,
        WatchlistStock.symbol == symbol.upper()
    ).first()
    
    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stock not found in watchlist"
        )
    
    db.delete(stock)
    db.commit()

from ..data_freshness import check_data_freshness, get_watchlist_freshness

@router.get("/freshness")
def get_freshness(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check data freshness for all stocks in watchlist"""
    return get_watchlist_freshness(db, current_user.id)

@router.get("/{symbol}/freshness")
def get_symbol_freshness(
    symbol: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check data freshness for a specific symbol"""
    return check_data_freshness(db, symbol)