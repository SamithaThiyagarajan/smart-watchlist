# Smart Watchlist

> Don't open a watchlist and scan 20 stocks. Open Smart Watchlist and understand what changed while you were away.

Built for CODE 2026 — Groww's engineering hackathon.

---

## Status

- **Local development**: fully working end-to-end (frontend + backend + database).
- **Deployed**: fully working end-to-end — frontend, backend, and production database are all live and connected.

| Service | URL |
|---|---|
| Frontend — Vercel | [https://frontend-pi-seven-5jrqkk6pea.vercel.app](https://frontend-pi-seven-5jrqkk6pea.vercel.app) |
| Backend API — Render | [https://smart-watchlist-backend-hv03.onrender.com](https://smart-watchlist-backend-hv03.onrender.com) |
| API Docs | [https://smart-watchlist-backend-hv03.onrender.com/docs](https://smart-watchlist-backend-hv03.onrender.com/docs) |

---

## The problem with a normal watchlist

A normal watchlist answers "what's the price now?" That creates information overload: a 2% move might be completely normal for one stock and a major surprise for another. And a move that's statistically ordinary for a stock can still matter a lot if a user holds a large position in it.

The real question isn't "did the price change?" It's **"what actually deserves my attention?"**

## What this does

When you return to the app, instead of scanning every stock, you see **"Since you last checked"** — only the changes that meaningfully deserve attention, ranked by an explainable score.

Every change is evaluated across independent signals:

- **Company events** — earnings, acquisitions, management changes, regulatory actions, dividends, splits
- **Statistical anomaly** — is this move unusual for *this specific stock's* own volatility, and was it accompanied by unusual volume?
- **Market context** — is the stock diverging from the broader market, or moving with it?
- **Sector correlation** — is the stock diverging from its own sector, based on historical correlation and current sector breadth?
- **Rupee relevance** — how much does this move actually impact *this user's* real position, in rupees? A move that's statistically "normal" can still be worth flagging if it represents a large impact on someone's actual holdings — this is what lets the system catch changes that pure anomaly detection would miss.

No single signal gates the others — each contributes independently, so a big-but-statistically-normal move still gets surfaced.

Each flagged item shows **why** it was flagged, in plain language — never a black-box score.

## Facts, not forecasts

Smart Watchlist never predicts what will happen and never recommends buying or selling. It only states what happened, how unusual it was, and what context surrounds it. This is a deliberate choice, not a limitation — it keeps the product safe, trustworthy, and defensible.

## Features

| Feature | Description |
|---|---|
| Attention engine | Event + statistical anomaly + market context + rupee relevance, combined into one explainable score |
| Since you last checked | Server-side checkpoint per user — shows only what's new since their last visit, identical across devices |
| Sector correlation | Uses historical sector correlation to identify stock-specific divergence |
| Rupee relevance | Calculates real money impact on the user's actual position, not just percentage move |
| Stale data handling | Prices carry a freshness timestamp; delayed data is flagged, never shown as live |
| Cross-device persistence | Watchlist and checkpoint state live server-side, keyed by user, not device |
| Responsive UI | Works on phone and desktop from one codebase |

## The attention engine

```
ATTENTION SCORE (0–100, capped)

Event significance      — up to 40 points
  earnings, acquisitions, management changes, regulatory actions, dividends, splits

Statistical anomaly     — up to 30 points
  price move vs. the stock's own volatility (z-score), volume spikes

Market context          — up to 20 points
  stock's move vs. the broader market

Sector correlation      — up to 15 points
  historical correlation with the sector, current divergence,
  and sector breadth

Rupee relevance         — up to 10 points
  actual rupee impact on the user's position

High attention   ≥ 60
Worth knowing    35–59
Normal           < 35
```

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python) |
| Database | PostgreSQL |
| Frontend | React + Tailwind CSS|
| Auth | JWT |
| Deployment | Render (backend) + Vercel (frontend) |

## Architecture

- The attention engine computes a score once per event, at ingestion — not recomputed per user per request — so the API layer stays stateless and can scale horizontally.
- User state (watchlist, last-checked timestamp) lives server-side in Postgres, keyed by user ID rather than device, so it's identical across phone and laptop.

## Running it locally

### Prerequisites
- Python 3.9+
- Node.js 16+
- Docker (for local PostgreSQL)

### 1. Clone

```bash
git clone https://github.com/SamithaThiyagarajan/smart-watchlist.git
cd smart-watchlist
```

### 2. Start PostgreSQL

```bash
docker compose up -d
```

### 3. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env with your local DB credentials

python -c "from app.database import engine, Base; from app import models; Base.metadata.create_all(bind=engine)"

uvicorn app.main:app --reload
```

API: `http://localhost:8000` · Docs: `http://localhost:8000/docs`

### 4. Frontend

```bash
cd frontend
npm install
npm start
```

Frontend: `http://localhost:3000`

### 5. Generate sample market data (optional)

```bash
cd backend
python run_worker.py
python -c "from app.significance_engine import process_events; process_events()"
```

## API

**Auth**: `POST /auth/signup`, `POST /auth/login`

**Watchlist**: `GET /watchlist/`, `POST /watchlist/`, `DELETE /watchlist/{symbol}`, `GET /watchlist/freshness`

**Digest**: `GET /digest/since-last-check`, `POST /digest/checkpoint/reset`, `GET /digest/checkpoint/status`

## Design decisions

**Why facts, not forecasts?** We never predict what will happen. We only show what happened and why it matters — a safety/liability decision as much as a product one.

**Why rupee relevance is the key differentiator**: a stock can move a normal amount for its own volatility, but if a user holds a large position, that "normal" move can still be a significant rupee impact. Traditional watchlists primarily surface percentage or price movement; Smart Watchlist additionally considers the user's actual rupee exposure.

**What was deliberately left out for this build**: real market data (a simulated feed was used instead, to keep the focus on the attention-scoring logic rather than third-party API integration), and a caching layer, since neither was needed to demonstrate the core idea at hackathon scale.

## What I'd build next

Per-symbol status directly on the watchlist table (currently the full attention score for every symbol, not just digest-featured ones, isn't yet surfaced there — this was cut deliberately to avoid shipping an inconsistent status label rather than leave it wrong), per-user signal weighting, an ongoing/unresolved-event tracker (e.g. an active trading halt that should stay surfaced until resolved, not just "new since last check"), and a real market data feed in place of the simulated one.

---

This isn't a watchlist with more features. It's a filter for what deserves your attention.

Built by Samitha Thiyagarajan for CODE 2026.
