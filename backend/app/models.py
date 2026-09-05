from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func  # ← IMPORT FUNC
from .database import Base
import enum


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    watchlist = relationship("Watchlist", back_populates="user", uselist=False)
    checkpoint = relationship("UserCheckpoint", back_populates="user", uselist=False)


class Watchlist(Base):
    __tablename__ = "watchlists"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    
    user = relationship("User", back_populates="watchlist")
    stocks = relationship("WatchlistStock", back_populates="watchlist")


class WatchlistStock(Base):
    __tablename__ = "watchlist_stocks"
    
    id = Column(Integer, primary_key=True, index=True)
    watchlist_id = Column(Integer, ForeignKey("watchlists.id"))
    symbol = Column(String, nullable=False)
    quantity = Column(Integer, default=100)  # Shares held
    reference_price = Column(Float, nullable=True)  # Price when added
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    
    watchlist = relationship("Watchlist", back_populates="stocks")


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    price = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    source = Column(String, nullable=False, default="mock_feed")


class MarketEvent(Base):
    __tablename__ = "market_events"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False)  # earnings, dividend, acquisition, etc.
    payload = Column(JSON, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    significance_score = Column(Float, nullable=True)  # For caching computed scores


class UserCheckpoint(Base):
    __tablename__ = "user_checkpoints"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    
    user = relationship("User", back_populates="checkpoint")