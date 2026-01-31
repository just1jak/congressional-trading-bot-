"""Congressional trade data collector"""

from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
import requests
from bs4 import BeautifulSoup
import time
import re

from sqlalchemy.orm import Session

from src.data.database import CongressionalTrade, get_database
from src.utils.logger import get_logger
from src.utils.helpers import parse_date, parse_amount_range, normalize_ticker, normalize_politician_name

logger = get_logger()

# Import scrapers (lazy import to avoid circular dependencies)
def _get_house_scraper():
    """Lazy import of House scraper"""
    from src.data.collectors.government_scrapers import HouseDisclosureScraper
    return HouseDisclosureScraper()


class CongressionalTradeCollector:
    """Collects congressional stock trade disclosures from various sources"""

    def __init__(self, db: Optional[Session] = None):
        """
        Initialize the collector.

        Args:
            db: Database session (optional)
        """
        self.db = db or get_database().get_session()

    def fetch_recent_trades(self, days_back: int = 30) -> List[CongressionalTrade]:
        """
        Fetch recent congressional trades from all available sources.

        Args:
            days_back: Number of days to look back

        Returns:
            List of CongressionalTrade objects
        """
        logger.info(f"Fetching congressional trades from last {days_back} days...")

        all_trades = []

        # Try Senate Stock Watcher API (if available)
        try:
            trades = self._fetch_from_senate_stock_watcher(days_back)
            all_trades.extend(trades)
            logger.info(f"Fetched {len(trades)} trades from Senate Stock Watcher")
        except Exception as e:
            logger.warning(f"Failed to fetch from Senate Stock Watcher: {e}")

        # Try Capitol Trades API (if available)
        try:
            trades = self._fetch_from_capitol_trades(days_back)
            all_trades.extend(trades)
            logger.info(f"Fetched {len(trades)} trades from Capitol Trades")
        except Exception as e:
            logger.warning(f"Failed to fetch from Capitol Trades: {e}")

        # Fallback: scrape Senate EFDS (if other sources failed)
        if not all_trades:
            logger.info("Attempting to scrape from Senate EFDS...")
            try:
                trades = self._scrape_senate_efds(days_back)
                all_trades.extend(trades)
                logger.info(f"Scraped {len(trades)} trades from Senate EFDS")
            except Exception as e:
                logger.error(f"Failed to scrape Senate EFDS: {e}")

        # Remove duplicates
        all_trades = self._deduplicate_trades(all_trades)

        logger.info(f"Total unique trades collected: {len(all_trades)}")
        return all_trades

    def _fetch_from_senate_stock_watcher(self, days_back: int) -> List[CongressionalTrade]:
        """
        Fetch trades from Senate Stock Watcher API.

        Note: This is a placeholder. Actual implementation depends on API availability.

        Args:
            days_back: Number of days to look back

        Returns:
            List of trades
        """
        # Placeholder - implement when API is available
        logger.debug("Senate Stock Watcher API not yet implemented")
        return []

    def _fetch_from_capitol_trades(self, days_back: int) -> List[CongressionalTrade]:
        """
        Fetch trades from Capitol Trades API.

        Note: This is a placeholder. Actual implementation depends on API availability.

        Args:
            days_back: Number of days to look back

        Returns:
            List of trades
        """
        # Placeholder - implement when API is available
        logger.debug("Capitol Trades API not yet implemented")
        return []

    def _scrape_senate_efds(self, days_back: int) -> List[CongressionalTrade]:
        """
        Scrape trades from Senate Electronic Financial Disclosure System.

        Note: This is a simplified implementation. Real scraping would be more complex
        and need to handle pagination, CAPTCHA, etc.

        Args:
            days_back: Number of days to look back

        Returns:
            List of trades
        """
        logger.info("Direct Senate EFDS scraping requires more complex implementation")
        logger.info("For MVP, recommend using a third-party API or manual CSV import")

        # This would require:
        # 1. Navigate to efdsearch.senate.gov
        # 2. Handle search forms
        # 3. Parse PTR (Periodic Transaction Report) filings
        # 4. Extract transaction details
        #
        # Due to complexity, recommended approach is to use API or manual data import
        # for initial development and testing

        return []

    def _deduplicate_trades(self, trades: List[CongressionalTrade]) -> List[CongressionalTrade]:
        """
        Remove duplicate trades based on politician, ticker, date, and transaction type.

        Args:
            trades: List of trades (may contain duplicates)

        Returns:
            Deduplicated list
        """
        seen = set()
        unique_trades = []

        for trade in trades:
            # Create unique key
            key = (
                trade.politician_name,
                trade.ticker,
                trade.transaction_date,
                trade.transaction_type
            )

            if key not in seen:
                seen.add(key)
                unique_trades.append(trade)

        logger.info(f"Removed {len(trades) - len(unique_trades)} duplicate trades")
        return unique_trades

    def store_trade(self, trade: CongressionalTrade) -> CongressionalTrade:
        """
        Store a trade in the database.

        Args:
            trade: Trade to store

        Returns:
            Stored trade with ID
        """
        # Check if trade already exists
        existing = self.db.query(CongressionalTrade).filter(
            CongressionalTrade.politician_name == trade.politician_name,
            CongressionalTrade.ticker == trade.ticker,
            CongressionalTrade.transaction_date == trade.transaction_date,
            CongressionalTrade.transaction_type == trade.transaction_type
        ).first()

        if existing:
            logger.debug(f"Trade already exists: {trade}")
            return existing

        # Store new trade
        self.db.add(trade)
        self.db.commit()
        self.db.refresh(trade)

        logger.debug(f"Stored trade: {trade}")
        return trade

    def store_trades(self, trades: List[CongressionalTrade]) -> int:
        """
        Store multiple trades in the database.

        Args:
            trades: List of trades to store

        Returns:
            Number of new trades stored
        """
        count = 0
        for trade in trades:
            stored = self.store_trade(trade)
            if stored.id is not None and stored in trades:
                count += 1

        logger.info(f"Stored {count} new trades in database")
        return count

    def get_historical_trades(
        self,
        politician_name: Optional[str] = None,
        ticker: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        transaction_type: Optional[str] = None
    ) -> List[CongressionalTrade]:
        """
        Get historical trades from database with filtering.

        Args:
            politician_name: Filter by politician name
            ticker: Filter by ticker symbol
            start_date: Filter by start date (inclusive)
            end_date: Filter by end date (inclusive)
            transaction_type: Filter by transaction type (Purchase/Sale)

        Returns:
            List of trades matching criteria
        """
        query = self.db.query(CongressionalTrade)

        if politician_name:
            query = query.filter(CongressionalTrade.politician_name == politician_name)

        if ticker:
            query = query.filter(CongressionalTrade.ticker == ticker)

        if start_date:
            query = query.filter(CongressionalTrade.transaction_date >= start_date)

        if end_date:
            query = query.filter(CongressionalTrade.transaction_date <= end_date)

        if transaction_type:
            query = query.filter(CongressionalTrade.transaction_type == transaction_type)

        trades = query.order_by(CongressionalTrade.transaction_date.desc()).all()

        logger.info(f"Retrieved {len(trades)} trades from database")
        return trades

    def import_from_csv(self, csv_path: str) -> int:
        """
        Import trades from a CSV file.

        Expected CSV format:
        politician_name,party,ticker,transaction_type,amount_range,transaction_date,disclosure_date,asset_description

        Args:
            csv_path: Path to CSV file

        Returns:
            Number of trades imported
        """
        import csv

        logger.info(f"Importing trades from {csv_path}...")

        trades = []
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    trade = CongressionalTrade(
                        politician_name=normalize_politician_name(row['politician_name']),
                        party=row.get('party', '').strip(),
                        ticker=normalize_ticker(row['ticker']),
                        transaction_type=row['transaction_type'].strip(),
                        amount_range=row.get('amount_range', ''),
                        estimated_amount=parse_amount_range(row.get('amount_range', '')),
                        transaction_date=parse_date(row['transaction_date']),
                        disclosure_date=parse_date(row['disclosure_date']),
                        asset_description=row.get('asset_description', ''),
                        source='csv_import'
                    )
                    trades.append(trade)
                except Exception as e:
                    logger.warning(f"Failed to parse row: {row}. Error: {e}")

        count = self.store_trades(trades)
        logger.info(f"Imported {count} trades from CSV")
        return count

    def get_trades_for_ticker(
        self,
        ticker: str,
        days_back: int = 30,
        transaction_type: Optional[str] = None
    ) -> List[CongressionalTrade]:
        """
        Get all trades for a specific ticker within a time window.

        Args:
            ticker: Stock ticker symbol
            days_back: Number of days to look back
            transaction_type: Filter by Purchase or Sale

        Returns:
            List of trades for the ticker
        """
        start_date = date.today() - timedelta(days=days_back)

        return self.get_historical_trades(
            ticker=ticker,
            start_date=start_date,
            transaction_type=transaction_type
        )

    def scrape_house_data(
        self,
        start_year: int,
        end_year: Optional[int] = None,
        progress_callback=None
    ) -> int:
        """
        Scrape House of Representatives trade data from official government XML files.

        This downloads annual XML files from disclosures.house.gov and parses
        all Periodic Transaction Reports (PTRs).

        Args:
            start_year: First year to scrape (e.g., 2021)
            end_year: Last year to scrape (defaults to current year)
            progress_callback: Optional callback for progress updates

        Returns:
            Number of new trades stored in database

        Example:
            collector = CongressionalTradeCollector()
            count = collector.scrape_house_data(2021, 2023)
            print(f"Imported {count} House trades")
        """
        logger.info(f"Scraping House data from {start_year} to {end_year or 'current year'}...")

        # Get the scraper
        scraper = _get_house_scraper()

        # Scrape the data
        trades = scraper.scrape_multiple_years(start_year, end_year, progress_callback)

        # Store in database
        count = self.store_trades(trades)

        logger.info(f"Successfully scraped and stored {count} House trades")
        return count

    def get_house_available_years(self) -> List[int]:
        """
        Get list of years with available House disclosure data.

        Returns:
            List of years (e.g., [2021, 2022, 2023])
        """
        scraper = _get_house_scraper()
        return scraper.get_available_years()
