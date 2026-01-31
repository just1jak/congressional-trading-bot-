"""Helper utility functions"""

from datetime import datetime, date
from typing import Optional, Union
import yaml
from pathlib import Path


def load_config(config_path: str = "config/config.yaml") -> dict:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to config file

    Returns:
        Configuration dictionary
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_file, 'r') as f:
        return yaml.safe_load(f)


def load_credentials(creds_path: str = "config/credentials.yaml") -> dict:
    """
    Load credentials from YAML file.

    Args:
        creds_path: Path to credentials file

    Returns:
        Credentials dictionary
    """
    creds_file = Path(creds_path)
    if not creds_file.exists():
        raise FileNotFoundError(
            f"Credentials file not found: {creds_path}\n"
            f"Copy config/credentials.yaml.example to config/credentials.yaml and add your credentials"
        )

    with open(creds_file, 'r') as f:
        return yaml.safe_load(f)


def parse_date(date_str: Union[str, date, datetime]) -> date:
    """
    Parse various date formats into a date object.

    Args:
        date_str: Date string, date, or datetime object

    Returns:
        Date object
    """
    if isinstance(date_str, date):
        return date_str
    if isinstance(date_str, datetime):
        return date_str.date()

    # Try common date formats
    formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    raise ValueError(f"Unable to parse date: {date_str}")


def parse_amount_range(amount_range: str) -> float:
    """
    Parse congressional disclosure amount ranges into estimated dollar amounts.

    Congressional disclosures use ranges like:
    - $1,001 - $15,000
    - $15,001 - $50,000
    - $50,001 - $100,000
    - Over $1,000,000

    Args:
        amount_range: Amount range string

    Returns:
        Estimated amount (midpoint of range)
    """
    # Remove dollar signs and commas
    cleaned = amount_range.replace('$', '').replace(',', '').strip()

    # Handle "Over X" format
    if cleaned.lower().startswith('over'):
        # For "over X", estimate as 1.5 * X
        amount = float(cleaned.lower().replace('over', '').strip())
        return amount * 1.5

    # Handle range format "X - Y"
    if '-' in cleaned:
        parts = cleaned.split('-')
        if len(parts) == 2:
            try:
                low = float(parts[0].strip())
                high = float(parts[1].strip())
                # Return midpoint
                return (low + high) / 2
            except ValueError:
                pass

    # Try to parse as single number
    try:
        return float(cleaned)
    except ValueError:
        # Default to median congressional trade value (~$35,000)
        return 35000.0


def format_currency(amount: float) -> str:
    """
    Format amount as currency.

    Args:
        amount: Dollar amount

    Returns:
        Formatted string (e.g., "$1,234.56")
    """
    return f"${amount:,.2f}"


def format_percentage(value: float) -> str:
    """
    Format decimal as percentage.

    Args:
        value: Decimal value (e.g., 0.20 for 20%)

    Returns:
        Formatted string (e.g., "20.00%")
    """
    return f"{value * 100:.2f}%"


def normalize_ticker(ticker: str) -> str:
    """
    Normalize stock ticker symbol.

    Args:
        ticker: Raw ticker symbol

    Returns:
        Normalized ticker (uppercase, trimmed)
    """
    return ticker.strip().upper()


def normalize_politician_name(name: str) -> str:
    """
    Normalize politician name for consistent matching.

    Args:
        name: Raw politician name

    Returns:
        Normalized name
    """
    # Remove titles, extra spaces
    name = name.strip()

    # Remove common titles
    titles = ['Hon.', 'Rep.', 'Sen.', 'Mr.', 'Mrs.', 'Ms.', 'Dr.']
    for title in titles:
        name = name.replace(title, '')

    # Normalize spacing
    name = ' '.join(name.split())

    return name
