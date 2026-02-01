"""Core backtesting engine for congressional trading strategies"""

import yfinance as yf
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import time

from src.data.database import CongressionalTrade, get_database
from src.backtest.strategies import BaseStrategy
from src.backtest.metrics import calculate_metrics, calculate_holding_period_metrics
from src.utils.logger import get_logger

logger = get_logger()


@dataclass
class BacktestResult:
    """Single backtest trade result"""
    ticker: str
    politician_name: str
    transaction_date: datetime
    disclosure_date: datetime
    entry_date: datetime
    exit_date: datetime
    entry_price: float
    exit_price: float
    return_pct: float
    holding_period: int
    estimated_amount: Optional[float] = None


class BacktestEngine:
    """
    Main backtesting engine for congressional trading strategies.

    Handles:
    - Loading trades from database
    - Accounting for 45-day disclosure lag
    - Fetching historical prices
    - Simulating trades at different holding periods
    - Calculating performance metrics
    """

    def __init__(
        self,
        database_url: str = "sqlite:///data/congressional_trades.db",
        holding_periods: Optional[List[int]] = None
    ):
        """
        Initialize backtest engine.

        Args:
            database_url: Database connection string
            holding_periods: List of holding periods in days (default: [30, 60, 90])
        """
        self.db = get_database(database_url)
        self.holding_periods = holding_periods or [30, 60, 90]
        self.price_cache = {}  # Cache for historical prices

    def run_backtest(
        self,
        strategy: BaseStrategy,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        max_trades: Optional[int] = None,
        progress_callback=None
    ) -> Dict:
        """
        Run a backtest for a given strategy.

        Args:
            strategy: Trading strategy to test
            start_date: Start date for backtest (default: earliest trade)
            end_date: End date for backtest (default: today)
            max_trades: Maximum number of trades to test (for quick tests)
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with backtest results and metrics
        """
        logger.info(f"Starting backtest for strategy: {strategy.name}")

        # Load trades from database
        trades = self._load_trades(start_date, end_date)
        logger.info(f"Loaded {len(trades)} trades from database")

        # Filter trades using strategy
        filtered_trades = strategy.filter_trades(trades)
        logger.info(f"Strategy filtered to {len(filtered_trades)} trades")

        # Limit trades if requested
        if max_trades:
            filtered_trades = filtered_trades[:max_trades]
            logger.info(f"Limited to {max_trades} trades for testing")

        # Run backtest on filtered trades
        all_results = []
        failed_tickers = set()

        for i, trade in enumerate(filtered_trades):
            if progress_callback and i % 10 == 0:
                progress_callback(i, len(filtered_trades))

            # Simulate trade at each holding period
            for holding_period in self.holding_periods:
                result = self._simulate_trade(trade, holding_period)

                if result:
                    all_results.append(result)
                else:
                    failed_tickers.add(trade.ticker)

            # Rate limiting for yfinance
            if i % 50 == 0 and i > 0:
                time.sleep(1)

        logger.info(f"Completed backtest: {len(all_results)} successful trades")
        if failed_tickers:
            logger.warning(f"Failed to get prices for {len(failed_tickers)} tickers: {list(failed_tickers)[:10]}")

        # Calculate metrics
        results_dict = [self._result_to_dict(r) for r in all_results]
        overall_metrics = calculate_metrics(results_dict)
        period_metrics = calculate_holding_period_metrics(results_dict, self.holding_periods)

        return {
            'strategy': strategy.name,
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None,
            'total_trades_tested': len(filtered_trades),
            'successful_trades': len(all_results),
            'failed_tickers': list(failed_tickers),
            'overall_metrics': overall_metrics,
            'metrics_by_holding_period': period_metrics,
            'raw_results': all_results[:100],  # Limit to first 100 for display
        }

    def _load_trades(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> List[CongressionalTrade]:
        """
        Load trades from database within date range.

        Args:
            start_date: Start date filter
            end_date: End date filter

        Returns:
            List of congressional trades
        """
        session = self.db.get_session()

        try:
            query = session.query(CongressionalTrade)

            # Filter by disclosure date (when we would have known about it)
            if start_date:
                query = query.filter(CongressionalTrade.disclosure_date >= start_date)
            if end_date:
                query = query.filter(CongressionalTrade.disclosure_date <= end_date)

            # Order by disclosure date
            query = query.order_by(CongressionalTrade.disclosure_date)

            trades = query.all()

            # Detach from session
            session.expunge_all()

            return trades

        finally:
            session.close()

    def _simulate_trade(
        self,
        trade: CongressionalTrade,
        holding_period: int
    ) -> Optional[BacktestResult]:
        """
        Simulate a single trade with a given holding period.

        Args:
            trade: Congressional trade to simulate
            holding_period: Number of days to hold

        Returns:
            BacktestResult or None if failed
        """
        try:
            # Entry date is disclosure date (when we learn about it)
            # This accounts for the 45-day lag automatically
            entry_date = trade.disclosure_date

            # Exit date is entry + holding period
            exit_date = entry_date + timedelta(days=holding_period)

            # Don't trade in the future
            if exit_date > datetime.now().date():
                return None

            # Get historical prices
            entry_price = self._get_price(trade.ticker, entry_date)
            exit_price = self._get_price(trade.ticker, exit_date)

            if entry_price is None or exit_price is None:
                return None

            # Calculate return
            return_pct = ((exit_price - entry_price) / entry_price) * 100

            return BacktestResult(
                ticker=trade.ticker,
                politician_name=trade.politician_name,
                transaction_date=trade.transaction_date,
                disclosure_date=trade.disclosure_date,
                entry_date=entry_date,
                exit_date=exit_date,
                entry_price=entry_price,
                exit_price=exit_price,
                return_pct=return_pct,
                holding_period=holding_period,
                estimated_amount=trade.estimated_amount
            )

        except Exception as e:
            logger.debug(f"Error simulating trade for {trade.ticker}: {e}")
            return None

    def _get_price(self, ticker: str, date: datetime) -> Optional[float]:
        """
        Get historical price for a ticker on a specific date.

        Uses caching to avoid redundant API calls.

        Args:
            ticker: Stock ticker symbol
            date: Date to get price for

        Returns:
            Adjusted close price or None if unavailable
        """
        # Check cache first
        cache_key = f"{ticker}_{date.isoformat()}"
        if cache_key in self.price_cache:
            return self.price_cache[cache_key]

        try:
            # Convert date to datetime if needed
            if isinstance(date, datetime):
                date = date.date()

            # Fetch data for a window around the date
            start = date - timedelta(days=7)
            end = date + timedelta(days=7)

            stock = yf.Ticker(ticker)
            hist = stock.history(start=start, end=end)

            if hist.empty:
                logger.debug(f"No price data for {ticker} around {date}")
                self.price_cache[cache_key] = None
                return None

            # Find closest date
            hist.index = hist.index.date
            if date in hist.index:
                price = float(hist.loc[date]['Close'])
            else:
                # Use nearest available date
                nearest_idx = min(hist.index, key=lambda d: abs((d - date).days))
                price = float(hist.loc[nearest_idx]['Close'])
                logger.debug(f"Using {nearest_idx} price for {ticker} (requested {date})")

            self.price_cache[cache_key] = price
            return price

        except Exception as e:
            logger.debug(f"Error fetching price for {ticker} on {date}: {e}")
            self.price_cache[cache_key] = None
            return None

    def _result_to_dict(self, result: BacktestResult) -> Dict:
        """Convert BacktestResult to dictionary for metrics calculation"""
        return {
            'ticker': result.ticker,
            'politician_name': result.politician_name,
            'entry_date': result.entry_date,
            'exit_date': result.exit_date,
            'entry_price': result.entry_price,
            'exit_price': result.exit_price,
            'return_pct': result.return_pct,
            'holding_period': result.holding_period,
            'estimated_amount': result.estimated_amount,
        }

    def clear_cache(self):
        """Clear the price cache"""
        self.price_cache.clear()
        logger.info("Price cache cleared")
