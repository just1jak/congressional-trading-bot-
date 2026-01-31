#!/usr/bin/env python3
"""Verification script to test Congressional Trading Bot setup"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")

    try:
        from src.data.database import init_database, CongressionalTrade
        print("  ✓ Database module")
    except ImportError as e:
        print(f"  ✗ Database module: {e}")
        return False

    try:
        from src.data.collectors.congressional_trades import CongressionalTradeCollector
        print("  ✓ Congressional trades collector")
    except ImportError as e:
        print(f"  ✗ Congressional trades collector: {e}")
        return False

    try:
        from src.data.collectors.stock_prices import StockPriceCollector
        print("  ✓ Stock prices collector")
    except ImportError as e:
        print(f"  ✗ Stock prices collector: {e}")
        return False

    try:
        from src.strategy.risk_manager import RiskManager
        print("  ✓ Risk manager")
    except ImportError as e:
        print(f"  ✗ Risk manager: {e}")
        return False

    try:
        from src.strategy.signal_generator import SignalGenerator
        print("  ✓ Signal generator")
    except ImportError as e:
        print(f"  ✗ Signal generator: {e}")
        return False

    try:
        from src.utils.logger import setup_logger
        from src.utils.helpers import load_config
        print("  ✓ Utilities")
    except ImportError as e:
        print(f"  ✗ Utilities: {e}")
        return False

    return True


def test_database():
    """Test database initialization"""
    print("\nTesting database...")

    try:
        from src.data.database import init_database

        # Initialize in-memory database for testing
        db = init_database("sqlite:///:memory:")
        print("  ✓ Database initialization")

        # Test session
        session = db.get_session()
        print("  ✓ Database session")

        return True

    except Exception as e:
        print(f"  ✗ Database: {e}")
        return False


def test_data_collection():
    """Test data collection modules"""
    print("\nTesting data collection...")

    try:
        from src.data.database import init_database, CongressionalTrade
        from src.data.collectors.congressional_trades import CongressionalTradeCollector
        from datetime import date

        # Initialize test database
        db = init_database("sqlite:///:memory:")
        collector = CongressionalTradeCollector(db=db.get_session())

        # Create test trade
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

        # Store trade
        stored = collector.store_trade(trade)

        if stored.id is not None:
            print("  ✓ Store congressional trade")
        else:
            print("  ✗ Failed to store trade")
            return False

        # Retrieve trade
        trades = collector.get_historical_trades(ticker="AAPL")
        if len(trades) == 1:
            print("  ✓ Retrieve congressional trade")
        else:
            print("  ✗ Failed to retrieve trade")
            return False

        return True

    except Exception as e:
        print(f"  ✗ Data collection: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_strategy():
    """Test strategy modules"""
    print("\nTesting strategy...")

    try:
        from src.strategy.risk_manager import RiskManager, RiskConfig
        from src.data.database import Position

        # Test risk manager
        config = RiskConfig(profit_threshold=0.20, stop_loss=-0.10)
        risk_mgr = RiskManager(config)

        # Test position sizing
        shares = risk_mgr.calculate_position_size(100000, 100.0, 0)
        if shares > 0:
            print("  ✓ Risk manager position sizing")
        else:
            print("  ✗ Risk manager position sizing failed")
            return False

        # Test exit logic
        position = Position(
            ticker="AAPL",
            quantity=100,
            average_entry_price=100.0,
            mode="paper"
        )

        should_exit, reason = risk_mgr.should_exit_position(position, 120.0)
        if should_exit:
            print("  ✓ Risk manager exit logic")
        else:
            print("  ✗ Risk manager exit logic failed")
            return False

        return True

    except Exception as e:
        print(f"  ✗ Strategy: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config():
    """Test configuration loading"""
    print("\nTesting configuration...")

    try:
        from src.utils.helpers import load_config

        config = load_config()

        if 'risk_management' in config:
            print("  ✓ Load configuration file")
        else:
            print("  ✗ Configuration incomplete")
            return False

        return True

    except Exception as e:
        print(f"  ✗ Configuration: {e}")
        return False


def main():
    """Run all verification tests"""
    print("=" * 60)
    print("Congressional Trading Bot - Setup Verification")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Database", test_database()))
    results.append(("Data Collection", test_data_collection()))
    results.append(("Strategy", test_strategy()))
    results.append(("Configuration", test_config()))

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{name:20s}: {status}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n✓ All tests passed! Your setup is ready.")
        print("\nNext steps:")
        print("  1. Import sample data: make import-sample")
        print("  2. View recommendations: make recommendations")
        print("  3. Check status: make status")
        return 0
    else:
        print("\n✗ Some tests failed. Please check the errors above.")
        print("\nTroubleshooting:")
        print("  1. Make sure you've installed dependencies: make install")
        print("  2. Check that config files exist in config/")
        print("  3. Verify you're in the project root directory")
        return 1


if __name__ == "__main__":
    sys.exit(main())
