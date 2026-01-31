"""Ticker symbol resolver - maps company names to ticker symbols"""

import re
from typing import Optional, Dict
from difflib import get_close_matches

from src.utils.logger import get_logger

logger = get_logger()


# Comprehensive mapping of company names to ticker symbols
# This is a curated list of common stocks traded by politicians
COMPANY_TO_TICKER: Dict[str, str] = {
    # Tech Giants
    "apple inc": "AAPL",
    "apple computer inc": "AAPL",
    "microsoft corporation": "MSFT",
    "microsoft corp": "MSFT",
    "alphabet inc": "GOOGL",
    "google": "GOOGL",
    "amazon.com inc": "AMZN",
    "amazon inc": "AMZN",
    "amazon": "AMZN",
    "meta platforms inc": "META",
    "facebook inc": "META",
    "facebook": "META",
    "nvidia corporation": "NVDA",
    "nvidia corp": "NVDA",
    "tesla inc": "TSLA",
    "tesla motors": "TSLA",
    "netflix inc": "NFLX",
    "netflix": "NFLX",

    # Other Tech
    "advanced micro devices": "AMD",
    "amd inc": "AMD",
    "intel corporation": "INTC",
    "intel corp": "INTC",
    "oracle corporation": "ORCL",
    "salesforce inc": "CRM",
    "adobe inc": "ADBE",
    "cisco systems": "CSCO",
    "qualcomm inc": "QCOM",
    "broadcom inc": "AVGO",
    "texas instruments": "TXN",
    "ibm": "IBM",
    "international business machines": "IBM",

    # Financial
    "jpmorgan chase & co": "JPM",
    "jpmorgan chase": "JPM",
    "bank of america corporation": "BAC",
    "bank of america corp": "BAC",
    "wells fargo & company": "WFC",
    "wells fargo": "WFC",
    "citigroup inc": "C",
    "goldman sachs group inc": "GS",
    "morgan stanley": "MS",
    "berkshire hathaway": "BRK.B",
    "american express": "AXP",
    "visa inc": "V",
    "mastercard inc": "MA",
    "paypal holdings": "PYPL",

    # Healthcare/Pharma
    "johnson & johnson": "JNJ",
    "pfizer inc": "PFE",
    "moderna inc": "MRNA",
    "abbvie inc": "ABBV",
    "merck & co": "MRK",
    "unitedhealth group": "UNH",
    "eli lilly and company": "LLY",
    "bristol-myers squibb": "BMY",
    "thermo fisher scientific": "TMO",
    "abbott laboratories": "ABT",

    # Consumer
    "procter & gamble": "PG",
    "coca-cola company": "KO",
    "pepsico inc": "PEP",
    "walmart inc": "WMT",
    "costco wholesale": "COST",
    "target corporation": "TGT",
    "home depot": "HD",
    "nike inc": "NKE",
    "starbucks corporation": "SBUX",
    "mcdonald's corporation": "MCD",

    # Media/Entertainment
    "walt disney company": "DIS",
    "disney": "DIS",
    "comcast corporation": "CMCSA",
    "verizon communications": "VZ",
    "at&t inc": "T",
    "t-mobile us inc": "TMUS",

    # Industrial/Energy
    "exxon mobil corporation": "XOM",
    "chevron corporation": "CVX",
    "boeing company": "BA",
    "lockheed martin": "LMT",
    "raytheon technologies": "RTX",
    "general electric": "GE",
    "caterpillar inc": "CAT",
    "3m company": "MMM",

    # Retail/E-commerce
    "alibaba group": "BABA",
    "ebay inc": "EBAY",
    "shopify inc": "SHOP",

    # Semiconductors
    "taiwan semiconductor": "TSM",
    "asml holding": "ASML",
    "applied materials": "AMAT",
    "lam research": "LRCX",
    "micron technology": "MU",

    # ETFs (common ones)
    "spdr s&p 500 etf": "SPY",
    "invesco qqq trust": "QQQ",
    "vanguard total stock market": "VTI",
    "ishares russell 2000": "IWM",
}


class TickerResolver:
    """Resolves company names to ticker symbols"""

    def __init__(self):
        """Initialize the resolver with company mappings"""
        self.mapping = COMPANY_TO_TICKER
        self.cache = {}  # Cache for resolved tickers

    def resolve(self, asset_name: str) -> Optional[str]:
        """
        Resolve a company/asset name to a ticker symbol.

        Args:
            asset_name: Company or asset name from disclosure

        Returns:
            Ticker symbol or None if not found
        """
        if not asset_name:
            return None

        # Check cache first
        if asset_name in self.cache:
            return self.cache[asset_name]

        # Normalize the name
        normalized = self._normalize_name(asset_name)

        # Try direct lookup
        ticker = self.mapping.get(normalized)

        if ticker:
            self.cache[asset_name] = ticker
            logger.debug(f"Resolved '{asset_name}' -> {ticker}")
            return ticker

        # Try fuzzy matching
        ticker = self._fuzzy_match(normalized)

        if ticker:
            self.cache[asset_name] = ticker
            logger.debug(f"Fuzzy matched '{asset_name}' -> {ticker}")
            return ticker

        # Try extracting ticker from parentheses (e.g., "Apple Inc (AAPL)")
        ticker = self._extract_ticker_from_parentheses(asset_name)

        if ticker:
            self.cache[asset_name] = ticker
            logger.debug(f"Extracted ticker from '{asset_name}' -> {ticker}")
            return ticker

        # Check if it's already a ticker symbol
        if self._looks_like_ticker(asset_name):
            ticker = asset_name.upper().strip()
            self.cache[asset_name] = ticker
            logger.debug(f"'{asset_name}' appears to be a ticker: {ticker}")
            return ticker

        # Not found
        logger.warning(f"Could not resolve ticker for: '{asset_name}'")
        return None

    def _normalize_name(self, name: str) -> str:
        """
        Normalize company name for matching.

        Args:
            name: Raw company name

        Returns:
            Normalized name
        """
        # Convert to lowercase
        normalized = name.lower().strip()

        # Remove common suffixes
        suffixes = [
            ' inc.', ' inc', ' corporation', ' corp.', ' corp',
            ' company', ' co.', ' co', ' ltd.', ' ltd',
            ' llc', ' l.l.c.', ' plc', ' holdings', ' group',
            ' class a', ' class b', ' class c',
            ' common stock', ' - common stock'
        ]

        for suffix in suffixes:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]

        # Remove extra whitespace
        normalized = ' '.join(normalized.split())

        # Remove periods
        normalized = normalized.replace('.', '')

        return normalized

    def _fuzzy_match(self, name: str, cutoff: float = 0.85) -> Optional[str]:
        """
        Try to find a close match using fuzzy string matching.

        Args:
            name: Normalized company name
            cutoff: Minimum similarity score (0-1)

        Returns:
            Ticker symbol or None
        """
        matches = get_close_matches(name, self.mapping.keys(), n=1, cutoff=cutoff)

        if matches:
            matched_name = matches[0]
            return self.mapping[matched_name]

        return None

    def _extract_ticker_from_parentheses(self, name: str) -> Optional[str]:
        """
        Extract ticker from parentheses in name like "Apple Inc (AAPL)".

        Args:
            name: Asset name possibly containing ticker in parentheses

        Returns:
            Ticker symbol or None
        """
        # Look for pattern: (TICKER) or [TICKER]
        pattern = r'[\(\[]([A-Z]{1,5})[\)\]]'
        match = re.search(pattern, name)

        if match:
            ticker = match.group(1)
            # Validate it looks like a ticker (1-5 uppercase letters)
            if re.match(r'^[A-Z]{1,5}$', ticker):
                return ticker

        return None

    def _looks_like_ticker(self, name: str) -> bool:
        """
        Check if the name looks like a ticker symbol.

        Args:
            name: Potential ticker

        Returns:
            True if it looks like a ticker
        """
        # Ticker symbols are typically 1-5 uppercase letters
        # May have a dash or dot (e.g., BRK.B)
        cleaned = name.strip().upper()

        # Remove common prefixes
        cleaned = cleaned.replace('TICKER:', '').replace('SYMBOL:', '').strip()

        # Check if it matches ticker pattern
        return bool(re.match(r'^[A-Z]{1,5}(\.[A-Z])?$', cleaned))

    def add_mapping(self, company_name: str, ticker: str):
        """
        Add a custom company-to-ticker mapping.

        Args:
            company_name: Company name
            ticker: Ticker symbol
        """
        normalized = self._normalize_name(company_name)
        self.mapping[normalized] = ticker.upper()
        logger.info(f"Added custom mapping: '{company_name}' -> {ticker}")

    def get_stats(self) -> dict:
        """
        Get resolver statistics.

        Returns:
            Dictionary with stats
        """
        return {
            'total_mappings': len(self.mapping),
            'cached_resolutions': len(self.cache),
        }


# Global resolver instance
_resolver_instance: Optional[TickerResolver] = None


def get_ticker_resolver() -> TickerResolver:
    """
    Get or create the global ticker resolver instance.

    Returns:
        TickerResolver instance
    """
    global _resolver_instance

    if _resolver_instance is None:
        _resolver_instance = TickerResolver()

    return _resolver_instance
