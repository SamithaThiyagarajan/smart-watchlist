from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List, Dict, Any

# Auth schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    email: str
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

# Watchlist schemas
class WatchlistStockAdd(BaseModel):
    symbol: str
    quantity: Optional[int] = 0  # ← ADD THIS
    reference_price: Optional[float] = None  # ← ADD THIS

class WatchlistStockOut(BaseModel):
    symbol: str
    quantity: int
    reference_price: Optional[float] = None
    added_at: datetime

# Market schemas
class MarketSnapshotOut(BaseModel):
    symbol: str
    price: float
    volume: int
    timestamp: datetime
    source: str

class MarketEventOut(BaseModel):
    id: int
    symbol: str
    type: str
    payload: Dict[str, Any]
    timestamp: datetime
    significance_score: Optional[float] = None

# Digest schemas
class DigestItem(BaseModel):
    symbol: str
    event_type: str
    description: str
    significance_score: float
    tier: str
    timestamp: datetime
    context: Optional[Dict[str, Any]] = None

class DigestResponse(BaseModel):
    items: List[DigestItem]
    total_new: int
    last_checked_at: Optional[datetime]
    current_time: datetime
    message: Optional[str] = None