"""Tests for strategy modules"""

import pytest
from datetime import date
from src.strategy.risk_manager import RiskManager, RiskConfig
from src.data.database import ExecutedTrade, Position


def test_risk_manager_initialization():
    """Test risk manager initialization"""
    config = RiskConfig(
        profit_threshold=0.20,
        stop_loss=-0.10,
        max_position_size=0.05,
        max_positions=10
    )

    risk_mgr = RiskManager(config)
    assert risk_mgr.config.profit_threshold == 0.20


def test_should_exit_position_profit():
    """Test exit signal on profit threshold"""
    risk_mgr = RiskManager(RiskConfig(profit_threshold=0.20))

    position = Position(
        ticker="AAPL",
        quantity=100,
        average_entry_price=100.0,
        mode="paper"
    )

    # Should exit at 20% profit
    should_exit, reason = risk_mgr.should_exit_position(position, 120.0)
    assert should_exit is True
    assert "profit threshold" in reason.lower()


def test_should_exit_position_stop_loss():
    """Test exit signal on stop loss"""
    risk_mgr = RiskManager(RiskConfig(stop_loss=-0.10))

    position = Position(
        ticker="AAPL",
        quantity=100,
        average_entry_price=100.0,
        mode="paper"
    )

    # Should exit at 10% loss
    should_exit, reason = risk_mgr.should_exit_position(position, 89.0)
    assert should_exit is True
    assert "stop loss" in reason.lower()


def test_calculate_position_size():
    """Test position sizing calculation"""
    risk_mgr = RiskManager(RiskConfig(max_position_size=0.05))

    # With $100k account and $100 stock, max position is $5k = 50 shares
    shares = risk_mgr.calculate_position_size(100000, 100.0, current_positions_count=0)
    assert shares == 50


def test_calculate_position_size_max_positions():
    """Test position size with max positions reached"""
    risk_mgr = RiskManager(RiskConfig(max_positions=5))

    shares = risk_mgr.calculate_position_size(100000, 100.0, current_positions_count=5)
    assert shares == 0  # Should return 0 when max positions reached


def test_calculate_profit_loss():
    """Test P&L calculation"""
    risk_mgr = RiskManager()

    pl_dollars, pl_pct = risk_mgr.calculate_profit_loss(
        entry_price=100.0,
        exit_price=120.0,
        quantity=10
    )

    assert pl_dollars == 200.0  # (120 - 100) * 10
    assert pl_pct == 0.20  # 20%


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
