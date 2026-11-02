"""
Standalone CLI script to run the STRATZ data scraper and update Supabase.
Usage:
    python scripts/run_scraper.py
"""
import sys
import os

# Add root directory to sys.path so 'app' imports work smoothly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.stratz import run_scraper_task

def main():
    print("=" * 60)
    print("Starting STRATZ Dota 2 Scraper...")
    print("=" * 60)
    try:
        count = run_scraper_task()
        print(f"SUCCESS: Successfully updated stats for {count} heroes in Supabase.")
    except Exception as e:
        print(f"ERROR: Scraper failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
