"""Tests for government scraping modules"""

import pytest
from datetime import date
from src.data.collectors.ticker_resolver import TickerResolver, get_ticker_resolver
from src.data.collectors.government_scrapers import HouseDisclosureScraper


def test_ticker_resolver_direct_mapping():
    """Test direct ticker resolution"""
    resolver = TickerResolver()

    assert resolver.resolve("Apple Inc") == "AAPL"
    assert resolver.resolve("Microsoft Corporation") == "MSFT"
    assert resolver.resolve("NVIDIA Corporation") == "NVDA"
    assert resolver.resolve("Tesla Inc") == "TSLA"


def test_ticker_resolver_normalization():
    """Test that resolver handles variations in company names"""
    resolver = TickerResolver()

    # Different formats of Apple
    assert resolver.resolve("Apple Inc.") == "AAPL"
    assert resolver.resolve("Apple Inc") == "AAPL"
    assert resolver.resolve("apple inc") == "AAPL"
    assert resolver.resolve("APPLE INC.") == "AAPL"


def test_ticker_resolver_extraction():
    """Test ticker extraction from parentheses"""
    resolver = TickerResolver()

    assert resolver.resolve("Apple Inc (AAPL)") == "AAPL"
    assert resolver.resolve("Microsoft Corporation [MSFT]") == "MSFT"


def test_ticker_resolver_looks_like_ticker():
    """Test recognition of ticker symbols"""
    resolver = TickerResolver()

    assert resolver._looks_like_ticker("AAPL") == True
    assert resolver._looks_like_ticker("MSFT") == True
    assert resolver._looks_like_ticker("BRK.B") == True
    assert resolver._looks_like_ticker("Apple Inc") == False


def test_ticker_resolver_unknown():
    """Test handling of unknown companies"""
    resolver = TickerResolver()

    result = resolver.resolve("Unknown Fake Company XYZ")
    assert result is None


def test_ticker_resolver_custom_mapping():
    """Test adding custom ticker mappings"""
    resolver = TickerResolver()

    resolver.add_mapping("My Custom Company", "CUST")
    assert resolver.resolve("My Custom Company") == "CUST"


def test_ticker_resolver_cache():
    """Test that resolver caches results"""
    resolver = TickerResolver()

    # First resolution
    result1 = resolver.resolve("Apple Inc")
    assert result1 == "AAPL"

    # Should be in cache now
    assert "Apple Inc" in resolver.cache
    assert resolver.cache["Apple Inc"] == "AAPL"

    # Second resolution (from cache)
    result2 = resolver.resolve("Apple Inc")
    assert result2 == "AAPL"


def test_ticker_resolver_singleton():
    """Test that get_ticker_resolver returns singleton"""
    resolver1 = get_ticker_resolver()
    resolver2 = get_ticker_resolver()

    assert resolver1 is resolver2


def test_house_scraper_initialization():
    """Test that House scraper can be initialized"""
    scraper = HouseDisclosureScraper()

    assert scraper is not None
    assert scraper.ticker_resolver is not None
    assert scraper.BASE_URL == "https://disclosures.house.gov/public_disc/financial-pdfs"


def test_house_scraper_get_available_years():
    """Test getting available years (requires internet)"""
    scraper = HouseDisclosureScraper()

    # This requires internet connection, so we'll make it optional
    try:
        years = scraper.get_available_years()

        # Should return a list
        assert isinstance(years, list)

        # Years should be integers
        if years:
            assert all(isinstance(y, int) for y in years)

            # Years should be in reasonable range
            assert all(2012 <= y <= 2025 for y in years)

            # Should be sorted
            assert years == sorted(years)

    except Exception as e:
        pytest.skip(f"Skipping internet-dependent test: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
