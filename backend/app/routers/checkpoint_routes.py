from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timedelta
from typing import List, Optional
from ..database import get_db
from ..models import User, UserCheckpoint, MarketEvent, MarketSnapshot, WatchlistStock, Watchlist
from ..schemas import DigestResponse, DigestItem
from ..auth import get_current_user
from ..significance_engine import AttentionEngine

router = APIRouter(prefix="/digest", tags=["digest"])

@router.get("/since-last-check", response_model=DigestResponse)
def get_digest(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    filter_tier: Optional[str] = Query(None, description="Filter by tier: high, worth, all"),
    update_checkpoint: Optional[bool] = Query(True, description="Whether to update the checkpoint timestamp")
):
    """
    Get all meaningful events since the user's last check.
    Filter by tier: 'high' (≥60), 'worth' (35-59), or 'all' (default)
    update_checkpoint: If False, does NOT update last_checked_at (used for filtering)
    """
    
    # Get or create user checkpoint
    checkpoint = db.query(UserCheckpoint).filter(
        UserCheckpoint.user_id == current_user.id
    ).first()
    
    if not checkpoint:
        checkpoint = UserCheckpoint(user_id=current_user.id, last_checked_at=None)
        db.add(checkpoint)
        db.commit()
        db.refresh(checkpoint)
    
    last_checked = checkpoint.last_checked_at
    current_time = datetime.now()
    
    # Get user's watchlist
    watchlist = db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id
    ).first()
    
    if not watchlist:
        return DigestResponse(
            items=[],
            total_new=0,
            last_checked_at=last_checked,
            current_time=current_time,
            message="Add stocks to your watchlist to see updates"
        )
    
    # Get stocks in watchlist
    watchlist_stocks = db.query(WatchlistStock).filter(
        WatchlistStock.watchlist_id == watchlist.id
    ).all()
    symbols = [stock.symbol for stock in watchlist_stocks]
    
    if not symbols:
        return DigestResponse(
            items=[],
            total_new=0,
            last_checked_at=last_checked,
            current_time=current_time,
            message="Your watchlist is empty. Add some stocks to track!"
        )
    
    # ============================================================
    # BUILD FULL MERGED LIST FIRST (NO TIER FILTER YET)
    # ============================================================
    
    # Query events (no tier filter)
    events_query = db.query(MarketEvent).filter(
        MarketEvent.symbol.in_(symbols),
        MarketEvent.significance_score.isnot(None)
    )
    if last_checked:
        events_query = events_query.filter(MarketEvent.timestamp > last_checked)
    
    events = events_query.order_by(MarketEvent.significance_score.desc()).all()
    
    # Build FULL merged list
    all_items = []
    symbols_with_events = set()
    
    # Add event-based items
    for event in events:
        try:
            latest_snapshot = db.query(MarketSnapshot).filter(
                MarketSnapshot.symbol == event.symbol
            ).order_by(MarketSnapshot.timestamp.desc()).first()
            
            score = event.significance_score or 0
            tier = "High attention" if score >= 60 else "Worth knowing" if score >= 35 else "Normal"
            
            description = generate_description(event, latest_snapshot, score)
            engine = AttentionEngine(db, current_user.id)
            result = engine.calculate_attention_score(
                symbol=event.symbol, event=event, snapshot=latest_snapshot
            )
            reasons = result.get("reasons", [])
            
            rupee_impact = None
            for reason in reasons:
                if "impact on your" in reason:
                    rupee_impact = reason
                    break
            
            context = {
                "event_type": event.type,
                "event_details": event.payload,
                "reasons": reasons,
                "rupee_impact": rupee_impact,
            }
            if latest_snapshot:
                context["price"] = latest_snapshot.price
                context["volume"] = latest_snapshot.volume
                context["timestamp"] = latest_snapshot.timestamp
            
            all_items.append(DigestItem(
                symbol=event.symbol,
                event_type=event.type,
                description=description,
                significance_score=score,
                tier=tier,
                timestamp=event.timestamp,
                context=context
            ))
            symbols_with_events.add(event.symbol)
        except Exception as e:
            print(f"Error processing event {event.id}: {e}")
            continue
    
    # Add snapshot-based items (for stocks with no events)
    engine = AttentionEngine(db, current_user.id)
    for symbol in symbols:
        if symbol in symbols_with_events:
            continue
        latest_snapshot = db.query(MarketSnapshot).filter(
            MarketSnapshot.symbol == symbol
        ).order_by(MarketSnapshot.timestamp.desc()).first()
        if not latest_snapshot:
            continue
        
        result = engine.calculate_attention_score(
            symbol=symbol, event=None, snapshot=latest_snapshot
        )
        
        if result["tier"] != "Normal":
            rupee_impact = None
            for reason in result.get("reasons", []):
                if "impact on your" in reason or "impact" in reason.lower():
                    rupee_impact = reason
                    break
            
            all_items.append(DigestItem(
                symbol=symbol,
                event_type="price_alert",
                description=f"{symbol} moved significantly (price: ₹{latest_snapshot.price:.2f})",
                significance_score=result["attention_score"],
                tier=result["tier"],
                timestamp=latest_snapshot.timestamp,
                context={
                    "event_type": "price_alert",
                    "reasons": result.get("reasons", []),
                    "rupee_impact": rupee_impact,
                    "price": latest_snapshot.price,
                    "volume": latest_snapshot.volume,
                    "timestamp": latest_snapshot.timestamp
                }
            ))
    
    # ============================================================
    # NOW APPLY FILTER TO THE MERGED LIST
    # ============================================================
    
    if filter_tier == "high":
        filtered_items = [item for item in all_items if item.tier == "High attention"]
    elif filter_tier == "worth":
        filtered_items = [item for item in all_items if item.tier == "Worth knowing"]
    else:
        filtered_items = all_items
    
    # Sort and cap
    filtered_items.sort(key=lambda x: x.significance_score, reverse=True)
    total_new = len(filtered_items)
    top_items = filtered_items[:5]
    
    # ONLY update checkpoint if:
    # 1. It's the default view (no filter or filter_tier='all')
    # 2. OR update_checkpoint is explicitly True
    should_update = update_checkpoint and (filter_tier is None or filter_tier == "all")
    
    if should_update:
        checkpoint.last_checked_at = current_time
        db.commit()
    
    if total_new == 0:
        if last_checked is None:
            message = "Welcome! No significant events found yet. Check back later."
        else:
            message = f"Nothing significant changed since {last_checked.strftime('%I:%M %p')} — {len(symbols)} stocks tracked"
    else:
        message = f"Found {total_new} significant {'event' if total_new == 1 else 'events'} since your last check"
    
    return DigestResponse(
        items=top_items,
        total_new=total_new,
        last_checked_at=last_checked,
        current_time=current_time,
        message=message
    )


def generate_description(event: MarketEvent, snapshot: Optional[MarketSnapshot], score: float) -> str:
    """Generate plain language description for an event - NO EMOJIS"""
    
    event_type = event.type.lower()
    symbol = event.symbol
    payload = event.payload
    
    # Base descriptions - NO EMOJIS
    descriptions = {
        "earnings": f"{symbol} announced earnings with revenue of ₹{payload.get('revenue', 'N/A')} crore and profit of ₹{payload.get('profit', 'N/A')} crore",
        "acquisition": f"{symbol} acquired {payload.get('target', 'a company')} for ₹{payload.get('value', 'N/A')} crore",
        "management_change": f"{symbol} appointed {payload.get('new_appointee', 'new')} as {payload.get('position', 'management')}",
        "credit_rating_change": f"{symbol}'s rating changed from {payload.get('old_rating', 'N/A')} to {payload.get('new_rating', 'N/A')} by {payload.get('agency', 'rating agency')}",
        "regulatory_action": f"{payload.get('agency', 'Regulator')} took {payload.get('action', 'action')} against {symbol}",
        "stock_split": f"{symbol} announced a {payload.get('ratio', '')} stock split",
        "bonus": f"{symbol} announced a {payload.get('ratio', '')} bonus issue",
        "trading_halt": f"Trading in {symbol} halted due to {payload.get('reason', '')}",
        "dividend": f"{symbol} announced dividend of ₹{payload.get('amount', 'N/A')} per share",
        "insider_transaction": f"{payload.get('insider', 'Insider')} {payload.get('type', 'transacted')} {payload.get('shares', 'N/A')} shares in {symbol}"
    }
    
    description = descriptions.get(event_type, f"{symbol}: {event_type} event occurred")
    
    if snapshot:
        description += f" (Current price: ₹{snapshot.price:.2f})"
    
    return description


@router.post("/checkpoint/reset")
def reset_checkpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reset the user's checkpoint (for testing)"""
    
    checkpoint = db.query(UserCheckpoint).filter(
        UserCheckpoint.user_id == current_user.id
    ).first()
    
    if checkpoint:
        checkpoint.last_checked_at = None
        db.commit()
        return {
            "message": "Checkpoint reset successfully",
            "last_checked_at": None
        }
    
    return {"message": "No checkpoint found"}


@router.get("/checkpoint/status")
def get_checkpoint_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current checkpoint status"""
    
    checkpoint = db.query(UserCheckpoint).filter(
        UserCheckpoint.user_id == current_user.id
    ).first()
    
    if checkpoint:
        return {
            "last_checked_at": checkpoint.last_checked_at,
            "has_checked_before": checkpoint.last_checked_at is not None,
            "last_check_human": checkpoint.last_checked_at.strftime('%B %d, %Y at %I:%M %p') if checkpoint.last_checked_at else "Never"
        }
    else:
        return {
            "last_checked_at": None,
            "has_checked_before": False,
            "last_check_human": "Never"
        }