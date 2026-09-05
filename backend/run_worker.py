import asyncio
from worker.market_data_generator import run_market_generator

if __name__ == "__main__":
    print("Starting market data worker...")
    print("Press Ctrl+C to stop")
    asyncio.run(run_market_generator())