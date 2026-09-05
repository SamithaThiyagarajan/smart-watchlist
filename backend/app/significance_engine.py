import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from .models import MarketSnapshot, MarketEvent, User, WatchlistStock, Watchlist
from .database import SessionLocal
from .sector_mapping import get_sector, get_sector_stocks
from .data_providers import DataPoint, DataConflictResolver, DataProvider
"""
ATTENTION SCORE ENGINE - Core of the Application

Five independent signals combined into one score (0-100):

1. EVENT SIGNIFICANCE (0-40 points)
   - Earnings, acquisitions, management changes, etc.

2. STATISTICAL ANOMALY (0-30 points)
   - Price/volume vs stock's own historical volatility

3. CONTEXTUAL SIGNIFICANCE (0-20 points)
   - Stock vs overall market movement

4. SECTOR CORRELATION (0-15 points) - ENHANCED!
   - Historical correlation + current divergence + sector breadth
   - Identifies stock-specific events hidden by sector moves

5. RUPEE RELEVANCE (0-10 points)
   - Actual money impact on user's position

Total Score: 0-100
Tiers:
- High attention: >= 60
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


class AttentionEngine:
    def __init__(self, db: Session, user_id: Optional[int] = None):
        self.db = db
        self.user_id = user_id
        self._watchlist_symbols = None
        self._watchlist_holdings = None

    def _get_watchlist_symbols(self) -> List[str]:
        """Cache watchlist symbols for this user"""
        if self._watchlist_symbols is not None:
            return self._watchlist_symbols
        
        if not self.user_id:
            self._watchlist_symbols = []
            self._watchlist_holdings = {}
            return []
        
        watchlist_stocks = self.db.query(WatchlistStock).join(
            Watchlist
        ).filter(
            Watchlist.user_id == self.user_id
        ).all()
        
        self._watchlist_symbols = [stock.symbol for stock in watchlist_stocks]
        self._watchlist_holdings = {
            stock.symbol: {
                "quantity": stock.quantity or 0,
                "reference_price": stock.reference_price
            }
            for stock in watchlist_stocks
        }
        return self._watchlist_symbols

    def _get_watchlist_holding(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get holding details for a symbol (quantity, reference_price)"""
        if self._watchlist_symbols is None:
            self._get_watchlist_symbols()
        
        return self._watchlist_holdings.get(symbol) if self._watchlist_holdings else None

    def get_reliable_snapshot(
        self, 
        symbol: str, 
        prefer_source: Optional[str] = None
    ) -> Optional[MarketSnapshot]:
        """
        Get the most reliable snapshot with conflict resolution
        """
        # Get snapshots from multiple sources
        sources = [prefer_source] if prefer_source else [
            DataProvider.BLOOMBERG.value,
            DataProvider.REUTERS.value,
            DataProvider.MOCK.value
        ]
        
        snapshots = []
        for source in sources:
            snapshot = self.db.query(MarketSnapshot).filter(
                MarketSnapshot.symbol == symbol,
                MarketSnapshot.source == source
            ).order_by(MarketSnapshot.timestamp.desc()).first()
            if snapshot:
                snapshots.append(snapshot)
        
        if not snapshots:
            return None
        
        if len(snapshots) == 1:
            return snapshots[0]
        
        # Resolve conflicts
        data_points = [
            DataPoint(
                symbol=s.symbol,
                price=s.price,
                volume=s.volume,
                timestamp=s.timestamp,
                source=s.source
            )
            for s in snapshots
        ]
        
        resolver = DataConflictResolver()
        resolution = resolver.resolve(data_points)
        
        # Return the primary snapshot with resolved price
        primary = snapshots[0]
        if resolution.status in ["minor_diff", "major_conflict"]:
            # Add conflict info to the snapshot
            primary.conflict_resolved = True
            primary.resolved_price = resolution.resolved_price
            primary.conflict_message = resolution.message
        
        return primary

    # Use this in calculate_statistical_anomaly and other methods:
    # Instead of:
    # latest_snapshot = db.query(MarketSnapshot).filter(...).first()
    # Use:
    # latest_snapshot = self.get_reliable_snapshot(symbol)
    def calculate_event_significance(self, event: MarketEvent) -> Tuple[float, Dict[str, Any]]:
        """Signal 1: Event significance (0-40 points)"""
        event_type = event.type.lower()
        base_weight = EVENT_WEIGHTS.get(event_type, 10)
        
        bonus = 0
        if event_type == "earnings":
            profit = event.payload.get("profit", 0)
            if profit > 50000:
                bonus = 5
            elif profit > 25000:
                bonus = 3
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
        
        reason = f"{event_type.replace('_', ' ').title()} event"
        if bonus > 0:
            reason += f" (high impact: +{bonus} bonus)"
        
        context = {
            "event_type": event_type,
            "base_weight": base_weight,
            "bonus": bonus,
            "score": score,
            "reason": reason
        }
        
        return score, context

    def calculate_statistical_anomaly(
        self, 
        symbol: str, 
        current_snapshot: MarketSnapshot
    ) -> Tuple[float, Dict[str, Any]]:
        """Signal 2: Statistical anomaly (0-30 points)"""
        
        historical = self.db.query(MarketSnapshot).filter(
            MarketSnapshot.symbol == symbol,
            MarketSnapshot.timestamp < current_snapshot.timestamp
        ).order_by(MarketSnapshot.timestamp.desc()).limit(20).all()
        
        if len(historical) < 5:
            return 0, {"reason": "insufficient_data", "historical_count": len(historical)}
        
        prices = [h.price for h in historical]
        daily_moves = []
        
        for i in range(len(prices) - 1):
            signed_move = (prices[i] - prices[i+1]) / prices[i+1] * 100
            daily_moves.append(abs(signed_move))
        
        if len(daily_moves) < 2:
            return 0, {"reason": "insufficient_data"}
        
        mean_move = sum(daily_moves) / len(daily_moves)
        std_dev = math.sqrt(sum((m - mean_move) ** 2 for m in daily_moves) / len(daily_moves))
        
        current_price = current_snapshot.price
        previous_price = historical[0].price
        current_signed_move = (current_price - previous_price) / previous_price * 100
        current_magnitude = abs(current_signed_move)
        
        if std_dev == 0:
            z_score = 0
        else:
            z_score = (current_magnitude - mean_move) / std_dev
        
        # Score based on z-score (0 for normal movement)
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
            score = 0
        
        # Volume anomaly bonus
        avg_volume = sum(h.volume for h in historical[:10]) / min(len(historical), 10)
        volume_ratio = 0
        volume_reason = ""
        if avg_volume > 0:
            volume_ratio = current_snapshot.volume / avg_volume
            if volume_ratio > 5:
                score += 10
                volume_reason = f"volume {volume_ratio:.1f}x normal"
            elif volume_ratio > 3:
                score += 5
                volume_reason = f"volume {volume_ratio:.1f}x normal"
        
        score = min(score, 30)
        
        if current_signed_move > 0:
            direction = "up"
        elif current_signed_move < 0:
            direction = "down"
        else:
            direction = "flat"
        
        reasons = []
        if z_score > 1:
            reasons.append(f"price moved {current_magnitude:.1f}% ({z_score:.1f}σ above normal)")
        if volume_ratio > 3:
            reasons.append(volume_reason)
        
        reason = ", ".join(reasons) if reasons else "normal movement (no anomaly)"
        
        context = {
            "z_score": round(z_score, 2),
            "current_move": round(current_signed_move, 2),
            "current_magnitude": round(current_magnitude, 2),
            "avg_move": round(mean_move, 2),
            "std_dev": round(std_dev, 2),
            "volume_ratio": round(volume_ratio, 2),
            "historical_count": len(historical),
            "direction": direction,
            "score": score,
            "reason": reason
        }
        
        return score, context

    def calculate_contextual_significance(
        self, 
        symbol: str, 
        current_snapshot: MarketSnapshot
    ) -> Tuple[float, Dict[str, Any]]:
        """Signal 3: Contextual/market-wide significance (0-20 points)"""
        
        time_window = current_snapshot.timestamp - timedelta(hours=1)
        
        market_snapshots = self.db.query(
            MarketSnapshot.symbol,
            func.max(MarketSnapshot.timestamp).label('latest_time')
        ).filter(
            MarketSnapshot.timestamp >= time_window,
            MarketSnapshot.timestamp <= current_snapshot.timestamp
        ).group_by(MarketSnapshot.symbol).all()
        
        if len(market_snapshots) < 5:
            return 5, {"reason": "insufficient_market_data", "num_symbols": len(market_snapshots)}
        
        symbol_returns = {}
        for sym, latest_time in market_snapshots:
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
        
        returns = list(symbol_returns.values())
        avg_market_return = sum(returns) / len(returns)
        market_volatility = math.sqrt(sum((r - avg_market_return) ** 2 for r in returns) / len(returns))
        
        stock_return = symbol_returns.get(symbol, 0)
        
        if market_volatility == 0:
            z_vs_market = 0
        else:
            z_vs_market = (stock_return - avg_market_return) / market_volatility
        
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
        
        if abs_z > 1:
            direction = "up" if stock_return > 0 else "down"
            market_dir = "up" if avg_market_return > 0 else "down"
            if (stock_return > 0 and avg_market_return < 0) or (stock_return < 0 and avg_market_return > 0):
                reason = f"{symbol} moved {direction} ({stock_return:.1f}%) while market moved {market_dir} ({avg_market_return:.1f}%)"
            else:
                reason = f"{symbol} moved {direction} {stock_return:.1f}%, market {market_dir} {avg_market_return:.1f}%"
        else:
            reason = "move aligns with broader market"
        
        context = {
            "stock_return": round(stock_return, 2),
            "avg_market_return": round(avg_market_return, 2),
            "market_volatility": round(market_volatility, 2),
            "z_vs_market": round(z_vs_market, 2),
            "num_stocks": len(symbol_returns),
            "score": score,
            "reason": reason
        }
        
        return score, context

    def calculate_historical_correlation(
        self, 
        symbol: str, 
        sector: str,
        sector_stocks: List[str],
        days: int = 30
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Calculate historical correlation between a stock and its sector.
        
        Returns:
        - correlation: Pearson correlation coefficient (-1 to 1)
        - context: Additional info about the correlation
        """
        if len(sector_stocks) < 3:
            return 0, {"reason": "Insufficient stocks for correlation", "score": 0}
        
        # Get historical daily returns for the stock
        stock_snapshots = self.db.query(MarketSnapshot).filter(
            MarketSnapshot.symbol == symbol
        ).order_by(MarketSnapshot.timestamp.desc()).limit(days * 2).all()
        
        if len(stock_snapshots) < 10:
            return 0, {"reason": "Insufficient historical data", "score": 0}
        
        # Get sector average returns for same period
        sector_returns = {}
        for s in sector_stocks:
            if s == symbol:
                continue
            snapshots = self.db.query(MarketSnapshot).filter(
                MarketSnapshot.symbol == s
            ).order_by(MarketSnapshot.timestamp.desc()).limit(days * 2).all()
            if len(snapshots) > 5:
                sector_returns[s] = [s.price for s in snapshots]
        
        if len(sector_returns) < 2:
            return 0, {"reason": "Insufficient sector data for correlation", "score": 0}
        
        # Calculate daily returns for stock
        stock_returns = []
        for i in range(len(stock_snapshots) - 1):
            ret = (stock_snapshots[i].price - stock_snapshots[i+1].price) / stock_snapshots[i+1].price * 100
            stock_returns.append(ret)
        
        # Calculate daily returns for each sector stock
        sector_returns_list = []
        for s, prices in sector_returns.items():
            rets = []
            for i in range(len(prices) - 1):
                ret = (prices[i] - prices[i+1]) / prices[i+1] * 100
                rets.append(ret)
            sector_returns_list.append(rets)
        
        if not stock_returns or not sector_returns_list:
            return 0, {"reason": "No return data available", "score": 0}
        
        # Average sector returns
        avg_sector_returns = []
        min_len = min(len(stock_returns), min(len(r) for r in sector_returns_list))
        
        for i in range(min_len):
            day_avg = sum(r[i] for r in sector_returns_list) / len(sector_returns_list)
            avg_sector_returns.append(day_avg)
        
        # Calculate Pearson correlation
        stock_returns = stock_returns[:min_len]
        
        if len(stock_returns) < 5:
            return 0, {"reason": "Insufficient data points", "score": 0}
        
        mean_stock = sum(stock_returns) / len(stock_returns)
        mean_sector = sum(avg_sector_returns) / len(avg_sector_returns)
        
        numerator = sum((s - mean_stock) * (sec - mean_sector) for s, sec in zip(stock_returns, avg_sector_returns))
        denominator = math.sqrt(sum((s - mean_stock) ** 2 for s in stock_returns)) * math.sqrt(sum((sec - mean_sector) ** 2 for sec in avg_sector_returns))
        
        correlation = numerator / denominator if denominator != 0 else 0
        
        context = {
            "correlation": round(correlation, 3),
            "data_points": len(stock_returns),
            "correlation_strength": "strong" if abs(correlation) > 0.7 else "moderate" if abs(correlation) > 0.4 else "weak"
        }
        
        return correlation, context

    def calculate_sector_breadth(
        self,
        sector: str,
        sector_stocks: List[str],
        current_snapshot: MarketSnapshot,
        threshold_percent: float = 1.0
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Calculate sector breadth - how many stocks in the sector are moving together.
        
        Returns:
        - breadth_score: 0-10 points based on how concentrated the move is
        - context: Additional info about sector breadth
        """
        time_window = current_snapshot.timestamp - timedelta(hours=1)
        
        sector_moves = {}
        
        for s in sector_stocks:
            earliest = self.db.query(MarketSnapshot).filter(
                MarketSnapshot.symbol == s,
                MarketSnapshot.timestamp >= time_window,
                MarketSnapshot.timestamp <= current_snapshot.timestamp
            ).order_by(MarketSnapshot.timestamp.asc()).first()
            
            latest = self.db.query(MarketSnapshot).filter(
                MarketSnapshot.symbol == s,
                MarketSnapshot.timestamp >= time_window,
                MarketSnapshot.timestamp <= current_snapshot.timestamp
            ).order_by(MarketSnapshot.timestamp.desc()).first()
            
            if earliest and latest:
                move = (latest.price - earliest.price) / earliest.price * 100
                sector_moves[s] = move
        
        if len(sector_moves) < 3:
            return 0, {"reason": "Insufficient data for breadth analysis", "score": 0}
        
        # Count stocks with significant moves (positive or negative)
        positive_moves = [m for m in sector_moves.values() if m > threshold_percent]
        negative_moves = [m for m in sector_moves.values() if m < -threshold_percent]
        total_stocks = len(sector_moves)
        
        breadth_ratio = (len(positive_moves) + len(negative_moves)) / total_stocks
        
        # Score: Higher breadth = more stocks moving together = sector-wide event
        if breadth_ratio > 0.8:
            breadth_score = 10
            breadth_status = "strong"
        elif breadth_ratio > 0.6:
            breadth_score = 7
            breadth_status = "moderate"
        elif breadth_ratio > 0.4:
            breadth_score = 4
            breadth_status = "weak"
        else:
            breadth_score = 0
            breadth_status = "very weak"
        
        # Directional bias
        if len(positive_moves) > len(negative_moves) * 2:
            direction = "up"
        elif len(negative_moves) > len(positive_moves) * 2:
            direction = "down"
        else:
            direction = "mixed"
        
        context = {
            "breadth_score": breadth_score,
            "breadth_status": breadth_status,
            "direction": direction,
            "positive_count": len(positive_moves),
            "negative_count": len(negative_moves),
            "total_stocks": total_stocks,
            "breadth_ratio": round(breadth_ratio, 2)
        }
        
        return breadth_score, context

    def calculate_sector_correlation(
        self, 
        symbol: str, 
        current_snapshot: MarketSnapshot
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Signal 4: Sector correlation break (0-15 points)
        
        Combines three factors:
        1. Historical correlation - Does this stock normally move with its sector?
        2. Current divergence - How different is today's move?
        3. Sector breadth - How many stocks in the sector are moving together?
        
        This identifies stock-specific events that are hidden by sector-wide movements.
        """
        sector = get_sector(symbol)
        if sector == "Unknown":
            return 0, {"reason": "Unknown sector", "score": 0}
        
        sector_stocks = get_sector_stocks(sector)
        
        if len(sector_stocks) < 3:
            return 0, {"reason": f"Insufficient stocks in {sector} sector", "score": 0}
        
        # 1. Calculate historical correlation
        correlation, corr_context = self.calculate_historical_correlation(symbol, sector, sector_stocks)
        
        # 2. Calculate current divergence
        sector_returns = {}
        time_window = current_snapshot.timestamp - timedelta(hours=1)
        
        for s in sector_stocks:
            if s == symbol:
                continue
                
            earliest = self.db.query(MarketSnapshot).filter(
                MarketSnapshot.symbol == s,
                MarketSnapshot.timestamp >= time_window,
                MarketSnapshot.timestamp <= current_snapshot.timestamp
            ).order_by(MarketSnapshot.timestamp.asc()).first()
            
            latest = self.db.query(MarketSnapshot).filter(
                MarketSnapshot.symbol == s,
                MarketSnapshot.timestamp >= time_window,
                MarketSnapshot.timestamp <= current_snapshot.timestamp
            ).order_by(MarketSnapshot.timestamp.desc()).first()
            
            if earliest and latest:
                return_pct = (latest.price - earliest.price) / earliest.price * 100
                sector_returns[s] = return_pct
        
        if len(sector_returns) < 2:
            return 0, {"reason": "Insufficient sector data", "score": 0}
        
        # Get this stock's return
        current_price = current_snapshot.price
        previous = self.db.query(MarketSnapshot).filter(
            MarketSnapshot.symbol == symbol,
            MarketSnapshot.timestamp < current_snapshot.timestamp
        ).order_by(MarketSnapshot.timestamp.desc()).first()
        
        if not previous:
            return 0, {"reason": "No previous data", "score": 0}
        
        stock_return = (current_price - previous.price) / previous.price * 100
        
        sector_avg_return = sum(sector_returns.values()) / len(sector_returns)
        
        variance = sum((r - sector_avg_return) ** 2 for r in sector_returns.values()) / len(sector_returns)
        sector_std_dev = math.sqrt(variance) if variance > 0 else 0.01
        
        deviation = abs(stock_return - sector_avg_return)
        z_score = deviation / sector_std_dev if sector_std_dev > 0 else 0
        
        # 3. Calculate sector breadth
        breadth_score, breadth_context = self.calculate_sector_breadth(sector, sector_stocks, current_snapshot)
        
        # COMBINE ALL THREE FACTORS
        # Factor 1: Historical correlation (0-5 points)
        if abs(correlation) > 0.7:
            corr_score = 5  # Usually moves with sector - breaking is more significant
        elif abs(correlation) > 0.4:
            corr_score = 3
        else:
            corr_score = 1  # Already low correlation, so not significant
        
        # Factor 2: Current divergence (0-8 points)
        if z_score > 3:
            div_score = 8
            status = "severely broken"
        elif z_score > 2:
            div_score = 6
            status = "significant divergence"
        elif z_score > 1.5:
            div_score = 4
            status = "diverging"
        elif z_score > 1:
            div_score = 2
            status = "slight divergence"
        else:
            div_score = 0
            status = "aligned"
        
        # Factor 3: Sector breadth adjustment
        # If sector breadth is high, this is a sector-wide event (lower score)
        # If sector breadth is low, this is stock-specific (higher score)
        if breadth_context["breadth_ratio"] > 0.7:
            breadth_adjustment = -3  # Sector-wide event - reduce score
        elif breadth_context["breadth_ratio"] > 0.5:
            breadth_adjustment = -1
        else:
            breadth_adjustment = 2  # Mostly stock-specific - increase score
        
        # Calculate final score
        total_sector_score = max(0, corr_score + div_score + breadth_adjustment)
        total_sector_score = min(total_sector_score, 15)  # Cap at 15
        
        stock_direction = "up" if stock_return > 0 else "down" if stock_return < 0 else "flat"
        sector_direction = "up" if sector_avg_return > 0 else "down" if sector_avg_return < 0 else "flat"
        
        # Build reason with all three factors
        reason_parts = []
        if abs(correlation) > 0.5:
            reason_parts.append(f"normally moves with {sector} sector (corr: {correlation:.2f})")
        if z_score > 1:
            reason_parts.append(f"today diverged {stock_direction} {abs(stock_return):.1f}% vs sector {sector_direction} {abs(sector_avg_return):.1f}%")
        if breadth_context["breadth_ratio"] > 0.6:
            reason_parts.append(f"{breadth_context['positive_count'] + breadth_context['negative_count']}/{breadth_context['total_stocks']} sector stocks moving")
        
        reason = f"{symbol} - " + ", ".join(reason_parts) if reason_parts else f"Aligned with {sector} sector"
        
        context = {
            "sector": sector,
            "stock_return": round(stock_return, 2),
            "sector_avg_return": round(sector_avg_return, 2),
            "z_score": round(z_score, 2),
            "correlation": round(correlation, 3),
            "correlation_strength": corr_context.get("correlation_strength", "unknown"),
            "breadth_ratio": round(breadth_context.get("breadth_ratio", 0), 2),
            "status": status,
            "score": total_sector_score,
            "reason": reason,
            "num_sector_stocks": len(sector_returns)
        }
        
        return total_sector_score, context

    def calculate_rupee_relevance(
        self, 
        symbol: str, 
        current_snapshot: MarketSnapshot
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Signal 5: Rupee impact on this user's actual position (0-10 points)
        
        This is the KEY DIFFERENTIATOR - catches "big but not unusual" moves.
        A statistically normal move (signal 2 = 0) can still be a ₹50,000 impact
        on the user's position, and this signal catches it.
        """
        if not self.user_id:
            return 0, {"reason": "no_user", "score": 0}
        
        holding = self._get_watchlist_holding(symbol)
        if holding is None:
            return 0, {"reason": "not_in_watchlist", "score": 0}
        
        quantity = holding.get("quantity", 0)
        if quantity <= 0:
            return 0, {"reason": "no_position_size", "score": 0}
        
        ref_price = holding.get("reference_price")
        if ref_price is None:
            first_snapshot = self.db.query(MarketSnapshot).filter(
                MarketSnapshot.symbol == symbol
            ).order_by(MarketSnapshot.timestamp.asc()).first()
            ref_price = first_snapshot.price if first_snapshot else current_snapshot.price
        
        price_change = current_snapshot.price - ref_price
        rupee_impact = abs(price_change * quantity)
        direction = "up" if price_change > 0 else "down" if price_change < 0 else "flat"
        
        if rupee_impact > 20000:
            score = 10
            impact_level = "large"
        elif rupee_impact > 10000:
            score = 7
            impact_level = "significant"
        elif rupee_impact > 5000:
            score = 4
            impact_level = "moderate"
        elif rupee_impact > 1000:
            score = 2
            impact_level = "small"
        else:
            score = 0
            impact_level = "minor"
        
        if score > 0:
            reason = f"₹{rupee_impact:,.0f} {direction}ward impact on your {quantity} shares"
        else:
            reason = f"Minor position impact (₹{rupee_impact:,.0f})"
        
        context = {
            "rupee_impact": round(rupee_impact, 2),
            "quantity": quantity,
            "price_change": round(price_change, 2),
            "direction": direction,
            "score": score,
            "impact_level": impact_level,
            "reason": reason
        }
        
        return score, context

    def calculate_attention_score(
        self, 
        symbol: str, 
        event: Optional[MarketEvent] = None,
        snapshot: Optional[MarketSnapshot] = None
    ) -> Dict[str, Any]:
        """Combine all five signals into one attention score (0-100)"""
        
        scores = {}
        contexts = {}
        reasons = []
        total_score = 0
        
        # Signal 1: Event significance
        if event:
            event_score, event_context = self.calculate_event_significance(event)
            scores["event"] = event_score
            contexts["event"] = event_context
            total_score += event_score
            if event_score > 0:
                reasons.append(event_context.get("reason", "Event occurred"))
        else:
            scores["event"] = 0
            contexts["event"] = {"reason": "no_event"}
        
        if snapshot:
            # Signal 2: Statistical anomaly
            anomaly_score, anomaly_context = self.calculate_statistical_anomaly(symbol, snapshot)
            scores["anomaly"] = anomaly_score
            contexts["anomaly"] = anomaly_context
            total_score += anomaly_score
            if anomaly_score > 0:
                reasons.append(anomaly_context.get("reason", "Statistical anomaly"))
            
            # Signal 3: Contextual significance
            contextual_score, contextual_context = self.calculate_contextual_significance(symbol, snapshot)
            scores["contextual"] = contextual_score
            contexts["contextual"] = contextual_context
            total_score += contextual_score
            if contextual_score > 5:
                reasons.append(contextual_context.get("reason", "Contextual significance"))
            
            # Signal 4: Sector correlation (ONLY ONCE!)
            sector_score, sector_context = self.calculate_sector_correlation(symbol, snapshot)
            scores["sector_correlation"] = sector_score
            contexts["sector_correlation"] = sector_context
            total_score += sector_score
            if sector_score > 0:
                reasons.append(sector_context.get("reason", "Sector divergence"))
            
            # Signal 5: Rupee relevance
            rupee_score, rupee_context = self.calculate_rupee_relevance(symbol, snapshot)
            scores["rupee_relevance"] = rupee_score
            contexts["rupee_relevance"] = rupee_context
            total_score += rupee_score
            if rupee_score > 0:
                reasons.append(rupee_context.get("reason", "Rupee impact"))
        else:
            scores["anomaly"] = 0
            scores["contextual"] = 0
            scores["sector_correlation"] = 0
            scores["rupee_relevance"] = 0
            contexts["anomaly"] = {"reason": "no_snapshot"}
            contexts["contextual"] = {"reason": "no_snapshot"}
            contexts["sector_correlation"] = {"reason": "no_snapshot"}
            contexts["rupee_relevance"] = {"reason": "no_snapshot"}
        
        total_score = min(total_score, 100)
        
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
            "reasons": reasons,
            "timestamp": datetime.now()
        }


def process_events():
    """Process all unprocessed events and calculate attention scores"""
    db = SessionLocal()
    
    unprocessed_events = db.query(MarketEvent).filter(
        MarketEvent.significance_score.is_(None)
    ).all()
    
    print(f"Processing {len(unprocessed_events)} events...")
    print("-" * 60)
    
    for event in unprocessed_events:
        latest_snapshot = db.query(MarketSnapshot).filter(
            MarketSnapshot.symbol == event.symbol
        ).order_by(MarketSnapshot.timestamp.desc()).first()
        
        engine = AttentionEngine(db)
        result = engine.calculate_attention_score(
            symbol=event.symbol,
            event=event,
            snapshot=latest_snapshot
        )
        
        event.significance_score = result["attention_score"]
        db.commit()
        
        score_str = f"{result['attention_score']:.0f}"
        tier_str = result['tier']
        symbol_str = event.symbol.ljust(12)
        type_str = event.type.ljust(20)
        reasons_str = ", ".join(result['reasons'][:3])
        
        print(f"  {symbol_str} {type_str} Score: {score_str} ({tier_str})")
        print(f"    → {reasons_str}")
        print()
    
    db.close()
    print("-" * 60)
    print(f"✅ Done processing {len(unprocessed_events)} events!")


if __name__ == "__main__":
    process_events()