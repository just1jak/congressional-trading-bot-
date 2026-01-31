"""Direct scrapers for official government disclosure websites"""

import requests
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO
from datetime import datetime, date
from typing import List, Optional, Dict
import time

from src.data.database import CongressionalTrade
from src.data.collectors.ticker_resolver import get_ticker_resolver
from src.utils.logger import get_logger
from src.utils.helpers import parse_date, parse_amount_range, normalize_politician_name

logger = get_logger()


class HouseDisclosureScraper:
    """
    Scraper for House of Representatives Financial Disclosures.

    Downloads and parses annual XML files from disclosures.house.gov
    """

    BASE_URL = "https://disclosures.house.gov/public_disc/financial-pdfs"

    def __init__(self):
        """Initialize the House scraper"""
        self.ticker_resolver = get_ticker_resolver()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CongressionalTradingBot/1.0 (Educational Research)'
        })

    def get_available_years(self) -> List[int]:
        """
        Get list of years with available data.

        Returns:
            List of years (e.g., [2021, 2022, 2023])
        """
        # House disclosures typically go back to 2012
        # We'll check from 2012 to current year
        current_year = datetime.now().year
        available_years = []

        for year in range(2012, current_year + 1):
            # Quick check if the file exists
            url = f"{self.BASE_URL}/{year}FD.ZIP"
            try:
                response = self.session.head(url, timeout=5)
                if response.status_code == 200:
                    available_years.append(year)
            except:
                pass

        logger.info(f"Found {len(available_years)} years of House data: {available_years}")
        return available_years

    def scrape_year(self, year: int, progress_callback=None) -> List[CongressionalTrade]:
        """
        Scrape all House trades for a specific year.

        Args:
            year: Year to scrape (e.g., 2023)
            progress_callback: Optional callback function for progress updates

        Returns:
            List of CongressionalTrade objects
        """
        logger.info(f"Scraping House disclosures for {year}...")

        # Download the ZIP file
        zip_url = f"{self.BASE_URL}/{year}FD.ZIP"

        try:
            logger.info(f"Downloading {zip_url}...")
            response = self.session.get(zip_url, timeout=60)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to download {year} data: {e}")
            return []

        # Extract XML from ZIP
        try:
            zip_file = zipfile.ZipFile(BytesIO(response.content))
            xml_filename = f"{year}FD.xml"

            if xml_filename not in zip_file.namelist():
                logger.error(f"XML file {xml_filename} not found in ZIP")
                return []

            with zip_file.open(xml_filename) as xml_file:
                logger.info(f"Parsing XML file (this may take a minute)...")
                tree = ET.parse(xml_file)
                root = tree.getroot()

        except Exception as e:
            logger.error(f"Failed to extract/parse XML: {e}")
            return []

        # Parse the XML
        trades = self._parse_xml(root, year, progress_callback)

        logger.info(f"Successfully scraped {len(trades)} trades from {year}")
        return trades

    def _parse_xml(self, root: ET.Element, year: int, progress_callback=None) -> List[CongressionalTrade]:
        """
        Parse XML tree into CongressionalTrade objects.

        Args:
            root: XML root element
            year: Year being parsed
            progress_callback: Optional progress callback

        Returns:
            List of CongressionalTrade objects
        """
        trades = []
        members_processed = 0

        # Find all members
        members = root.findall('.//Member')
        total_members = len(members)

        logger.info(f"Processing {total_members} House members...")

        for member in members:
            try:
                # Get member info
                last_name = member.find('Last')
                first_name = member.find('First')

                if last_name is None or first_name is None:
                    continue

                politician_name = normalize_politician_name(
                    f"{first_name.text} {last_name.text}"
                )

                # Get party affiliation (if available)
                party_elem = member.find('Party')
                party = party_elem.text if party_elem is not None else None

                # Find all PTR (Periodic Transaction Report) filings
                for filing in member.findall('.//Filing'):
                    filing_type = filing.get('FilingType') or filing.find('FilingType')

                    # We want PTRs (type "P")
                    if filing_type is not None:
                        if isinstance(filing_type, str):
                            if filing_type != 'P':
                                continue
                        else:
                            if filing_type.text != 'P':
                                continue

                    # Get filing date
                    filing_date_elem = filing.find('FilingDate')
                    if filing_date_elem is None:
                        continue

                    try:
                        filing_date = parse_date(filing_date_elem.text)
                    except:
                        continue

                    # Parse all transactions in this filing
                    for transaction in filing.findall('.//Transaction'):
                        trade = self._parse_transaction(
                            transaction,
                            politician_name,
                            party,
                            filing_date,
                            year
                        )

                        if trade:
                            trades.append(trade)

                members_processed += 1

                if progress_callback and members_processed % 10 == 0:
                    progress_callback(members_processed, total_members)

            except Exception as e:
                logger.warning(f"Error processing member: {e}")
                continue

        return trades

    def _parse_transaction(
        self,
        transaction: ET.Element,
        politician_name: str,
        party: Optional[str],
        filing_date: date,
        year: int
    ) -> Optional[CongressionalTrade]:
        """
        Parse a single transaction from XML.

        Args:
            transaction: Transaction XML element
            politician_name: Name of politician
            party: Party affiliation
            filing_date: Date the disclosure was filed
            year: Year of the data

        Returns:
            CongressionalTrade object or None if invalid
        """
        try:
            # Get asset name/description
            asset_name_elem = transaction.find('AssetName')
            if asset_name_elem is None:
                return None
            asset_description = asset_name_elem.text

            # Try to get ticker from XML
            ticker_elem = transaction.find('Ticker')
            ticker = ticker_elem.text if ticker_elem is not None and ticker_elem.text else None

            # If no ticker in XML, try to resolve from asset name
            if not ticker or ticker.strip() == '':
                ticker = self.ticker_resolver.resolve(asset_description)

            # Skip if we can't determine ticker
            if not ticker:
                logger.debug(f"Could not resolve ticker for: {asset_description}")
                return None

            # Get transaction type
            trans_type_elem = transaction.find('TransactionType')
            if trans_type_elem is None:
                return None
            transaction_type = trans_type_elem.text

            # Normalize transaction type
            if transaction_type:
                if 'purchase' in transaction_type.lower() or 'buy' in transaction_type.lower():
                    transaction_type = 'Purchase'
                elif 'sale' in transaction_type.lower() or 'sell' in transaction_type.lower():
                    transaction_type = 'Sale'
                elif 'exchange' in transaction_type.lower():
                    transaction_type = 'Exchange'

            # Get transaction date
            trans_date_elem = transaction.find('TransactionDate')
            if trans_date_elem is None or not trans_date_elem.text:
                # Use filing date as fallback
                transaction_date = filing_date
            else:
                try:
                    transaction_date = parse_date(trans_date_elem.text)
                except:
                    transaction_date = filing_date

            # Get amount range
            amount_elem = transaction.find('Amount')
            amount_range = amount_elem.text if amount_elem is not None else None

            # Parse amount to get estimate
            estimated_amount = None
            if amount_range:
                try:
                    estimated_amount = parse_amount_range(amount_range)
                except:
                    pass

            # Create CongressionalTrade object
            trade = CongressionalTrade(
                politician_name=politician_name,
                party=party,
                ticker=ticker.upper(),
                transaction_type=transaction_type,
                amount_range=amount_range,
                estimated_amount=estimated_amount,
                transaction_date=transaction_date,
                disclosure_date=filing_date,
                asset_description=asset_description,
                source=f'house_xml_{year}'
            )

            return trade

        except Exception as e:
            logger.debug(f"Error parsing transaction: {e}")
            return None

    def scrape_multiple_years(
        self,
        start_year: int,
        end_year: Optional[int] = None,
        progress_callback=None
    ) -> List[CongressionalTrade]:
        """
        Scrape multiple years of House data.

        Args:
            start_year: First year to scrape
            end_year: Last year to scrape (defaults to current year)
            progress_callback: Optional progress callback

        Returns:
            List of all trades across years
        """
        if end_year is None:
            end_year = datetime.now().year

        all_trades = []

        for year in range(start_year, end_year + 1):
            logger.info(f"Scraping year {year}/{end_year}...")

            trades = self.scrape_year(year, progress_callback)
            all_trades.extend(trades)

            # Be nice to the server
            if year < end_year:
                time.sleep(2)

        logger.info(f"Total trades scraped: {len(all_trades)}")
        return all_trades


class SenateEFDSScraper:
    """
    Scraper for Senate Electronic Financial Disclosure System.

    Note: Senate uses PDFs which are much harder to parse.
    This is a placeholder for future implementation.
    """

    BASE_URL = "https://efdsearch.senate.gov"

    def __init__(self):
        """Initialize the Senate scraper"""
        logger.warning("Senate scraper not yet fully implemented (PDFs are complex)")

    def scrape_senator(self, last_name: str) -> List[CongressionalTrade]:
        """
        Scrape trades for a specific senator.

        Note: This is a placeholder. Senate PDFs require complex parsing.

        Args:
            last_name: Senator's last name

        Returns:
            List of trades (currently returns empty list)
        """
        logger.warning("Senate PDF scraping not yet implemented")
        logger.info("Consider using CSV export or API for Senate data")
        return []

    def scrape_recent(self, days: int = 30) -> List[CongressionalTrade]:
        """
        Scrape recent Senate filings.

        Note: This is a placeholder.

        Args:
            days: Number of days to look back

        Returns:
            List of trades (currently returns empty list)
        """
        logger.warning("Senate PDF scraping not yet implemented")
        return []


def scrape_house_data(
    start_year: int = 2021,
    end_year: Optional[int] = None,
    progress_callback=None
) -> List[CongressionalTrade]:
    """
    Convenience function to scrape House data.

    Args:
        start_year: First year to scrape
        end_year: Last year to scrape (defaults to current year)
        progress_callback: Optional progress callback

    Returns:
        List of CongressionalTrade objects
    """
    scraper = HouseDisclosureScraper()
    return scraper.scrape_multiple_years(start_year, end_year, progress_callback)
