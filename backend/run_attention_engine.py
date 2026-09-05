import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.significance_engine_v2 import process_events

if __name__ == "__main__":
    print("🎯 Running Attention Score Engine...")
    print("=" * 50)
    process_events()
    print("=" * 50)
    print("✅ Done!")