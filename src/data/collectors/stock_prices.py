"""Stock price data collector"""

from datetime import datetime, date, timedelta
from typing import List, Optional, Dict
import yfinance as yf
from sqlalchemy.orm import Session

from src.data.database import StockPrice, get_database
from src.utils.logger import get_logger
from src.utils.helpers import normalize_ticker

logger = get_logger()


class StockPriceCollector:
    """Collects and caches stock price data"""

    def __init__(self, db: Optional[Session] = None):
        """
        Initialize the collector.

        Args:
            db: Database session (optional)
        """
        self.db = db or get_database().get_session()

    def get_price(
        self,
        ticker: str,
        target_date: date,
        use_cache: bool = True
    ) -> Optional[float]:
        """
        Get closing price for a ticker on a specific date.

        Args:
            ticker: Stock ticker symbol
            target_date: Date to get price for
            use_cache: Whether to use cached prices

        Returns:
            Closing price or None if not available
        """
        ticker = normalize_ticker(ticker)

        # Check cache first
        if use_cache:
            cached = self.db.query(StockPrice).filter(
                StockPrice.ticker == ticker,
                StockPrice.date == target_date
            ).first()

            if cached:
                logger.debug(f"Cache hit for {ticker} on {target_date}: ${cached.close:.2f}")
                return cached.close

        # Fetch from API
        try:
            price = self._fetch_price_from_api(ticker, target_date)

            if price:
                # Cache the result
                self._cache_price(ticker, target_date, price)
                return price['close']

        except Exception as e:
            logger.error(f"Failed to fetch price for {ticker} on {target_date}: {e}")

        return None

    def get_current_price(self, ticker: str) -> Optional[float]:
        """
        Get the current/latest price for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Current price or None if not available
        """
        ticker = normalize_ticker(ticker)

        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            # Try different price fields
            price = (
                info.get('currentPrice') or
                info.get('regularMarketPrice') or
                info.get('previousClose')
            )

            if price:
                logger.debug(f"Current price for {ticker}: ${price:.2f}")
                return float(price)

        except Exception as e:
            logger.error(f"Failed to fetch current price for {ticker}: {e}")

        return None

    def get_historical_prices(
        self,
        ticker: str,
        start_date: date,
        end_date: Optional[date] = None,
        use_cache: bool = True
    ) -> Dict[date, float]:
        """
        Get historical prices for a ticker.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date
            end_date: End date (defaults to today)
            use_cache: Whether to use cached prices

        Returns:
            Dictionary mapping dates to closing prices
        """
        ticker = normalize_ticker(ticker)

        if end_date is None:
            end_date = date.today()

        logger.info(f"Fetching historical prices for {ticker} from {start_date} to {end_date}")

        prices = {}

        # Check cache first
        if use_cache:
            cached_prices = self.db.query(StockPrice).filter(
                StockPrice.ticker == ticker,
                StockPrice.date >= start_date,
                StockPrice.date <= end_date
            ).all()

            for price_record in cached_prices:
                prices[price_record.date] = price_record.close

            logger.debug(f"Found {len(prices)} cached prices for {ticker}")

        # Determine which dates we still need
        all_dates = [start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)]
        missing_dates = [d for d in all_dates if d not in prices]

        # Fetch missing prices from API
        if missing_dates:
            try:
                fetched_prices = self._fetch_historical_from_api(ticker, min(missing_dates), max(missing_dates))

                # Cache and add to results
                for price_date, price_data in fetched_prices.items():
                    self._cache_price(ticker, price_date, price_data)
                    prices[price_date] = price_data['close']

                logger.info(f"Fetched {len(fetched_prices)} new prices for {ticker}")

            except Exception as e:
                logger.error(f"Failed to fetch historical prices for {ticker}: {e}")

        return prices

    def _fetch_price_from_api(self, ticker: str, target_date: date) -> Optional[Dict]:
        """
        Fetch a single day's price from yfinance.

        Args:
            ticker: Stock ticker symbol
            target_date: Date to fetch

        Returns:
            Dict with OHLC prices or None
        """
        # Fetch a range around the target date to handle weekends/holidays
        start = target_date - timedelta(days=7)
        end = target_date + timedelta(days=1)

        prices = self._fetch_historical_from_api(ticker, start, end)

        # Find the closest date
        if prices:
            closest_date = min(prices.keys(), key=lambda d: abs((d - target_date).days))
            return prices[closest_date]

        return None

    def _fetch_historical_from_api(
        self,
        ticker: str,
        start_date: date,
        end_date: date
    ) -> Dict[date, Dict]:
        """
        Fetch historical prices from yfinance API.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary mapping dates to price data
        """
        logger.debug(f"Fetching prices from yfinance for {ticker} ({start_date} to {end_date})")

        stock = yf.Ticker(ticker)

        # Fetch historical data
        hist = stock.history(
            start=start_date.isoformat(),
            end=(end_date + timedelta(days=1)).isoformat()  # yfinance end date is exclusive
        )

        prices = {}

        for index, row in hist.iterrows():
            price_date = index.date()

            prices[price_date] = {
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': int(row['Volume']),
                'adjusted_close': float(row.get('Close', row['Close']))  # Use Close if Adj Close not available
            }

        logger.debug(f"Fetched {len(prices)} price records for {ticker}")
        return prices

    def _cache_price(self, ticker: str, price_date: date, price_data: Dict):
        """
        Cache a price in the database.

        Args:
            ticker: Stock ticker symbol
            price_date: Date of the price
            price_data: Dict with OHLC prices
        """
        # Check if already cached
        existing = self.db.query(StockPrice).filter(
            StockPrice.ticker == ticker,
            StockPrice.date == price_date
        ).first()

        if existing:
            return

        # Create new cache entry
        price_record = StockPrice(
            ticker=ticker,
            date=price_date,
            open=price_data.get('open'),
            high=price_data.get('high'),
            low=price_data.get('low'),
            close=price_data['close'],
            volume=price_data.get('volume'),
            adjusted_close=price_data.get('adjusted_close')
        )

        self.db.add(price_record)
        self.db.commit()

        logger.debug(f"Cached price for {ticker} on {price_date}")

    def update_prices_for_tickers(self, tickers: List[str], days_back: int = 30) -> int:
        """
        Update historical prices for multiple tickers.

        Args:
            tickers: List of ticker symbols
            days_back: Number of days to fetch

        Returns:
            Number of prices updated
        """
        start_date = date.today() - timedelta(days=days_back)
        end_date = date.today()

        total_updated = 0

        for ticker in tickers:
            try:
                prices = self.get_historical_prices(ticker, start_date, end_date, use_cache=False)
                total_updated += len(prices)
                logger.info(f"Updated {len(prices)} prices for {ticker}")
            except Exception as e:
                logger.error(f"Failed to update prices for {ticker}: {e}")

        logger.info(f"Total prices updated: {total_updated}")
        return total_updated

    def clear_cache(self, ticker: Optional[str] = None, older_than_days: Optional[int] = None):
        """
        Clear cached prices.

        Args:
            ticker: Clear cache for specific ticker (optional)
            older_than_days: Clear cache older than N days (optional)
        """
        query = self.db.query(StockPrice)

        if ticker:
            query = query.filter(StockPrice.ticker == normalize_ticker(ticker))

        if older_than_days:
            cutoff_date = date.today() - timedelta(days=older_than_days)
            query = query.filter(StockPrice.date < cutoff_date)

        count = query.delete()
        self.db.commit()

        logger.info(f"Cleared {count} cached price records")
