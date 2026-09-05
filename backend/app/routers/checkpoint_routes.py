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
    
    # Query events since last check (or all events if first time)
    events_query = db.query(MarketEvent).filter(
        MarketEvent.symbol.in_(symbols),
        MarketEvent.significance_score.isnot(None)
    )
    
    if last_checked:
        events_query = events_query.filter(
            MarketEvent.timestamp > last_checked
        )
    
    # Apply tier filter
    if filter_tier == "high":
        events_query = events_query.filter(
            MarketEvent.significance_score >= 60
        )
    elif filter_tier == "worth":
        events_query = events_query.filter(
            MarketEvent.significance_score >= 35,
            MarketEvent.significance_score < 60
        )
    else:
        # "all" or default - show everything >= 35
        events_query = events_query.filter(
            MarketEvent.significance_score >= 35
        )
    
    events = events_query.order_by(
        MarketEvent.significance_score.desc()
    ).all()
    
    # Get latest snapshots for each symbol (for context)
    digest_items = []
    
    for event in events:
        try:
            latest_snapshot = db.query(MarketSnapshot).filter(
                MarketSnapshot.symbol == event.symbol
            ).order_by(MarketSnapshot.timestamp.desc()).first()
            
            score = event.significance_score or 0
            
            if score >= 60:
                tier = "High attention"
            elif score >= 35:
                tier = "Worth knowing"
            else:
                tier = "Normal"
            
            description = generate_description(event, latest_snapshot, score)
            
            engine = AttentionEngine(db, current_user.id)
            result = engine.calculate_attention_score(
                symbol=event.symbol,
                event=event,
                snapshot=latest_snapshot
            )
            reasons = result.get("reasons", [])
            
            # Extract rupee impact prominently
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
            
            digest_items.append(DigestItem(
                symbol=event.symbol,
                event_type=event.type,
                description=description,
                significance_score=score,
                tier=tier,
                timestamp=event.timestamp,
                context=context
            ))
        except Exception as e:
            print(f"Error processing event {event.id}: {e}")
            continue
    
    total_new = len(digest_items)
    top_items = digest_items[:5]
    
    # ONLY update checkpoint if:
    # 1. It's the default view (no filter or filter_tier='all')
    # 2. OR update_checkpoint is explicitly True
    should_update = update_checkpoint and (filter_tier is None or filter_tier == "all")
    
    if should_update:
        checkpoint.last_checked_at = current_time
        db.commit()
        checkpoint_status = "updated"
    else:
        checkpoint_status = "preserved"
    
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

# ... rest of the file (generate_description, reset_checkpoint, get_checkpoint_status remain the same)

def generate_description(event: MarketEvent, snapshot: Optional[MarketSnapshot], score: float) -> str:
    """Generate plain language description for an event"""
    
    event_type = event.type.lower()
    symbol = event.symbol
    payload = event.payload
    
    # Base descriptions
    descriptions = {
        "earnings": f"📊 {symbol} announced earnings with revenue of ₹{payload.get('revenue', 'N/A')} crore and profit of ₹{payload.get('profit', 'N/A')} crore",
        "acquisition": f"🤝 {symbol} acquired {payload.get('target', 'a company')} for ₹{payload.get('value', 'N/A')} crore",
        "management_change": f"👔 {symbol} appointed {payload.get('new_appointee', 'new')} as {payload.get('position', 'management')}",
        "credit_rating_change": f"📈 {symbol}'s rating changed from {payload.get('old_rating', 'N/A')} to {payload.get('new_rating', 'N/A')} by {payload.get('agency', 'rating agency')}",
        "regulatory_action": f"⚖️ {payload.get('agency', 'Regulator')} took {payload.get('action', 'action')} against {symbol}",
        "stock_split": f"🔀 {symbol} announced a {payload.get('ratio', '')} stock split",
        "bonus": f"🎁 {symbol} announced a {payload.get('ratio', '')} bonus issue",
        "trading_halt": f"⏸️ Trading in {symbol} halted due to {payload.get('reason', '')}",
        "dividend": f"💰 {symbol} announced dividend of ₹{payload.get('amount', 'N/A')} per share",
        "insider_transaction": f"📋 {payload.get('insider', 'Insider')} {payload.get('type', 'transacted')} {payload.get('shares', 'N/A')} shares in {symbol}"
    }
    
    description = descriptions.get(event_type, f"📌 {symbol}: {event_type} event occurred")
    
    # Add price context if available
    if snapshot:
        description += f" (Current price: ₹{snapshot.price:.2f})"
    
    # Add attention level indicator
    if score >= 60:
        description = f"🔴 {description}"
    elif score >= 45:
        description = f"🟡 {description}"
    
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


@router.get("/test/generate-events")
def generate_test_events(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate test events for a specific user (for testing)"""
    
    # Only allow in development
    return {"message": "Use the mock data generator to create events"}