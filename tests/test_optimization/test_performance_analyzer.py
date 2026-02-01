"""Tests for PerformanceAnalyzer"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.database import Base
from src.optimization.performance_analyzer import PerformanceAnalyzer


@pytest.fixture
def test_db():
    """Create in-memory test database"""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def analyzer(test_db):
    """Create PerformanceAnalyzer with test database"""
    return PerformanceAnalyzer(db=test_db)


def test_normalize_returns(analyzer):
    """Test return normalization"""
    # Test various return values
    assert analyzer._normalize_returns(0.0) == 0.5  # 0% return -> middle
    assert analyzer._normalize_returns(0.20) == 1.0  # 20% return -> max
    assert analyzer._normalize_returns(-0.20) == 0.0  # -20% return -> min
    assert analyzer._normalize_returns(0.10) == 0.75  # 10% return -> 0.75


def test_normalize_sharpe(analyzer):
    """Test Sharpe ratio normalization"""
    assert analyzer._normalize_sharpe(0.0) == 0.4  # Sharpe 0 -> 0.4
    assert analyzer._normalize_sharpe(3.0) == 1.0  # Sharpe 3 -> max
    assert analyzer._normalize_sharpe(-2.0) == 0.0  # Sharpe -2 -> min
    assert analyzer._normalize_sharpe(1.0) == 0.6  # Sharpe 1 -> 0.6


def test_normalize_profit_factor(analyzer):
    """Test profit factor normalization"""
    assert analyzer._normalize_profit_factor(0.0) == 0.0
    assert analyzer._normalize_profit_factor(3.0) == 1.0
    assert analyzer._normalize_profit_factor(1.5) == 0.5


def test_composite_score_weights_sum_to_one(analyzer):
    """Test that optimization weights sum to 1.0"""
    total_weight = sum(analyzer.weights.values())
    assert abs(total_weight - 1.0) < 0.01  # Allow small floating point error


def test_performance_summary_structure(analyzer, test_db):
    """Test that performance summary has expected structure"""
    summary = analyzer.get_performance_summary(window_days=30)

    # Should return dict even if empty
    assert isinstance(summary, dict)

    # If has data, check structure
    if summary:
        expected_keys = [
            'composite_score',
            'component_scores',
            'raw_metrics',
            'signal_accuracy',
            'performance_degraded',
            'window_days',
            'timestamp'
        ]
        for key in expected_keys:
            assert key in summary


def test_compare_strategies_empty(analyzer, test_db):
    """Test strategy comparison with no data"""
    strategies = analyzer.compare_strategies(window_days=30)
    assert isinstance(strategies, dict)
    # Empty dict when no signal data
    assert len(strategies) == 0


def test_detect_performance_degradation_no_baseline(analyzer, test_db):
    """Test degradation detection with no baseline"""
    is_degraded, reason = analyzer.detect_performance_degradation(
        window_days=30,
        threshold=-0.10
    )
    # Should not detect degradation with no baseline
    assert is_degraded is False
    assert reason is None
