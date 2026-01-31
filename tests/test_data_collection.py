"""Tests for data collection modules"""

import pytest
from datetime import date, datetime
from src.data.database import CongressionalTrade, get_database, init_database
from src.data.collectors.congressional_trades import CongressionalTradeCollector
from src.utils.helpers import parse_amount_range, normalize_ticker


def test_parse_amount_range():
    """Test amount range parsing"""
    assert parse_amount_range("$1,001 - $15,000") == 8000.5
    assert parse_amount_range("$15,001 - $50,000") == 32500.5
    assert parse_amount_range("Over $1,000,000") == 1500000.0


def test_normalize_ticker():
    """Test ticker normalization"""
    assert normalize_ticker("aapl") == "AAPL"
    assert normalize_ticker(" MSFT ") == "MSFT"
    assert normalize_ticker("googl") == "GOOGL"


def test_database_init():
    """Test database initialization"""
    db = init_database("sqlite:///:memory:")
    assert db is not None

    session = db.get_session()
    assert session is not None


def test_store_trade():
    """Test storing a congressional trade"""
    db = init_database("sqlite:///:memory:")
    collector = CongressionalTradeCollector(db=db.get_session())

    trade = CongressionalTrade(
        politician_name="Test Senator",
        party="D",
        ticker="AAPL",
        transaction_type="Purchase",
        amount_range="$15,001 - $50,000",
        estimated_amount=32500.5,
        transaction_date=date(2024, 1, 1),
        disclosure_date=date(2024, 2, 1),
        asset_description="Apple Inc",
        source="test"
    )

    stored = collector.store_trade(trade)
    assert stored.id is not None
    assert stored.ticker == "AAPL"


def test_deduplicate_trades():
    """Test trade deduplication"""
    db = init_database("sqlite:///:memory:")
    collector = CongressionalTradeCollector(db=db.get_session())

    trades = [
        CongressionalTrade(
            politician_name="Senator A",
            ticker="AAPL",
            transaction_type="Purchase",
            transaction_date=date(2024, 1, 1),
            disclosure_date=date(2024, 2, 1)
        ),
        CongressionalTrade(
            politician_name="Senator A",
            ticker="AAPL",
            transaction_type="Purchase",
            transaction_date=date(2024, 1, 1),
            disclosure_date=date(2024, 2, 1)
        ),
    ]

    unique = collector._deduplicate_trades(trades)
    assert len(unique) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
