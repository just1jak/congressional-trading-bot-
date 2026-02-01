"""Real-time metrics collection for optimization system"""

import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.data.database import (
    get_database,
    OptimizationMetric,
    SignalAccuracy,
    ExecutedTrade
)
from src.utils.logger import get_logger

logger = get_logger()


class MetricsCollector:
    """Collects and stores performance metrics for AI optimization"""

    def __init__(self, db: Optional[Session] = None):
        """
        Initialize metrics collector.

        Args:
            db: Database session (optional)
        """
        self.db = db or get_database().get_session()
        logger.info("MetricsCollector initialized")

    def record_signal(
        self,
        ticker: str,
        signal: str,
        confidence: float,
        conflict_resolution_method: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Record a trading signal for later accuracy tracking.

        Args:
            ticker: Stock ticker
            signal: Signal type ('BUY', 'SELL', 'HOLD')
            confidence: Confidence score (0.0 to 1.0)
            conflict_resolution_method: Method used to resolve conflicts
            metadata: Additional context
        """
        try:
            signal_record = SignalAccuracy(
                signal_timestamp=datetime.utcnow(),
                ticker=ticker,
                predicted_signal=signal,
                predicted_confidence=confidence,
                conflict_resolution_method=conflict_resolution_method,
                actual_outcome=None,  # Will be updated when trade closes
                actual_pnl_pct=None
            )

            self.db.add(signal_record)
            self.db.commit()

            logger.debug(f"Recorded signal: {ticker} {signal} (conf={confidence:.2f})")

        except Exception as e:
            logger.error(f"Error recording signal: {e}", exc_info=True)
            self.db.rollback()

    def record_trade_outcome(
        self,
        ticker: str,
        pnl_pct: float,
        executed_trade_id: Optional[int] = None
    ) -> None:
        """
        Update signal accuracy with actual trade outcome.

        Args:
            ticker: Stock ticker
            pnl_pct: Profit/loss percentage
            executed_trade_id: ID of executed trade
        """
        try:
            # Find most recent signal for this ticker
            recent_signal = (
                self.db.query(SignalAccuracy)
                .filter(
                    SignalAccuracy.ticker == ticker,
                    SignalAccuracy.actual_outcome.is_(None)
                )
                .order_by(SignalAccuracy.signal_timestamp.desc())
                .first()
            )

            if recent_signal:
                # Determine outcome
                if pnl_pct > 0:
                    outcome = 'profit'
                elif pnl_pct < 0:
                    outcome = 'loss'
                else:
                    outcome = 'breakeven'

                recent_signal.actual_outcome = outcome
                recent_signal.actual_pnl_pct = pnl_pct
                recent_signal.executed_trade_id = executed_trade_id

                self.db.commit()

                logger.info(f"Updated signal outcome: {ticker} {outcome} ({pnl_pct:.2%})")

        except Exception as e:
            logger.error(f"Error recording trade outcome: {e}", exc_info=True)
            self.db.rollback()

    def calculate_and_store_metrics(
        self,
        window_days: int = 30
    ) -> Dict[str, float]:
        """
        Calculate performance metrics and store them.

        Args:
            window_days: Rolling window in days

        Returns:
            Dictionary of calculated metrics
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=window_days)

            # Get closed trades in window
            closed_trades = (
                self.db.query(ExecutedTrade)
                .filter(
                    ExecutedTrade.status == 'closed',
                    ExecutedTrade.exit_date >= cutoff_date
                )
                .all()
            )

            if not closed_trades:
                logger.warning(f"No closed trades in last {window_days} days")
                return {}

            # Calculate metrics
            metrics = self._calculate_metrics(closed_trades)

            # Store each metric
            timestamp = datetime.utcnow()
            for metric_name, value in metrics.items():
                metric_record = OptimizationMetric(
                    timestamp=timestamp,
                    window_days=window_days,
                    metric_type=metric_name,
                    metric_value=value,
                    metadata=json.dumps({'trade_count': len(closed_trades)})
                )
                self.db.add(metric_record)

            self.db.commit()

            logger.info(f"Stored {len(metrics)} metrics for {window_days}d window")
            return metrics

        except Exception as e:
            logger.error(f"Error calculating metrics: {e}", exc_info=True)
            self.db.rollback()
            return {}

    def _calculate_metrics(self, trades: List[ExecutedTrade]) -> Dict[str, float]:
        """
        Calculate performance metrics from trades.

        Args:
            trades: List of executed trades

        Returns:
            Dictionary of metrics
        """
        if not trades:
            return {}

        # Basic metrics
        total_trades = len(trades)
        profitable_trades = [t for t in trades if t.profit_loss_pct and t.profit_loss_pct > 0]
        losing_trades = [t for t in trades if t.profit_loss_pct and t.profit_loss_pct < 0]

        win_rate = len(profitable_trades) / total_trades if total_trades > 0 else 0.0

        # Returns
        total_return_pct = sum(t.profit_loss_pct or 0 for t in trades)
        avg_return_pct = total_return_pct / total_trades if total_trades > 0 else 0.0

        # Profit factor
        total_profit = sum(t.profit_loss or 0 for t in profitable_trades)
        total_loss = abs(sum(t.profit_loss or 0 for t in losing_trades))
        profit_factor = total_profit / total_loss if total_loss > 0 else 0.0

        # Drawdown (simplified)
        returns = [t.profit_loss_pct or 0 for t in trades]
        cumulative = 0
        peak = 0
        max_drawdown = 0

        for ret in returns:
            cumulative += ret
            if cumulative > peak:
                peak = cumulative
            drawdown = peak - cumulative
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # Sharpe ratio (simplified - assuming daily returns)
        if len(returns) > 1:
            import statistics
            mean_return = statistics.mean(returns)
            std_return = statistics.stdev(returns)
            sharpe_ratio = (mean_return / std_return * (252 ** 0.5)) if std_return > 0 else 0.0
        else:
            sharpe_ratio = 0.0

        return {
            'total_trades': float(total_trades),
            'win_rate': win_rate,
            'avg_return_pct': avg_return_pct,
            'total_return_pct': total_return_pct,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio
        }

    def get_recent_metrics(
        self,
        window_days: int = 30,
        lookback_hours: int = 24
    ) -> Dict[str, float]:
        """
        Get most recent metrics for a given window.

        Args:
            window_days: Metric window
            lookback_hours: How far back to look for metrics

        Returns:
            Dictionary of latest metrics
        """
        try:
            cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)

            metrics = (
                self.db.query(OptimizationMetric)
                .filter(
                    OptimizationMetric.window_days == window_days,
                    OptimizationMetric.timestamp >= cutoff
                )
                .order_by(OptimizationMetric.timestamp.desc())
                .all()
            )

            # Get most recent value for each metric type
            result = {}
            seen = set()
            for m in metrics:
                if m.metric_type not in seen:
                    result[m.metric_type] = m.metric_value
                    seen.add(m.metric_type)

            return result

        except Exception as e:
            logger.error(f"Error getting recent metrics: {e}", exc_info=True)
            return {}

    def get_signal_accuracy_by_method(
        self,
        days_back: int = 30
    ) -> Dict[str, Dict[str, float]]:
        """
        Get signal accuracy broken down by conflict resolution method.

        Args:
            days_back: Number of days to analyze

        Returns:
            Dictionary with accuracy stats per method
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)

            signals = (
                self.db.query(SignalAccuracy)
                .filter(
                    SignalAccuracy.signal_timestamp >= cutoff_date,
                    SignalAccuracy.actual_outcome.isnot(None)
                )
                .all()
            )

            if not signals:
                return {}

            # Group by method
            by_method = {}
            for sig in signals:
                method = sig.conflict_resolution_method or 'unknown'
                if method not in by_method:
                    by_method[method] = []
                by_method[method].append(sig)

            # Calculate accuracy for each method
            results = {}
            for method, method_signals in by_method.items():
                total = len(method_signals)
                correct = sum(
                    1 for s in method_signals
                    if (s.predicted_signal == 'BUY' and s.actual_outcome == 'profit') or
                       (s.predicted_signal == 'SELL' and s.actual_outcome == 'profit')
                )

                avg_confidence = sum(s.predicted_confidence for s in method_signals) / total
                avg_pnl = sum(s.actual_pnl_pct or 0 for s in method_signals) / total

                results[method] = {
                    'accuracy': correct / total if total > 0 else 0.0,
                    'total_signals': total,
                    'avg_confidence': avg_confidence,
                    'avg_pnl_pct': avg_pnl
                }

            return results

        except Exception as e:
            logger.error(f"Error calculating signal accuracy: {e}", exc_info=True)
            return {}

    def get_metric_trend(
        self,
        metric_type: str,
        window_days: int = 30,
        lookback_days: int = 90
    ) -> List[tuple]:
        """
        Get time series data for a metric.

        Args:
            metric_type: Type of metric to retrieve
            window_days: Rolling window size
            lookback_days: How far back to look

        Returns:
            List of (timestamp, value) tuples
        """
        try:
            cutoff = datetime.utcnow() - timedelta(days=lookback_days)

            metrics = (
                self.db.query(OptimizationMetric)
                .filter(
                    OptimizationMetric.metric_type == metric_type,
                    OptimizationMetric.window_days == window_days,
                    OptimizationMetric.timestamp >= cutoff
                )
                .order_by(OptimizationMetric.timestamp.asc())
                .all()
            )

            return [(m.timestamp, m.metric_value) for m in metrics]

        except Exception as e:
            logger.error(f"Error getting metric trend: {e}", exc_info=True)
            return []
