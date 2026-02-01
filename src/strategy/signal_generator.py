"""Trading signal generation from congressional trades"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict
from datetime import date, timedelta
from collections import defaultdict

from sqlalchemy.orm import Session

from src.data.database import CongressionalTrade, get_database
from src.data.collectors.congressional_trades import CongressionalTradeCollector
from src.utils.logger import get_logger
from src.utils.helpers import load_config

logger = get_logger()

# Import metrics collector (lazy import to avoid circular dependencies)
_metrics_collector = None


def get_metrics_collector():
    """Get or create metrics collector instance"""
    global _metrics_collector
    if _metrics_collector is None:
        try:
            from src.optimization.metrics_collector import MetricsCollector
            _metrics_collector = MetricsCollector()
        except Exception as e:
            logger.warning(f"Could not initialize MetricsCollector: {e}")
            _metrics_collector = None
    return _metrics_collector


class Signal(Enum):
    """Trading signal types"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class TradeSignal:
    """Trading signal with metadata"""
    ticker: str
    signal: Signal
    confidence: float  # 0.0 to 1.0
    supporting_trades: List[CongressionalTrade]
    conflicting_trades: List[CongressionalTrade]
    reason: str


class SignalGenerator:
    """Generates trading signals from congressional trade data"""

    def __init__(self, db: Optional[Session] = None):
        """
        Initialize signal generator.

        Args:
            db: Database session (optional)
        """
        self.db = db or get_database().get_session()
        self.collector = CongressionalTradeCollector(db=self.db)

        # Load configuration
        app_config = load_config()
        strategy_config = app_config.get('strategy', {})

        self.conflict_resolution = strategy_config.get('conflict_resolution', 'dollar_weighted')
        self.buy_threshold_multiplier = strategy_config.get('buy_threshold_multiplier', 1.5)
        self.trade_window_days = strategy_config.get('trade_aggregation_window_days', 7)
        self.min_confidence = strategy_config.get('min_confidence', 0.6)

        logger.info(f"Signal Generator initialized with conflict resolution: {self.conflict_resolution}")

    def analyze_ticker(
        self,
        ticker: str,
        lookback_days: int = 30
    ) -> TradeSignal:
        """
        Analyze congressional trades for a ticker and generate signal.

        Args:
            ticker: Stock ticker symbol
            lookback_days: Number of days to analyze

        Returns:
            TradeSignal object
        """
        # Get recent trades for this ticker
        trades = self.collector.get_trades_for_ticker(ticker, days_back=lookback_days)

        if not trades:
            return TradeSignal(
                ticker=ticker,
                signal=Signal.HOLD,
                confidence=0.0,
                supporting_trades=[],
                conflicting_trades=[],
                reason="No recent congressional trades found"
            )

        # Separate buys and sells
        buys = [t for t in trades if t.transaction_type.lower() in ['purchase', 'buy']]
        sells = [t for t in trades if t.transaction_type.lower() in ['sale', 'sell']]

        # Analyze based on conflict resolution method
        if self.conflict_resolution == 'dollar_weighted':
            signal = self._analyze_dollar_weighted(buys, sells, ticker)
        elif self.conflict_resolution == 'unanimous_only':
            signal = self._analyze_unanimous_only(buys, sells, ticker)
        elif self.conflict_resolution == 'senator_track_record':
            signal = self._analyze_by_track_record(buys, sells, ticker)
        else:
            # Default to dollar weighted
            signal = self._analyze_dollar_weighted(buys, sells, ticker)

        # Record signal for optimization tracking
        try:
            collector = get_metrics_collector()
            if collector and signal.signal != Signal.HOLD:
                collector.record_signal(
                    ticker=ticker,
                    signal=signal.signal.value,
                    confidence=signal.confidence,
                    conflict_resolution_method=self.conflict_resolution
                )
        except Exception as e:
            logger.debug(f"Could not record signal for optimization: {e}")

        return signal

    def _analyze_dollar_weighted(
        self,
        buys: List[CongressionalTrade],
        sells: List[CongressionalTrade],
        ticker: str
    ) -> TradeSignal:
        """
        Analyze trades using dollar-weighted method.

        Args:
            buys: List of purchase trades
            sells: List of sale trades
            ticker: Stock ticker

        Returns:
            TradeSignal
        """
        # Calculate total dollar amounts
        buy_weight = sum(t.estimated_amount for t in buys)
        sell_weight = sum(t.estimated_amount for t in sells)

        total_weight = buy_weight + sell_weight

        if total_weight == 0:
            return TradeSignal(
                ticker=ticker,
                signal=Signal.HOLD,
                confidence=0.0,
                supporting_trades=[],
                conflicting_trades=[],
                reason="No valid trade amounts found"
            )

        # Determine signal
        if buy_weight > sell_weight * self.buy_threshold_multiplier:
            # Strong buy signal
            confidence = min(buy_weight / (buy_weight + sell_weight), 1.0)
            return TradeSignal(
                ticker=ticker,
                signal=Signal.BUY,
                confidence=confidence,
                supporting_trades=buys,
                conflicting_trades=sells,
                reason=f"Buy trades (${buy_weight:,.0f}) outweigh sells (${sell_weight:,.0f})"
            )

        elif sell_weight > buy_weight * self.buy_threshold_multiplier:
            # Strong sell signal
            confidence = min(sell_weight / (buy_weight + sell_weight), 1.0)
            return TradeSignal(
                ticker=ticker,
                signal=Signal.SELL,
                confidence=confidence,
                supporting_trades=sells,
                conflicting_trades=buys,
                reason=f"Sell trades (${sell_weight:,.0f}) outweigh buys (${buy_weight:,.0f})"
            )

        else:
            # Conflicting signals
            return TradeSignal(
                ticker=ticker,
                signal=Signal.HOLD,
                confidence=0.0,
                supporting_trades=[],
                conflicting_trades=buys + sells,
                reason=f"Conflicting signals: buys ${buy_weight:,.0f}, sells ${sell_weight:,.0f}"
            )

    def _analyze_unanimous_only(
        self,
        buys: List[CongressionalTrade],
        sells: List[CongressionalTrade],
        ticker: str
    ) -> TradeSignal:
        """
        Only generate signal if all trades are in the same direction.

        Args:
            buys: List of purchase trades
            sells: List of sale trades
            ticker: Stock ticker

        Returns:
            TradeSignal
        """
        if buys and not sells:
            # All buys, no sells
            confidence = min(len(buys) / 10.0, 1.0)  # More trades = higher confidence
            return TradeSignal(
                ticker=ticker,
                signal=Signal.BUY,
                confidence=confidence,
                supporting_trades=buys,
                conflicting_trades=[],
                reason=f"Unanimous buy signal from {len(buys)} trades"
            )

        elif sells and not buys:
            # All sells, no buys
            confidence = min(len(sells) / 10.0, 1.0)
            return TradeSignal(
                ticker=ticker,
                signal=Signal.SELL,
                confidence=confidence,
                supporting_trades=sells,
                conflicting_trades=[],
                reason=f"Unanimous sell signal from {len(sells)} trades"
            )

        else:
            # Mixed signals - hold
            return TradeSignal(
                ticker=ticker,
                signal=Signal.HOLD,
                confidence=0.0,
                supporting_trades=[],
                conflicting_trades=buys + sells,
                reason=f"Mixed signals: {len(buys)} buys, {len(sells)} sells"
            )

    def _analyze_by_track_record(
        self,
        buys: List[CongressionalTrade],
        sells: List[CongressionalTrade],
        ticker: str
    ) -> TradeSignal:
        """
        Weight trades by politician's historical track record.

        Note: This requires historical performance data which would be built up over time.
        For now, falls back to dollar-weighted analysis.

        Args:
            buys: List of purchase trades
            sells: List of sale trades
            ticker: Stock ticker

        Returns:
            TradeSignal
        """
        # TODO: Implement politician performance weighting
        # For now, fall back to dollar-weighted
        logger.warning("Senator track record weighting not yet implemented, using dollar-weighted")
        return self._analyze_dollar_weighted(buys, sells, ticker)

    def get_all_recent_signals(
        self,
        lookback_days: int = 30,
        min_confidence: Optional[float] = None
    ) -> List[TradeSignal]:
        """
        Get trading signals for all tickers with recent congressional activity.

        Args:
            lookback_days: Number of days to look back
            min_confidence: Minimum confidence threshold (defaults to config)

        Returns:
            List of TradeSignal objects
        """
        if min_confidence is None:
            min_confidence = self.min_confidence

        # Get all recent trades
        start_date = date.today() - timedelta(days=lookback_days)
        all_trades = self.collector.get_historical_trades(start_date=start_date)

        # Group by ticker
        tickers = set(t.ticker for t in all_trades)

        # Generate signals for each ticker
        signals = []
        for ticker in tickers:
            signal = self.analyze_ticker(ticker, lookback_days)

            # Filter by confidence and actionable signals
            if signal.confidence >= min_confidence and signal.signal != Signal.HOLD:
                signals.append(signal)

        # Sort by confidence (highest first)
        signals.sort(key=lambda s: s.confidence, reverse=True)

        logger.info(f"Generated {len(signals)} actionable signals from {len(tickers)} tickers")
        return signals

    def get_top_recommendations(
        self,
        count: int = 10,
        lookback_days: int = 30
    ) -> List[TradeSignal]:
        """
        Get top N trade recommendations.

        Args:
            count: Number of recommendations to return
            lookback_days: Number of days to analyze

        Returns:
            List of top TradeSignal objects
        """
        all_signals = self.get_all_recent_signals(lookback_days)
        return all_signals[:count]
