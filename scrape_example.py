#!/usr/bin/env python3
"""
Example script demonstrating how to scrape House trading data.

This script shows how to:
1. Check available years
2. Scrape multiple years of data
3. View the results
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.data.database import init_database, get_database
from src.data.collectors.congressional_trades import CongressionalTradeCollector
from src.utils.logger import setup_logger


def main():
    """Run example scraping"""

    # Setup logging
    setup_logger()

    # Initialize database
    print("Initializing database...")
    db = init_database()

    # Create collector
    collector = CongressionalTradeCollector(db=db.get_session())

    # Check available years
    print("\nChecking available years...")
    years = collector.get_house_available_years()
    print(f"Available years: {years}")

    if not years:
        print("No years found. Check internet connection.")
        return

    # Scrape recent year (faster for demo)
    year_to_scrape = years[-1]  # Most recent year
    print(f"\nScraping {year_to_scrape} House data...")
    print("(This may take 1-2 minutes)\n")

    # Progress callback
    def show_progress(current, total):
        percent = (current / total) * 100
        print(f"  Progress: {current}/{total} members ({percent:.1f}%)")

    # Scrape the data
    count = collector.scrape_house_data(
        start_year=year_to_scrape,
        end_year=year_to_scrape,
        progress_callback=show_progress
    )

    print(f"\n✓ Successfully scraped {count} trades from {year_to_scrape}!")

    # Show some statistics
    session = db.get_session()
    from src.data.database import CongressionalTrade
    from sqlalchemy import func

    total_trades = session.query(CongressionalTrade).count()
    unique_politicians = session.query(func.count(func.distinct(CongressionalTrade.politician_name))).scalar()
    unique_tickers = session.query(func.count(func.distinct(CongressionalTrade.ticker))).scalar()

    print("\n" + "=" * 60)
    print("Database Statistics")
    print("=" * 60)
    print(f"Total trades in database: {total_trades}")
    print(f"Unique politicians: {unique_politicians}")
    print(f"Unique tickers: {unique_tickers}")
    print("=" * 60)

    print("\nNext steps:")
    print("  1. Scrape more years: python scrape_example.py")
    print("  2. View recommendations: python -m src.cli.cli recommendations")
    print("  3. Analyze a ticker: python -m src.cli.cli analyze NVDA")


if __name__ == "__main__":
    main()
