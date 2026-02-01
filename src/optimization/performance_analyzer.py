"""Multi-objective performance analysis for optimization"""

from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from src.data.database import get_database, OptimizationMetric
from src.optimization.metrics_collector import MetricsCollector
from src.utils.logger import get_logger
from src.utils.helpers import load_config

logger = get_logger()


class PerformanceAnalyzer:
    """Analyzes trading performance using multi-objective optimization"""

    def __init__(self, db: Optional[Session] = None):
        """
        Initialize performance analyzer.

        Args:
            db: Database session (optional)
        """
        self.db = db or get_database().get_session()
        self.metrics_collector = MetricsCollector(db=self.db)

        # Load optimization config
        try:
            app_config = load_config()
            opt_config = app_config.get('optimization', {})
            objectives = opt_config.get('objectives', {})

            # Multi-objective weights
            self.weights = {
                'returns': objectives.get('returns_weight', 0.30),
                'sharpe': objectives.get('sharpe_ratio_weight', 0.25),
                'win_rate': objectives.get('win_rate_weight', 0.20),
                'drawdown': objectives.get('drawdown_weight', 0.15),
                'profit_factor': objectives.get('profit_factor_weight', 0.10)
            }
        except Exception as e:
            logger.warning(f"Could not load optimization config, using defaults: {e}")
            # Default weights from plan
            self.weights = {
                'returns': 0.30,
                'sharpe': 0.25,
                'win_rate': 0.20,
                'drawdown': 0.15,
                'profit_factor': 0.10
            }

        logger.info(f"PerformanceAnalyzer initialized with weights: {self.weights}")

    def calculate_composite_score(
        self,
        window_days: int = 30
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculate multi-objective performance score.

        Args:
            window_days: Rolling window in days

        Returns:
            Tuple of (composite_score, component_scores)
        """
        try:
            # Get latest metrics
            metrics = self.metrics_collector.get_recent_metrics(window_days=window_days)

            if not metrics:
                logger.warning("No metrics available for scoring")
                return 0.0, {}

            # Normalize and weight each component
            components = {}

            # Returns (higher is better)
            returns = metrics.get('avg_return_pct', 0.0)
            components['returns'] = self._normalize_returns(returns) * self.weights['returns']

            # Sharpe ratio (higher is better)
            sharpe = metrics.get('sharpe_ratio', 0.0)
            components['sharpe'] = self._normalize_sharpe(sharpe) * self.weights['sharpe']

            # Win rate (higher is better)
            win_rate = metrics.get('win_rate', 0.0)
            components['win_rate'] = win_rate * self.weights['win_rate']

            # Drawdown (lower is better, so invert)
            drawdown = metrics.get('max_drawdown', 0.0)
            components['drawdown'] = (1 - min(drawdown, 1.0)) * self.weights['drawdown']

            # Profit factor (higher is better)
            profit_factor = metrics.get('profit_factor', 0.0)
            components['profit_factor'] = self._normalize_profit_factor(profit_factor) * self.weights['profit_factor']

            # Calculate composite score
            composite_score = sum(components.values())

            logger.info(f"Composite score: {composite_score:.4f} (window={window_days}d)")

            return composite_score, components

        except Exception as e:
            logger.error(f"Error calculating composite score: {e}", exc_info=True)
            return 0.0, {}

    def _normalize_returns(self, returns: float) -> float:
        """Normalize returns to 0-1 scale (assuming -20% to +20% range)"""
        return max(0, min(1, (returns + 0.20) / 0.40))

    def _normalize_sharpe(self, sharpe: float) -> float:
        """Normalize Sharpe ratio to 0-1 scale (assuming -2 to +3 range)"""
        return max(0, min(1, (sharpe + 2) / 5))

    def _normalize_profit_factor(self, pf: float) -> float:
        """Normalize profit factor to 0-1 scale (assuming 0 to 3 range)"""
        return max(0, min(1, pf / 3))

    def detect_performance_degradation(
        self,
        window_days: int = 30,
        threshold: float = -0.10
    ) -> Tuple[bool, Optional[str]]:
        """
        Detect if performance has degraded significantly.

        Args:
            window_days: Window to analyze
            threshold: Degradation threshold (-0.10 = 10% drop)

        Returns:
            Tuple of (is_degraded, reason)
        """
        try:
            # Get current score
            current_score, _ = self.calculate_composite_score(window_days=window_days)

            # Get historical baseline (average of last 90 days)
            baseline_score = self._get_baseline_score(lookback_days=90)

            if baseline_score == 0:
                logger.warning("No baseline score available")
                return False, None

            # Calculate degradation
            degradation = (current_score - baseline_score) / baseline_score

            if degradation <= threshold:
                reason = f"Performance degraded {degradation:.2%} (threshold: {threshold:.2%})"
                logger.warning(reason)
                return True, reason

            return False, None

        except Exception as e:
            logger.error(f"Error detecting degradation: {e}", exc_info=True)
            return False, None

    def _get_baseline_score(self, lookback_days: int = 90) -> float:
        """
        Calculate baseline composite score from historical data.

        Args:
            lookback_days: How far back to look

        Returns:
            Average composite score
        """
        try:
            # Get historical metrics (simplified - using recent calculation)
            # In production, this would aggregate stored composite scores
            metrics = self.metrics_collector.get_recent_metrics(
                window_days=30,
                lookback_hours=lookback_days * 24
            )

            if not metrics:
                return 0.0

            # Calculate score from historical metrics (simplified)
            returns = metrics.get('avg_return_pct', 0.0)
            sharpe = metrics.get('sharpe_ratio', 0.0)
            win_rate = metrics.get('win_rate', 0.0)
            drawdown = metrics.get('max_drawdown', 0.0)
            pf = metrics.get('profit_factor', 0.0)

            score = (
                self._normalize_returns(returns) * self.weights['returns'] +
                self._normalize_sharpe(sharpe) * self.weights['sharpe'] +
                win_rate * self.weights['win_rate'] +
                (1 - min(drawdown, 1.0)) * self.weights['drawdown'] +
                self._normalize_profit_factor(pf) * self.weights['profit_factor']
            )

            return score

        except Exception as e:
            logger.error(f"Error calculating baseline: {e}", exc_info=True)
            return 0.0

    def get_performance_summary(
        self,
        window_days: int = 30
    ) -> Dict:
        """
        Get comprehensive performance summary.

        Args:
            window_days: Window to analyze

        Returns:
            Dictionary with performance data
        """
        try:
            # Get composite score
            composite_score, components = self.calculate_composite_score(window_days)

            # Get raw metrics
            metrics = self.metrics_collector.get_recent_metrics(window_days=window_days)

            # Get signal accuracy
            signal_accuracy = self.metrics_collector.get_signal_accuracy_by_method(
                days_back=window_days
            )

            # Detect degradation
            is_degraded, degradation_reason = self.detect_performance_degradation(window_days)

            return {
                'composite_score': composite_score,
                'component_scores': components,
                'raw_metrics': metrics,
                'signal_accuracy': signal_accuracy,
                'performance_degraded': is_degraded,
                'degradation_reason': degradation_reason,
                'window_days': window_days,
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error generating performance summary: {e}", exc_info=True)
            return {}

    def compare_strategies(
        self,
        window_days: int = 30
    ) -> Dict[str, float]:
        """
        Compare performance of different conflict resolution strategies.

        Args:
            window_days: Window to analyze

        Returns:
            Dictionary with strategy scores
        """
        try:
            signal_accuracy = self.metrics_collector.get_signal_accuracy_by_method(
                days_back=window_days
            )

            # Create simplified scores for each strategy
            strategy_scores = {}
            for method, stats in signal_accuracy.items():
                # Weighted score based on accuracy and avg P&L
                score = (
                    stats['accuracy'] * 0.6 +
                    self._normalize_returns(stats['avg_pnl_pct']) * 0.4
                )
                strategy_scores[method] = score

            return strategy_scores

        except Exception as e:
            logger.error(f"Error comparing strategies: {e}", exc_info=True)
            return {}
