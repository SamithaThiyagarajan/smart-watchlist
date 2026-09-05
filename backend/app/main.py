from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from .routers import auth_routes, watchlist_routes, checkpoint_routes, market_routes
from .database import engine, Base
from .models import User, Watchlist, WatchlistStock, MarketSnapshot, MarketEvent, UserCheckpoint
from .auth import get_current_user

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Market Watchlist")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://frontend-pi-seven-5jrqkk6pea.vercel.app",
        "https://frontend-3rvi26w2s-samithathiyagarajans-projects.vercel.app",
        "https://*.vercel.app",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers - THIS IS CRITICAL
app.include_router(auth_routes.router)        # ← Make sure this is present
app.include_router(watchlist_routes.router)
app.include_router(checkpoint_routes.router)
app.include_router(market_routes.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/me")
def get_current_user_info(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "created_at": current_user.created_at
    }