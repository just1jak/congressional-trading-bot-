"""Direct scrapers for official government disclosure websites"""

import requests
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict
import time
import re

from src.data.database import CongressionalTrade
from src.data.collectors.ticker_resolver import get_ticker_resolver
from src.utils.logger import get_logger
from src.utils.helpers import parse_date, parse_amount_range, normalize_politician_name

logger = get_logger()


class HouseDisclosureScraper:
    """
    Scraper for House of Representatives Financial Disclosures.

    Downloads and parses annual XML files from disclosures-clerk.house.gov
    """

    BASE_URL = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs"

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

    def scrape_year(self, year: int, progress_callback=None, max_filings: Optional[int] = None) -> List[CongressionalTrade]:
        """
        Scrape all House trades for a specific year.

        Args:
            year: Year to scrape (e.g., 2023)
            progress_callback: Optional callback function for progress updates
            max_filings: Maximum number of PTR filings to process (None = all)

        Returns:
            List of CongressionalTrade objects
        """
        logger.info(f"Scraping House disclosures for {year}...")

        # Step 1: Download and parse XML index to get PTR filing IDs
        ptr_filings = self._get_ptr_filings_from_index(year)

        if not ptr_filings:
            logger.warning(f"No PTR filings found for {year}")
            return []

        # Limit filings if requested
        if max_filings:
            ptr_filings = ptr_filings[:max_filings]

        logger.info(f"Found {len(ptr_filings)} PTR filings for {year}")

        # Step 2: Download and parse each PTR PDF
        all_trades = []
        for i, filing in enumerate(ptr_filings):
            try:
                if progress_callback and i % 10 == 0:
                    progress_callback(i, len(ptr_filings))

                logger.debug(f"Processing filing {i+1}/{len(ptr_filings)}: {filing['name']} (DocID: {filing['doc_id']})")

                # Download PDF
                pdf_content = self._download_ptr_pdf(year, filing['doc_id'])
                if not pdf_content:
                    continue

                # Parse PDF for transactions
                filing_date = parse_date(filing['filing_date'])
                trades = self._parse_ptr_pdf(
                    pdf_content,
                    filing['name'],
                    filing.get('party'),
                    filing_date,
                    year
                )

                all_trades.extend(trades)

                # Be nice to the server
                time.sleep(1)

            except Exception as e:
                logger.warning(f"Error processing filing {filing.get('doc_id')}: {e}")
                continue

        logger.info(f"Successfully scraped {len(all_trades)} trades from {year}")
        return all_trades

    def _get_ptr_filings_from_index(self, year: int) -> List[Dict[str, str]]:
        """
        Parse the XML index to get list of PTR filings.

        Args:
            year: Year to get filings for

        Returns:
            List of filing dictionaries with name, doc_id, filing_date, party
        """
        # Download the ZIP file
        zip_url = f"{self.BASE_URL}/{year}FD.ZIP"

        try:
            logger.info(f"Downloading index for {year}...")
            response = self.session.get(zip_url, timeout=60)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to download {year} index: {e}")
            return []

        # Extract XML from ZIP
        try:
            zip_file = zipfile.ZipFile(BytesIO(response.content))
            xml_filename = f"{year}FD.xml"

            if xml_filename not in zip_file.namelist():
                logger.error(f"XML file {xml_filename} not found in ZIP")
                return []

            with zip_file.open(xml_filename) as xml_file:
                tree = ET.parse(xml_file)
                root = tree.getroot()

        except Exception as e:
            logger.error(f"Failed to extract/parse XML index: {e}")
            return []

        # Extract PTR filings
        ptr_filings = []
        members = root.findall('.//Member')

        for member in members:
            try:
                # Get member info
                last_name = member.find('Last')
                first_name = member.find('First')
                filing_type_elem = member.find('FilingType')
                doc_id_elem = member.find('DocID')
                filing_date_elem = member.find('FilingDate')

                # Only process PTR filings (type 'P')
                if filing_type_elem is None or filing_type_elem.text != 'P':
                    continue

                if last_name is None or first_name is None or doc_id_elem is None:
                    continue

                politician_name = normalize_politician_name(
                    f"{first_name.text} {last_name.text}"
                )

                # Get party affiliation (may not be in index)
                party_elem = member.find('Party')
                party = party_elem.text if party_elem is not None else None

                filing_date = filing_date_elem.text if filing_date_elem is not None else None

                ptr_filings.append({
                    'name': politician_name,
                    'doc_id': doc_id_elem.text,
                    'filing_date': filing_date,
                    'party': party
                })

            except Exception as e:
                logger.debug(f"Error parsing member entry: {e}")
                continue

        return ptr_filings

    def _download_ptr_pdf(self, year: int, doc_id: str) -> Optional[bytes]:
        """
        Download a PTR PDF from the House disclosure system.

        Args:
            year: Year of the filing
            doc_id: Document ID from the XML index

        Returns:
            PDF content as bytes, or None if failed
        """
        pdf_url = f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"

        try:
            response = self.session.get(pdf_url, timeout=30)
            response.raise_for_status()
            return response.content

        except Exception as e:
            logger.debug(f"Failed to download PDF {doc_id}: {e}")
            return None

    def _parse_ptr_pdf(
        self,
        pdf_content: bytes,
        politician_name: str,
        party: Optional[str],
        filing_date: date,
        year: int
    ) -> List[CongressionalTrade]:
        """
        Parse transactions from a House PTR PDF.

        Args:
            pdf_content: PDF file content as bytes
            politician_name: Name of the House member
            party: Party affiliation
            filing_date: Date the disclosure was filed
            year: Year of the filing

        Returns:
            List of CongressionalTrade objects
        """
        trades = []

        try:
            import pdfplumber

            # Open PDF with pdfplumber
            with pdfplumber.open(BytesIO(pdf_content)) as pdf:
                logger.debug(f"Parsing PDF with {len(pdf.pages)} pages for {politician_name}")

                # Extract text and tables from each page
                for page in pdf.pages:
                    # Try to extract tables first (more structured)
                    tables = page.extract_tables()

                    if tables:
                        for table in tables:
                            page_trades = self._parse_house_table(
                                table,
                                politician_name,
                                party,
                                filing_date,
                                year
                            )
                            trades.extend(page_trades)
                    else:
                        # Fallback to text parsing
                        text = page.extract_text()
                        if text:
                            page_trades = self._parse_house_text(
                                text,
                                politician_name,
                                party,
                                filing_date,
                                year
                            )
                            trades.extend(page_trades)

                logger.debug(f"Extracted {len(trades)} trades from PDF for {politician_name}")

        except ImportError:
            logger.error("pdfplumber not installed. Run: pip install pdfplumber")
        except Exception as e:
            logger.warning(f"Error parsing PDF for {politician_name}: {e}")

        return trades

    def _parse_house_table(
        self,
        table: List[List[str]],
        politician_name: str,
        party: Optional[str],
        filing_date: date,
        year: int
    ) -> List[CongressionalTrade]:
        """
        Parse transactions from a PDF table.

        Args:
            table: Table data as list of rows
            politician_name: Name of House member
            party: Party affiliation
            filing_date: Filing date
            year: Year of filing

        Returns:
            List of trades
        """
        trades = []

        # House PTR tables typically have columns like:
        # Asset | Owner | Transaction | Date | Amount | etc.

        # Find header row
        header_row = None
        for i, row in enumerate(table):
            if row and any(
                keyword in str(cell).lower() if cell else ''
                for cell in row
                for keyword in ['asset', 'ticker', 'security', 'transaction', 'stock']
            ):
                header_row = i
                break

        if header_row is None:
            return trades

        # Parse data rows
        for row in table[header_row + 1:]:
            if not row or len(row) < 2:
                continue

            try:
                trade = self._parse_house_transaction_row(
                    row,
                    politician_name,
                    party,
                    filing_date,
                    year
                )
                if trade:
                    trades.append(trade)

            except Exception as e:
                logger.debug(f"Error parsing row: {e}")
                continue

        return trades

    def _parse_house_transaction_row(
        self,
        row: List[str],
        politician_name: str,
        party: Optional[str],
        filing_date: date,
        year: int
    ) -> Optional[CongressionalTrade]:
        """
        Parse a single transaction row from a table.

        House PTR PDFs typically have columns:
        [ID, Owner, Asset, Transaction Type, Date, Notification Date, Amount, Cap Gains]

        Args:
            row: Table row data
            politician_name: House member name
            party: Party affiliation
            filing_date: Filing date
            year: Year of filing

        Returns:
            CongressionalTrade or None
        """
        try:
            # Skip rows that don't have enough columns
            if len(row) < 4:
                return None

            # Extract fields based on position (after validating)
            # Typical format: [ID/blank, Owner, Asset, Type, Date, NotifDate, Amount, CapGains]
            asset_description = None
            ticker = None
            transaction_type = None
            amount_range = None
            transaction_date = filing_date
            owner = None

            # Try columns in order
            for i, cell in enumerate(row):
                if not cell or cell.strip() == '':
                    continue

                cell_str = str(cell).strip()

                # Column 1-2: Owner (SP, JT, etc.) - skip these as they're not tickers
                if i < 2 and cell_str in ['SP', 'JT', 'DC', 'C']:
                    owner = cell_str
                    continue

                # Look for asset description with ticker in parentheses
                # Format: "Company Name (TICKER) [ST]"
                ticker_match = re.search(r'\(([A-Z]{1,5})\)', cell_str)
                if ticker_match:
                    ticker = ticker_match.group(1)
                    asset_description = cell_str
                    continue

                # Transaction type: single letter P, S, or E
                if cell_str in ['P', 'S', 'E']:
                    if cell_str == 'P':
                        transaction_type = 'Purchase'
                    elif cell_str == 'S':
                        transaction_type = 'Sale'
                    elif cell_str == 'E':
                        transaction_type = 'Exchange'
                    continue

                # Amount range
                if '$' in cell_str and '-' in cell_str:
                    # Clean up amount (may span multiple lines)
                    amount_range = re.sub(r'\s+', ' ', cell_str)
                    continue

                # Transaction date (MM/DD/YYYY)
                date_match = re.match(r'(\d{1,2}/\d{1,2}/\d{4})', cell_str)
                if date_match:
                    try:
                        transaction_date = parse_date(date_match.group(1))
                    except:
                        pass
                    continue

            # Must have ticker and transaction type
            if not ticker or not transaction_type:
                return None

            # Parse amount
            estimated_amount = None
            if amount_range:
                try:
                    estimated_amount = parse_amount_range(amount_range)
                except:
                    pass

            # Create trade object
            trade = CongressionalTrade(
                politician_name=politician_name,
                party=party,
                ticker=ticker.upper(),
                transaction_type=transaction_type,
                amount_range=amount_range,
                estimated_amount=estimated_amount,
                transaction_date=transaction_date,
                disclosure_date=filing_date,
                asset_description=asset_description or ticker,
                source=f'house_ptr_pdf_{year}'
            )

            return trade

        except Exception as e:
            logger.debug(f"Error parsing transaction row: {e}")
            return None

    def _parse_house_text(
        self,
        text: str,
        politician_name: str,
        party: Optional[str],
        filing_date: date,
        year: int
    ) -> List[CongressionalTrade]:
        """
        Parse transactions from plain text (fallback method).

        Looks for pattern: Company Name (TICKER) [ST] followed by P/S and dates

        Args:
            text: Extracted PDF text
            politician_name: House member name
            party: Party affiliation
            filing_date: Filing date
            year: Year of filing

        Returns:
            List of trades
        """
        trades = []

        lines = text.split('\n')

        for line in lines:
            # Look for ticker in parentheses (House PTR format)
            ticker_match = re.search(r'\(([A-Z]{1,5})\)\s*\[ST\]', line)
            if not ticker_match:
                continue

            ticker = ticker_match.group(1)

            # Skip if ticker is actually an owner code
            if ticker in ['SP', 'JT', 'DC']:
                continue

            # Look for transaction type (P or S)
            transaction_type = None
            if re.search(r'\s+P\s+\d{2}/\d{2}/\d{4}', line):
                transaction_type = 'Purchase'
            elif re.search(r'\s+S\s+\d{2}/\d{2}/\d{4}', line):
                transaction_type = 'Sale'
            elif re.search(r'\s+E\s+\d{2}/\d{2}/\d{4}', line):
                transaction_type = 'Exchange'

            if not transaction_type:
                continue

            # Extract asset description (text before ticker)
            asset_match = re.search(r'([A-Za-z\s,\.&-]+)\s*\(' + ticker + r'\)', line)
            asset_description = asset_match.group(1).strip() if asset_match else ticker

            # Try to extract amount
            amount_match = re.search(r'\$[\d,]+ -\s*\$[\d,]+', line)
            amount_range = amount_match.group(0) if amount_match else None

            # Try to extract transaction date (first date after transaction type)
            date_match = re.search(r'\d{2}/\d{2}/\d{4}', line)
            transaction_date = filing_date
            if date_match:
                try:
                    transaction_date = parse_date(date_match.group(0))
                except:
                    pass

            # Create trade
            trade = CongressionalTrade(
                politician_name=politician_name,
                party=party,
                ticker=ticker.upper(),
                transaction_type=transaction_type,
                amount_range=amount_range,
                estimated_amount=parse_amount_range(amount_range) if amount_range else None,
                transaction_date=transaction_date,
                disclosure_date=filing_date,
                asset_description=asset_description,
                source=f'house_ptr_text_{year}'
            )

            trades.append(trade)

        return trades

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

    Scrapes PTR (Periodic Transaction Report) PDFs from efdsearch.senate.gov
    """

    BASE_URL = "https://efdsearch.senate.gov"
    SEARCH_URL = f"{BASE_URL}/search"

    def __init__(self):
        """Initialize the Senate scraper"""
        self.ticker_resolver = get_ticker_resolver()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CongressionalTradingBot/1.0 (Educational Research)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        })
        logger.info("Senate EFDS scraper initialized")

    def search_recent_filings(
        self,
        filing_type: str = 'PTR',
        days_back: int = 90,
        max_results: int = 100
    ) -> List[Dict[str, str]]:
        """
        Search for recent Senate disclosure filings.

        Args:
            filing_type: Type of filing ('PTR' for Periodic Transaction Reports)
            days_back: Number of days to look back
            max_results: Maximum number of filings to return

        Returns:
            List of filing metadata dictionaries
        """
        logger.info(f"Searching for Senate {filing_type} filings from last {days_back} days...")

        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            # Search parameters for EFDS
            params = {
                'report_type': filing_type,
                'filed_date_from': start_date.strftime('%m/%d/%Y'),
                'filed_date_to': end_date.strftime('%m/%d/%Y'),
            }

            # Make search request
            response = self.session.post(
                f"{self.BASE_URL}/search/report/data/",
                data=params,
                timeout=30
            )
            response.raise_for_status()

            # Parse JSON response
            data = response.json()

            filings = []
            for record in data.get('data', [])[:max_results]:
                filing = {
                    'senator_name': record.get('first_name', '') + ' ' + record.get('last_name', ''),
                    'filing_date': record.get('filed_date'),
                    'pdf_url': f"{self.BASE_URL}{record.get('pdf_url', '')}",
                    'filing_id': record.get('id'),
                    'report_type': record.get('report_type')
                }
                filings.append(filing)

            logger.info(f"Found {len(filings)} Senate filings")
            return filings

        except Exception as e:
            logger.error(f"Error searching Senate filings: {e}")
            return []

    def download_pdf(self, pdf_url: str) -> Optional[bytes]:
        """
        Download a PDF file from EFDS.

        Args:
            pdf_url: URL to the PDF file

        Returns:
            PDF content as bytes, or None if failed
        """
        try:
            logger.debug(f"Downloading PDF: {pdf_url}")
            response = self.session.get(pdf_url, timeout=60)
            response.raise_for_status()
            return response.content

        except Exception as e:
            logger.error(f"Failed to download PDF: {e}")
            return None

    def parse_pdf_transactions(
        self,
        pdf_content: bytes,
        senator_name: str,
        filing_date: date
    ) -> List[CongressionalTrade]:
        """
        Parse transactions from a Senate PTR PDF.

        Args:
            pdf_content: PDF file content as bytes
            senator_name: Name of the senator
            filing_date: Date the disclosure was filed

        Returns:
            List of CongressionalTrade objects
        """
        trades = []

        try:
            import pdfplumber
            from io import BytesIO

            # Open PDF with pdfplumber
            with pdfplumber.open(BytesIO(pdf_content)) as pdf:
                logger.info(f"Parsing PDF with {len(pdf.pages)} pages for {senator_name}")

                # Extract text and tables from each page
                for page_num, page in enumerate(pdf.pages):
                    # Try to extract tables first (more structured)
                    tables = page.extract_tables()

                    if tables:
                        for table in tables:
                            page_trades = self._parse_table_transactions(
                                table,
                                senator_name,
                                filing_date
                            )
                            trades.extend(page_trades)
                    else:
                        # Fallback to text parsing
                        text = page.extract_text()
                        if text:
                            page_trades = self._parse_text_transactions(
                                text,
                                senator_name,
                                filing_date
                            )
                            trades.extend(page_trades)

            logger.info(f"Extracted {len(trades)} trades from PDF")

        except ImportError:
            logger.error("pdfplumber not installed. Run: pip install pdfplumber")
        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")

        return trades

    def _parse_table_transactions(
        self,
        table: List[List[str]],
        senator_name: str,
        filing_date: date
    ) -> List[CongressionalTrade]:
        """
        Parse transactions from a PDF table.

        Args:
            table: Table data as list of rows
            senator_name: Name of senator
            filing_date: Filing date

        Returns:
            List of trades
        """
        trades = []

        # Senate PTR tables typically have columns like:
        # Asset Name | Type | Date | Amount | Transaction Type

        # Find header row
        header_row = None
        for i, row in enumerate(table):
            if row and any(
                keyword in str(cell).lower() if cell else ''
                for cell in row
                for keyword in ['asset', 'ticker', 'security', 'transaction']
            ):
                header_row = i
                break

        if header_row is None:
            return trades

        # Parse data rows
        for row in table[header_row + 1:]:
            if not row or len(row) < 3:
                continue

            try:
                trade = self._parse_transaction_row(
                    row,
                    senator_name,
                    filing_date
                )
                if trade:
                    trades.append(trade)

            except Exception as e:
                logger.debug(f"Error parsing row: {e}")
                continue

        return trades

    def _parse_transaction_row(
        self,
        row: List[str],
        senator_name: str,
        filing_date: date
    ) -> Optional[CongressionalTrade]:
        """
        Parse a single transaction row from a table.

        Args:
            row: Table row data
            senator_name: Senator name
            filing_date: Filing date

        Returns:
            CongressionalTrade or None
        """
        try:
            # Extract fields (Senate PDFs vary in format)
            asset_name = None
            ticker = None
            transaction_type = None
            amount_range = None
            transaction_date = filing_date

            # Try to identify columns
            for cell in row:
                if not cell:
                    continue

                cell_lower = str(cell).lower().strip()

                # Transaction type indicators
                if any(keyword in cell_lower for keyword in ['purchase', 'buy', 'bought']):
                    transaction_type = 'Purchase'
                elif any(keyword in cell_lower for keyword in ['sale', 'sell', 'sold']):
                    transaction_type = 'Sale'

                # Amount range patterns
                if '$' in str(cell) and '-' in str(cell):
                    amount_range = str(cell).strip()

                # Date patterns
                if re.match(r'\d{1,2}/\d{1,2}/\d{2,4}', str(cell)):
                    try:
                        transaction_date = parse_date(str(cell))
                    except:
                        pass

                # Potential ticker (2-5 uppercase letters)
                if re.match(r'^[A-Z]{2,5}$', str(cell).strip()):
                    ticker = str(cell).strip()

                # Asset name (longer text)
                if len(str(cell)) > 10 and not any(c in str(cell) for c in ['$', '/', 'purchase', 'sale']):
                    if not asset_name:
                        asset_name = str(cell).strip()

            # Must have at least transaction type and some asset identifier
            if not transaction_type:
                return None

            # Try to get ticker
            if not ticker and asset_name:
                ticker = self.ticker_resolver.resolve(asset_name)

            if not ticker:
                return None

            # Parse amount
            estimated_amount = None
            if amount_range:
                try:
                    estimated_amount = parse_amount_range(amount_range)
                except:
                    pass

            # Create trade object
            trade = CongressionalTrade(
                politician_name=normalize_politician_name(senator_name),
                party=None,  # Will try to determine from senator list
                ticker=ticker.upper(),
                transaction_type=transaction_type,
                amount_range=amount_range,
                estimated_amount=estimated_amount,
                transaction_date=transaction_date,
                disclosure_date=filing_date,
                asset_description=asset_name or ticker,
                source='senate_ptr_pdf'
            )

            return trade

        except Exception as e:
            logger.debug(f"Error parsing transaction row: {e}")
            return None

    def _parse_text_transactions(
        self,
        text: str,
        senator_name: str,
        filing_date: date
    ) -> List[CongressionalTrade]:
        """
        Parse transactions from plain text (fallback method).

        Args:
            text: Extracted PDF text
            senator_name: Senator name
            filing_date: Filing date

        Returns:
            List of trades
        """
        trades = []

        # Look for transaction patterns in text
        # This is a simplified parser for when tables aren't detected

        lines = text.split('\n')

        for line in lines:
            line_lower = line.lower()

            # Skip non-transaction lines
            if not any(keyword in line_lower for keyword in ['purchase', 'sale', 'buy', 'sell', 'stock']):
                continue

            # Try to extract ticker (2-5 uppercase letters)
            ticker_match = re.search(r'\b([A-Z]{2,5})\b', line)
            if not ticker_match:
                continue

            ticker = ticker_match.group(1)

            # Determine transaction type
            transaction_type = 'Purchase' if any(
                kw in line_lower for kw in ['purchase', 'buy', 'bought']
            ) else 'Sale'

            # Try to extract amount
            amount_match = re.search(r'\$[\d,]+ - \$[\d,]+', line)
            amount_range = amount_match.group(0) if amount_match else None

            # Try to extract date
            date_match = re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', line)
            transaction_date = filing_date
            if date_match:
                try:
                    transaction_date = parse_date(date_match.group(0))
                except:
                    pass

            # Create trade
            trade = CongressionalTrade(
                politician_name=normalize_politician_name(senator_name),
                party=None,
                ticker=ticker.upper(),
                transaction_type=transaction_type,
                amount_range=amount_range,
                estimated_amount=parse_amount_range(amount_range) if amount_range else None,
                transaction_date=transaction_date,
                disclosure_date=filing_date,
                asset_description=f"{ticker} - extracted from text",
                source='senate_ptr_text'
            )

            trades.append(trade)

        return trades

    def scrape_senator(self, last_name: str, days_back: int = 90) -> List[CongressionalTrade]:
        """
        Scrape trades for a specific senator.

        Args:
            last_name: Senator's last name
            days_back: Number of days to look back

        Returns:
            List of trades
        """
        logger.info(f"Scraping trades for Senator {last_name}...")

        all_trades = []

        # Search for filings
        filings = self.search_recent_filings(
            filing_type='PTR',
            days_back=days_back
        )

        # Filter by senator
        senator_filings = [
            f for f in filings
            if last_name.lower() in f['senator_name'].lower()
        ]

        logger.info(f"Found {len(senator_filings)} filings for {last_name}")

        # Download and parse each filing
        for filing in senator_filings:
            try:
                # Download PDF
                pdf_content = self.download_pdf(filing['pdf_url'])
                if not pdf_content:
                    continue

                # Parse transactions
                filing_date = parse_date(filing['filing_date'])
                trades = self.parse_pdf_transactions(
                    pdf_content,
                    filing['senator_name'],
                    filing_date
                )

                all_trades.extend(trades)

                # Be nice to the server
                time.sleep(2)

            except Exception as e:
                logger.error(f"Error processing filing: {e}")
                continue

        logger.info(f"Scraped {len(all_trades)} trades for {last_name}")
        return all_trades

    def scrape_recent(self, days: int = 30, max_filings: int = 50) -> List[CongressionalTrade]:
        """
        Scrape recent Senate filings.

        Args:
            days: Number of days to look back
            max_filings: Maximum number of filings to process

        Returns:
            List of trades
        """
        logger.info(f"Scraping recent Senate filings from last {days} days...")

        all_trades = []

        # Search for recent PTR filings
        filings = self.search_recent_filings(
            filing_type='PTR',
            days_back=days,
            max_results=max_filings
        )

        logger.info(f"Processing {len(filings)} Senate filings...")

        # Process each filing
        for i, filing in enumerate(filings):
            try:
                logger.info(f"Processing filing {i+1}/{len(filings)}: {filing['senator_name']}")

                # Download PDF
                pdf_content = self.download_pdf(filing['pdf_url'])
                if not pdf_content:
                    continue

                # Parse transactions
                filing_date = parse_date(filing['filing_date'])
                trades = self.parse_pdf_transactions(
                    pdf_content,
                    filing['senator_name'],
                    filing_date
                )

                all_trades.extend(trades)

                # Rate limiting - be respectful
                if i < len(filings) - 1:
                    time.sleep(3)

            except Exception as e:
                logger.error(f"Error processing filing for {filing.get('senator_name')}: {e}")
                continue

        logger.info(f"Total Senate trades scraped: {len(all_trades)}")
        return all_trades


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
