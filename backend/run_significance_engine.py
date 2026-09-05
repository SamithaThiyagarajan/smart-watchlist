import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.significance_engine import process_events_and_snapshots

if __name__ == "__main__":
    print("🚀 Running Significance Engine...")
    print("=" * 50)
    process_events_and_snapshots()
    print("=" * 50)
    print("✅ Significance Engine complete!")