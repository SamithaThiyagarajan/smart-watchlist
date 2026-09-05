"""
Data providers and conflict resolution for market data
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import math
import random

class DataProvider(Enum):
    """Market data provider sources"""
    MOCK = "mock_feed"
    REUTERS = "reuters"
    BLOOMBERG = "bloomberg"
    ALPHA_VANTAGE = "alpha_vantage"
    YAHOO = "yahoo_finance"

    @classmethod
    def get_priority(cls, source: str) -> int:
        """Priority order: lower number = higher priority"""
        priorities = {
            cls.BLOOMBERG.value: 1,
            cls.REUTERS.value: 2,
            cls.ALPHA_VANTAGE.value: 3,
            cls.YAHOO.value: 4,
            cls.MOCK.value: 5,
        }
        return priorities.get(source, 99)

    @classmethod
    def get_primary(cls) -> str:
        """Get the primary data source"""
        return cls.BLOOMBERG.value


@dataclass
class DataPoint:
    """Single data point from a source"""
    symbol: str
    price: float
    volume: int
    timestamp: datetime
    source: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "volume": self.volume,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source
        }


@dataclass
class ConflictResolution:
    """Result of conflict resolution"""
    status: str  # "no_conflict", "minor_diff", "major_conflict", "single_source", "error"
    primary_price: float
    secondary_prices: Dict[str, float]
    resolved_price: float
    confidence: float
    message: str
    sources: List[str]

    @property
    def conflict(self) -> bool:
        """Return True if there is a conflict (minor or major)"""
        return self.status in ["minor_diff", "major_conflict"]


class DataConflictResolver:
    """Resolve conflicts between multiple data sources"""

    def __init__(self, tolerance_percent: float = 0.5):
        """
        Args:
            tolerance_percent: Maximum allowed difference between sources (as percentage)
        """
        self.tolerance_percent = tolerance_percent

    def resolve(self, data_points: List[DataPoint]) -> ConflictResolution:
        """
        Resolve conflicts between multiple data sources

        Returns:
            ConflictResolution with resolved data and status
        """
        if not data_points:
            return ConflictResolution(
                status="error",
                primary_price=0,
                secondary_prices={},
                resolved_price=0,
                confidence=0,
                message="No data available",
                sources=[]
            )

        if len(data_points) == 1:
            return ConflictResolution(
                status="single_source",
                primary_price=data_points[0].price,
                secondary_prices={},
                resolved_price=data_points[0].price,
                confidence=1.0,
                message=f"Data from {data_points[0].source} only",
                sources=[data_points[0].source]
            )

        # Group by source (take latest from each source)
        source_data = {}
        for dp in data_points:
            if dp.source not in source_data or dp.timestamp > source_data[dp.source].timestamp:
                source_data[dp.source] = dp

        # Sort sources by priority
        sorted_sources = sorted(
            source_data.keys(),
            key=lambda s: DataProvider.get_priority(s)
        )

        # Get prices
        prices = {s: source_data[s].price for s in sorted_sources}
        primary_price = prices[sorted_sources[0]]

        # Calculate differences
        max_price = max(prices.values())
        min_price = min(prices.values())
        avg_price = sum(prices.values()) / len(prices)
        diff_percent = (max_price - min_price) / avg_price * 100 if avg_price > 0 else 0

        # Build secondary prices
        secondary_prices = {
            s: p for s, p in prices.items() if s != sorted_sources[0]
        }

        # Determine status
        if diff_percent <= self.tolerance_percent:
            status = "no_conflict"
            resolved_price = avg_price
            confidence = 1.0 - (diff_percent / 100)
            message = f"All sources agree within {diff_percent:.2f}%"

        elif diff_percent <= self.tolerance_percent * 3:
            status = "minor_diff"
            # Weighted average (primary gets more weight)
            weight_primary = 0.6
            weight_others = 0.4 / (len(prices) - 1) if len(prices) > 1 else 0
            resolved_price = (primary_price * weight_primary) + sum(
                p * weight_others for s, p in prices.items() if s != sorted_sources[0]
            )
            confidence = 0.7 - (diff_percent / 100)
            message = f"Minor discrepancy between sources ({diff_percent:.2f}%). Showing weighted average."

        else:
            status = "major_conflict"
            resolved_price = primary_price  # Use primary source
            confidence = 0.3
            message = f"⚠️ Data discrepancy detected: {diff_percent:.2f}% difference. Showing primary source ({sorted_sources[0]})."

        return ConflictResolution(
            status=status,
            primary_price=primary_price,
            secondary_prices=secondary_prices,
            resolved_price=resolved_price,
            confidence=confidence,
            message=message,
            sources=sorted_sources
        )

    def get_combined_data(self, data_points: List[DataPoint]) -> Dict[str, Any]:
        """Get combined data with conflict resolution for API response"""
        resolution = self.resolve(data_points)

        return {
            "status": resolution.status,
            "message": resolution.message,
            "primary_price": round(resolution.primary_price, 2),
            "resolved_price": round(resolution.resolved_price, 2),
            "secondary_prices": {
                s: round(p, 2) for s, p in resolution.secondary_prices.items()
            },
            "confidence": round(resolution.confidence, 2),
            "sources": resolution.sources,
            "conflict": resolution.conflict
        }


def create_mock_data_points(symbol: str, base_price: float, count: int = 3) -> List[DataPoint]:
    """
    Create mock data points from multiple sources for testing
    """
    now = datetime.now()
    sources = [p.value for p in DataProvider]

    points = []
    for i in range(min(count, len(sources))):
        # Add random variation to simulate different sources
        variation = random.uniform(-0.5, 0.5) if random.random() > 0.3 else random.uniform(-1.5, 1.5)
        price = base_price * (1 + variation / 100)

        points.append(DataPoint(
            symbol=symbol,
            price=round(price, 2),
            volume=random.randint(100000, 5000000),
            timestamp=now - timedelta(minutes=random.randint(0, 5)),
            source=sources[i]
        ))

    return points