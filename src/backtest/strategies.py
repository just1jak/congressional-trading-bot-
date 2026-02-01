"""Trading strategies for backtesting congressional trades"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from src.data.database import CongressionalTrade


class BaseStrategy(ABC):
    """Base class for all trading strategies"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def filter_trades(self, trades: List[CongressionalTrade]) -> List[CongressionalTrade]:
        """
        Filter trades based on strategy criteria.

        Args:
            trades: List of all congressional trades

        Returns:
            List of trades that pass the strategy filter
        """
        pass

    @abstractmethod
    def get_position_size(self, trade: CongressionalTrade) -> float:
        """
        Determine position size for a trade.

        Args:
            trade: Congressional trade

        Returns:
            Position size as a fraction of portfolio (0.0 to 1.0)
        """
        pass


class FollowAllStrategy(BaseStrategy):
    """
    Strategy A: Follow All Trades

    Follows every congressional purchase disclosed, accounting for the 45-day lag.
    This is the baseline strategy to test if congressional trading has any edge.
    """

    def __init__(
        self,
        min_trade_value: Optional[float] = None,
        exclude_sales: bool = True
    ):
        """
        Initialize Follow All strategy.

        Args:
            min_trade_value: Minimum estimated trade value to follow (optional filter)
            exclude_sales: If True, only follow purchases (default: True)
        """
        super().__init__(
            name="Follow All Trades",
            description="Follow every congressional purchase with 45-day disclosure lag"
        )
        self.min_trade_value = min_trade_value
        self.exclude_sales = exclude_sales

    def filter_trades(self, trades: List[CongressionalTrade]) -> List[CongressionalTrade]:
        """
        Filter trades to only purchases (and optionally by minimum value).

        Args:
            trades: All congressional trades

        Returns:
            Filtered trades to backtest
        """
        filtered = []

        for trade in trades:
            # Skip sales if configured
            if self.exclude_sales:
                if trade.transaction_type.lower() in ['sale', 'sell']:
                    continue

            # Skip if below minimum value
            if self.min_trade_value and trade.estimated_amount:
                if trade.estimated_amount < self.min_trade_value:
                    continue

            # Must have a valid ticker
            if not trade.ticker or len(trade.ticker) > 5:
                continue

            filtered.append(trade)

        return filtered

    def get_position_size(self, trade: CongressionalTrade) -> float:
        """
        Equal weight all positions.

        Args:
            trade: Congressional trade

        Returns:
            Fixed position size (e.g., 1% of portfolio per trade)
        """
        # Equal weight: allocate 1% of portfolio to each trade
        return 0.01


class TopPerformersStrategy(BaseStrategy):
    """
    Strategy B: Follow Top Performers

    Only follow trades from politicians who have historically outperformed.
    Requires analyzing past performance and ranking politicians.
    """

    def __init__(
        self,
        lookback_days: int = 180,
        top_n_politicians: int = 10,
        min_trades_required: int = 5
    ):
        """
        Initialize Top Performers strategy.

        Args:
            lookback_days: Days to look back for performance calculation
            top_n_politicians: Number of top performers to follow
            min_trades_required: Minimum trades needed to be considered
        """
        super().__init__(
            name="Follow Top Performers",
            description=f"Follow trades from top {top_n_politicians} performing politicians"
        )
        self.lookback_days = lookback_days
        self.top_n_politicians = top_n_politicians
        self.min_trades_required = min_trades_required
        self.top_politicians = set()  # Will be populated during backtest

    def filter_trades(self, trades: List[CongressionalTrade]) -> List[CongressionalTrade]:
        """
        Filter to only trades from top performing politicians.

        Note: This requires the backtest engine to update top_politicians
        periodically based on rolling performance.

        Args:
            trades: All congressional trades

        Returns:
            Trades from top performers only
        """
        if not self.top_politicians:
            # First iteration: return all purchases to establish baseline
            return [t for t in trades if t.transaction_type.lower() in ['purchase', 'buy']]

        # Filter to top performers
        filtered = []
        for trade in trades:
            if trade.transaction_type.lower() not in ['purchase', 'buy']:
                continue

            if trade.politician_name in self.top_politicians:
                filtered.append(trade)

        return filtered

    def get_position_size(self, trade: CongressionalTrade) -> float:
        """
        Larger position size for top performers.

        Args:
            trade: Congressional trade

        Returns:
            Position size (2% for top performers)
        """
        return 0.02

    def update_top_politicians(self, politician_performance: Dict[str, float]):
        """
        Update the list of top performing politicians.

        Args:
            politician_performance: Dict mapping politician name to avg return
        """
        # Filter politicians with enough trades
        # Sort by performance and take top N
        sorted_politicians = sorted(
            politician_performance.items(),
            key=lambda x: x[1],
            reverse=True
        )

        self.top_politicians = set([
            name for name, _ in sorted_politicians[:self.top_n_politicians]
        ])


class LargeTradesStrategy(BaseStrategy):
    """
    Strategy C: Follow Large Trades Only

    Only follow trades above a certain threshold (e.g., $50K+).
    Hypothesis: Larger trades may signal higher conviction.
    """

    def __init__(self, min_trade_value: float = 50000):
        """
        Initialize Large Trades strategy.

        Args:
            min_trade_value: Minimum trade value in dollars
        """
        super().__init__(
            name="Follow Large Trades",
            description=f"Follow only trades above ${min_trade_value:,.0f}"
        )
        self.min_trade_value = min_trade_value

    def filter_trades(self, trades: List[CongressionalTrade]) -> List[CongressionalTrade]:
        """
        Filter to only large purchases.

        Args:
            trades: All congressional trades

        Returns:
            Large trades only
        """
        filtered = []

        for trade in trades:
            # Only purchases
            if trade.transaction_type.lower() not in ['purchase', 'buy']:
                continue

            # Must have estimated amount above threshold
            if trade.estimated_amount and trade.estimated_amount >= self.min_trade_value:
                filtered.append(trade)

        return filtered

    def get_position_size(self, trade: CongressionalTrade) -> float:
        """
        Position size scales with trade value.

        Args:
            trade: Congressional trade

        Returns:
            Position size (1-3% based on trade size)
        """
        if not trade.estimated_amount:
            return 0.01

        # Scale position size: $50K = 1%, $500K+ = 3%
        if trade.estimated_amount >= 500000:
            return 0.03
        elif trade.estimated_amount >= 100000:
            return 0.02
        else:
            return 0.01
