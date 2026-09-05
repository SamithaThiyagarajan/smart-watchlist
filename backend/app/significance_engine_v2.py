import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from .models import MarketSnapshot, MarketEvent, User, WatchlistStock
from .database import SessionLocal

"""
ATTENTION SCORE ENGINE - Core of the Application

Four independent signals combined into one score (0-100):

1. EVENT SIGNIFICANCE (0-40 points)
   - Earnings: 40
   - Acquisitions: 35
   - Management change: 30
   - Credit rating change: 25
   - Regulatory action: 25
   - Stock split/Bonus: 20
   - Dividend: 15
   - Insider transaction: 10
   - Trading halt: 15

2. STATISTICAL ANOMALY (0-30 points)
   - Price move vs stock's own volatility (z-score)
   - Volume spike (3x+ normal volume)
   - z-score > 3: 30 points
   - z-score 2-3: 20 points
   - z-score 1-2: 10 points
   - Volume 5x+: 10 bonus points
   - Volume 3-5x: 5 bonus points

3. CONTEXTUAL SIGNIFICANCE (0-20 points)
   - Is the move market-wide or stock-specific?
   - Stock moves opposite market: 15-20 points
   - Stock moves with market but more extreme: 10-15 points

4. USER RELEVANCE (0-10 points) - Optional
   - Does the user own this stock in their watchlist?
   - If yes, add base relevance points

Total Score: 0-100
Tiers:
- High attention: ≥ 60
- Worth knowing: 35-59
- Normal: < 35
"""

# Event weights (strictly 0-40)
EVENT_WEIGHTS = {
    "earnings": 40,
    "acquisition": 35,
    "management_change": 30,
    "credit_rating_change": 25,
    "regulatory_action": 25,
    "stock_split": 20,
    "bonus": 20,
    "trading_halt": 15,
    "dividend": 15,
    "insider_transaction": 10,
}

EVENT_DESCRIPTIONS = {
    "earnings": "Earnings announced",
    "acquisition": "Acquisition announced",
    "management_change": "Management change",
    "credit_rating_change": "Credit rating changed",
    "regulatory_action": "Regulatory action",
    "stock_split": "Stock split announced",
    "bonus": "Bonus issue announced",
    "trading_halt": "Trading halted",
    "dividend": "Dividend announced",
    "insider_transaction": "Insider transaction",
}


class AttentionEngine:
    def __init__(self, db: Session, user_id: Optional[int] = None):
        self.db = db
        self.user_id = user_id
        self._watchlist_symbols = None

    def _get_watchlist_symbols(self) -> List[str]:
        """Cache watchlist symbols for this user"""
        if self._watchlist_symbols is not None:
            return self._watchlist_symbols
        
        if not self.user_id:
            self._watchlist_symbols = []
            return []
        
        watchlist_stocks = self.db.query(WatchlistStock).join(
            WatchlistStock.watchlist
        ).filter(
            WatchlistStock.watchlist.has(user_id=self.user_id)
        ).all()
        
        self._watchlist_symbols = [stock.symbol for stock in watchlist_stocks]
        return self._watchlist_symbols

    def calculate_event_significance(self, event: MarketEvent) -> Tuple[float, Dict[str, Any]]:
        """Signal 1: Event significance (0-40 points)"""
        event_type = event.type.lower()
        base_weight = EVENT_WEIGHTS.get(event_type, 10)
        
        # Bonus for high-impact events within type (capped at 40)
        bonus = 0
        if event_type == "earnings":
            profit = event.payload.get("profit", 0)
            if profit > 50000:
                bonus = 5
            elif profit > 25000:
                bonus = 3
            # Cap at 40
            score = min(base_weight + bonus, 40)
        
        elif event_type == "acquisition":
            value = event.payload.get("value", 0)
            if value > 5000:
                bonus = 5
            elif value > 2000:
                bonus = 3
            score = min(base_weight + bonus, 40)
        
        elif event_type == "insider_transaction":
            shares = event.payload.get("shares", 0)
            if shares > 50000:
                bonus = 5
            elif shares > 20000:
                bonus = 3
            score = min(base_weight + bonus, 40)
        
        else:
            score = base_weight
        
        context = {
            "event_type": event_type,
            "base_weight": base_weight,
            "bonus": bonus,
            "score": score
        }
        
        return score, context

    def calculate_statistical_anomaly(
        self, 
        symbol: str, 
        current_snapshot: MarketSnapshot
    ) -> Tuple[float, Dict[str, Any]]:
        """Signal 2: Statistical anomaly (0-30 points)"""
        
        # Get last 20 snapshots for this symbol
        historical = self.db.query(MarketSnapshot).filter(
            MarketSnapshot.symbol == symbol,
            MarketSnapshot.timestamp < current_snapshot.timestamp
        ).order_by(MarketSnapshot.timestamp.desc()).limit(20).all()
        
        if len(historical) < 5:
            return 0, {"reason": "insufficient_data", "historical_count": len(historical)}
        
        # Calculate volatility (standard deviation of daily moves)
        prices = [h.price for h in historical]
        daily_moves = []
        signed_moves = []  # Preserve direction
        
        for i in range(len(prices) - 1):
            # Signed move (preserves direction)
            signed_move = (prices[i] - prices[i+1]) / prices[i+1] * 100
            signed_moves.append(signed_move)
            # Magnitude for volatility
            daily_moves.append(abs(signed_move))
        
        if len(daily_moves) < 2:
            return 0, {"reason": "insufficient_data"}
        
        mean_move = sum(daily_moves) / len(daily_moves)
        std_dev = math.sqrt(sum((m - mean_move) ** 2 for m in daily_moves) / len(daily_moves))
        
        # Calculate current move (signed)
        current_price = current_snapshot.price
        previous_price = historical[0].price
        current_signed_move = (current_price - previous_price) / previous_price * 100
        current_magnitude = abs(current_signed_move)
        
        # Calculate z-score
        if std_dev == 0:
            z_score = 0
        else:
            z_score = (current_magnitude - mean_move) / std_dev
        
        # Score based on z-score (capped at 30)
        score = 0
        if z_score > 3:
            score = 30
        elif z_score > 2.5:
            score = 25
        elif z_score > 2:
            score = 20
        elif z_score > 1.5:
            score = 15
        elif z_score > 1:
            score = 10
        else:
            score = 5
        
        # Volume anomaly bonus
        avg_volume = sum(h.volume for h in historical[:10]) / min(len(historical), 10)
        volume_ratio = 0
        if avg_volume > 0:
            volume_ratio = current_snapshot.volume / avg_volume
            if volume_ratio > 5:
                score += 10
            elif volume_ratio > 3:
                score += 5
        
        # Cap at 30
        score = min(score, 30)
        
        # Direction info
        direction = "up" if current_signed_move > 0 else "down"
        
        context = {
            "z_score": round(z_score, 2),
            "current_move": round(current_signed_move, 2),  # Signed
            "current_magnitude": round(current_magnitude, 2),
            "avg_move": round(mean_move, 2),
            "std_dev": round(std_dev, 2),
            "volume_ratio": round(volume_ratio, 2),
            "historical_count": len(historical),
            "direction": direction,
            "score": score
        }
        
        return score, context

    def calculate_contextual_significance(
        self, 
        symbol: str, 
        current_snapshot: MarketSnapshot
    ) -> Tuple[float, Dict[str, Any]]:
        """Signal 3: Contextual/market-wide significance (0-20 points)"""
        
        # Get all snapshots in the last hour for market comparison
        time_window = current_snapshot.timestamp - timedelta(hours=1)
        
        # Get latest snapshot for each symbol in this window
        market_snapshots = self.db.query(
            MarketSnapshot.symbol,
            func.max(MarketSnapshot.timestamp).label('latest_time')
        ).filter(
            MarketSnapshot.timestamp >= time_window,
            MarketSnapshot.timestamp <= current_snapshot.timestamp
        ).group_by(MarketSnapshot.symbol).all()
        
        if len(market_snapshots) < 5:  # Need at least 5 symbols for comparison
            return 5, {"reason": "insufficient_market_data", "num_symbols": len(market_snapshots)}
        
        # Get price at start of window for each symbol
        symbol_returns = {}
        for sym, latest_time in market_snapshots:
            # Get earliest price in window
            earliest = self.db.query(MarketSnapshot).filter(
                MarketSnapshot.symbol == sym,
                MarketSnapshot.timestamp >= time_window
            ).order_by(MarketSnapshot.timestamp.asc()).first()
            
            latest = self.db.query(MarketSnapshot).filter(
                MarketSnapshot.symbol == sym,
                MarketSnapshot.timestamp == latest_time
            ).first()
            
            if earliest and latest:
                return_pct = (latest.price - earliest.price) / earliest.price * 100
                symbol_returns[sym] = return_pct
        
        if len(symbol_returns) < 5:
            return 5, {"reason": "insufficient_data"}
        
        # Calculate market average and volatility
        returns = list(symbol_returns.values())
        avg_market_return = sum(returns) / len(returns)
        market_volatility = math.sqrt(sum((r - avg_market_return) ** 2 for r in returns) / len(returns))
        
        # Get this stock's return
        stock_return = symbol_returns.get(symbol, 0)
        
        # Score: How different is this stock from the market?
        if market_volatility == 0:
            z_vs_market = 0
        else:
            z_vs_market = (stock_return - avg_market_return) / market_volatility
        
        # Calculate score (0-20)
        abs_z = abs(z_vs_market)
        if abs_z > 2:
            score = 20
        elif abs_z > 1.5:
            score = 17
        elif abs_z > 1:
            score = 15
        elif abs_z > 0.5:
            score = 10
        else:
            score = 5
        
        context = {
            "stock_return": round(stock_return, 2),
            "avg_market_return": round(avg_market_return, 2),
            "market_volatility": round(market_volatility, 2),
            "z_vs_market": round(z_vs_market, 2),
            "num_stocks": len(symbol_returns),
            "score": score
        }
        
        return score, context

    def calculate_user_relevance(
        self, 
        symbol: str
    ) -> Tuple[float, Dict[str, Any]]:
        """Signal 4: User relevance (0-10 points) - Optional"""
        
        if not self.user_id:
            return 0, {"reason": "no_user", "score": 0}
        
        watchlist_symbols = self._get_watchlist_symbols()
        
        if symbol in watchlist_symbols:
            return 10, {"in_watchlist": True, "score": 10}
        else:
            return 0, {"in_watchlist": False, "score": 0}

    def calculate_attention_score(
        self, 
        symbol: str, 
        event: Optional[MarketEvent] = None,
        snapshot: Optional[MarketSnapshot] = None
    ) -> Dict[str, Any]:
        """Combine all four signals into one attention score (0-100)"""
        
        scores = {}
        contexts = {}
        total_score = 0
        
        # Signal 1: Event significance
        if event:
            event_score, event_context = self.calculate_event_significance(event)
            scores["event"] = event_score
            contexts["event"] = event_context
            total_score += event_score
        else:
            scores["event"] = 0
            contexts["event"] = {"reason": "no_event"}
        
        # Signal 2: Statistical anomaly
        if snapshot:
            anomaly_score, anomaly_context = self.calculate_statistical_anomaly(symbol, snapshot)
            scores["anomaly"] = anomaly_score
            contexts["anomaly"] = anomaly_context
            total_score += anomaly_score
            
            # Signal 3: Contextual significance
            contextual_score, contextual_context = self.calculate_contextual_significance(symbol, snapshot)
            scores["contextual"] = contextual_score
            contexts["contextual"] = contextual_context
            total_score += contextual_score
        else:
            scores["anomaly"] = 0
            scores["contextual"] = 0
            contexts["anomaly"] = {"reason": "no_snapshot"}
            contexts["contextual"] = {"reason": "no_snapshot"}
        
        # Signal 4: User relevance (optional)
        user_score, user_context = self.calculate_user_relevance(symbol)
        scores["user_relevance"] = user_score
        contexts["user_relevance"] = user_context
        total_score += user_score
        
        # Ensure total doesn't exceed 100
        total_score = min(total_score, 100)
        
        # Determine tier
        if total_score >= 60:
            tier = "High attention"
        elif total_score >= 35:
            tier = "Worth knowing"
        else:
            tier = "Normal"
        
        return {
            "symbol": symbol,
            "attention_score": round(total_score, 2),
            "tier": tier,
            "scores": scores,
            "context": contexts,
            "timestamp": datetime.now()
        }


def process_events():
    """Process all unprocessed events and calculate attention scores"""
    db = SessionLocal()
    
    # Get events without attention scores
    unprocessed_events = db.query(MarketEvent).filter(
        MarketEvent.significance_score.is_(None)
    ).all()
    
    print(f"Processing {len(unprocessed_events)} events...")
    
    for event in unprocessed_events:
        # Get latest snapshot for this symbol
        latest_snapshot = db.query(MarketSnapshot).filter(
            MarketSnapshot.symbol == event.symbol
        ).order_by(MarketSnapshot.timestamp.desc()).first()
        
        # Calculate attention score (no user context for batch processing)
        engine = AttentionEngine(db)
        result = engine.calculate_attention_score(
            symbol=event.symbol,
            event=event,
            snapshot=latest_snapshot
        )
        
        # Update event with score
        event.significance_score = result["attention_score"]
        db.commit()
        
        # Print result
        score_str = f"{result['attention_score']:.0f}"
        tier_str = result['tier']
        symbol_str = event.symbol.ljust(12)
        type_str = event.type.ljust(20)
        print(f"  {symbol_str} {type_str} Score: {score_str} ({tier_str})")
    
    db.close()
    print("✅ Done processing events!")


if __name__ == "__main__":
    process_events()