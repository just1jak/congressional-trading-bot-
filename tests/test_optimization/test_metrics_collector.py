"""Tests for MetricsCollector"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.database import Base, ExecutedTrade, SignalAccuracy
from src.optimization.metrics_collector import MetricsCollector


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
def metrics_collector(test_db):
    """Create MetricsCollector with test database"""
    return MetricsCollector(db=test_db)


def test_record_signal(metrics_collector, test_db):
    """Test recording a trading signal"""
    metrics_collector.record_signal(
        ticker='AAPL',
        signal='BUY',
        confidence=0.85,
        conflict_resolution_method='dollar_weighted'
    )

    # Check signal was recorded
    signals = test_db.query(SignalAccuracy).all()
    assert len(signals) == 1
    assert signals[0].ticker == 'AAPL'
    assert signals[0].predicted_signal == 'BUY'
    assert signals[0].predicted_confidence == 0.85


def test_record_trade_outcome(metrics_collector, test_db):
    """Test recording trade outcome"""
    # First record a signal
    metrics_collector.record_signal(
        ticker='TSLA',
        signal='BUY',
        confidence=0.75,
        conflict_resolution_method='unanimous_only'
    )

    # Then record outcome
    metrics_collector.record_trade_outcome(
        ticker='TSLA',
        pnl_pct=0.12,
        executed_trade_id=1
    )

    # Check outcome was recorded
    signal = test_db.query(SignalAccuracy).filter_by(ticker='TSLA').first()
    assert signal.actual_outcome == 'profit'
    assert signal.actual_pnl_pct == 0.12


def test_calculate_metrics_with_trades(metrics_collector, test_db):
    """Test metrics calculation with sample trades"""
    # Create sample trades
    trades = [
        ExecutedTrade(
            ticker='AAPL',
            action='buy',
            quantity=10,
            entry_price=150.0,
            exit_price=165.0,
            entry_date=datetime.utcnow() - timedelta(days=5),
            exit_date=datetime.utcnow(),
            profit_loss=150.0,
            profit_loss_pct=0.10,
            status='closed',
            mode='paper'
        ),
        ExecutedTrade(
            ticker='TSLA',
            action='buy',
            quantity=5,
            entry_price=200.0,
            exit_price=190.0,
            entry_date=datetime.utcnow() - timedelta(days=3),
            exit_date=datetime.utcnow(),
            profit_loss=-50.0,
            profit_loss_pct=-0.05,
            status='closed',
            mode='paper'
        )
    ]

    for trade in trades:
        test_db.add(trade)
    test_db.commit()

    # Calculate metrics
    metrics = metrics_collector.calculate_and_store_metrics(window_days=30)

    # Verify metrics
    assert metrics['total_trades'] == 2.0
    assert metrics['win_rate'] == 0.5  # 1 win out of 2
    assert 'sharpe_ratio' in metrics
    assert 'max_drawdown' in metrics


def test_get_signal_accuracy_by_method(metrics_collector, test_db):
    """Test signal accuracy calculation by method"""
    # Create signals with outcomes
    signals = [
        SignalAccuracy(
            ticker='AAPL',
            predicted_signal='BUY',
            predicted_confidence=0.8,
            conflict_resolution_method='dollar_weighted',
            actual_outcome='profit',
            actual_pnl_pct=0.10
        ),
        SignalAccuracy(
            ticker='MSFT',
            predicted_signal='BUY',
            predicted_confidence=0.7,
            conflict_resolution_method='dollar_weighted',
            actual_outcome='loss',
            actual_pnl_pct=-0.05
        ),
        SignalAccuracy(
            ticker='GOOGL',
            predicted_signal='BUY',
            predicted_confidence=0.9,
            conflict_resolution_method='unanimous_only',
            actual_outcome='profit',
            actual_pnl_pct=0.15
        )
    ]

    for signal in signals:
        test_db.add(signal)
    test_db.commit()

    # Get accuracy by method
    accuracy = metrics_collector.get_signal_accuracy_by_method(days_back=30)

    # Verify results
    assert 'dollar_weighted' in accuracy
    assert 'unanimous_only' in accuracy
    assert accuracy['dollar_weighted']['accuracy'] == 0.5  # 1 correct out of 2
    assert accuracy['unanimous_only']['accuracy'] == 1.0  # 1 correct out of 1
    assert accuracy['dollar_weighted']['total_signals'] == 2


def test_metrics_calculation_with_no_trades(metrics_collector, test_db):
    """Test metrics calculation when no trades exist"""
    metrics = metrics_collector.calculate_and_store_metrics(window_days=30)
    assert metrics == {}


def test_get_metric_trend(metrics_collector, test_db):
    """Test getting metric trend over time"""
    from src.data.database import OptimizationMetric

    # Create sample metrics
    base_time = datetime.utcnow()
    for i in range(5):
        metric = OptimizationMetric(
            timestamp=base_time - timedelta(days=i),
            window_days=30,
            metric_type='win_rate',
            metric_value=0.6 + (i * 0.05)
        )
        test_db.add(metric)
    test_db.commit()

    # Get trend
    trend = metrics_collector.get_metric_trend(
        metric_type='win_rate',
        window_days=30,
        lookback_days=10
    )

    assert len(trend) == 5
    assert all(isinstance(t, tuple) and len(t) == 2 for t in trend)
