from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from .routers import auth_routes, watchlist_routes, checkpoint_routes
from .routers.market_routes import router as market_routes
from .database import engine, Base
from .models import User, Watchlist, WatchlistStock, MarketSnapshot, MarketEvent, UserCheckpoint
from .auth import get_current_user
import asyncio
from contextlib import asynccontextmanager
import sys
import os

# Create tables
Base.metadata.create_all(bind=engine)


# ============================================================
# BACKGROUND WORKER - Generates market data every 15 seconds
# ============================================================
async def background_worker():
    """Run the market data generator in the background"""
    print("🚀 Background market data worker started!")
    
    # Add backend directory to path so we can import the worker
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_dir not in sys.path:
        sys.path.append(backend_dir)
    
    try:
        from worker.market_data_generator import run_market_generator
        await run_market_generator()
    except ImportError as e:
        print(f"⚠️ Could not import worker: {e}")
        print("   Market data generator will not run automatically.")
        print("   You can still run it manually with: python run_worker.py")
    except Exception as e:
        print(f"⚠️ Worker error: {e}")
        # Keep running, don't crash the app


# ============================================================
# FastAPI Lifespan - Start worker on app startup
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start the background worker
    task = asyncio.create_task(background_worker())
    print("✅ FastAPI app started with background worker")
    
    yield  # The app runs here
    
    # Shutdown: Clean up the worker
    task.cancel()
    print("🛑 FastAPI app shutting down, worker cancelled")


# ============================================================
# Create the FastAPI app
# ============================================================
app = FastAPI(
    title="Smart Market Watchlist",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://frontend-pi-seven-5jrqkk6pea.vercel.app",
        "https://frontend-3rvi26w2s-samithathiyagarajans-projects.vercel.app",
        "https://*.vercel.app",
        "*"  # Allow all during demo
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_routes.router)
app.include_router(watchlist_routes.router)
app.include_router(checkpoint_routes.router)
app.include_router(market_routes)


# ============================================================
# Simple endpoints
# ============================================================
@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": "2026-09-06T00:00:00Z"}


@app.get("/me")
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "created_at": current_user.created_at
    }