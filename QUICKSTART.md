# Quick Start Guide

Get up and running with the Congressional Trading Bot in 5 minutes.

## Prerequisites

- Python 3.11 or higher
- pip (Python package installer)
- Virtual environment (recommended)

## Installation

### 1. Set Up Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate  # On Windows
```

### 2. Install Dependencies

```bash
# Install all required packages
pip install -r requirements.txt

# Install the package in development mode
pip install -e .
```

Or simply use the Makefile:

```bash
make install
```

## Getting Started

### Import Sample Data

To get started quickly, import the sample congressional trades:

```bash
python -m src.cli.cli collect trades --csv data/sample_trades.csv
```

Or using Make:

```bash
make import-sample
```

### View Available Commands

```bash
python -m src.cli.cli --help
```

### Check Status

```bash
python -m src.cli.cli status
```

### View Trade Recommendations

```bash
python -m src.cli.cli recommendations --days 30 --count 10
```

### Analyze a Specific Ticker

```bash
python -m src.cli.cli analyze NVDA --days 30
```

### View Politician Statistics

```bash
python -m src.cli.cli politician-stats "Nancy Pelosi"
```

## Common Commands

```bash
# Data Collection
python -m src.cli.cli collect trades --days 30
python -m src.cli.cli collect trades --csv path/to/trades.csv
python -m src.cli.cli collect prices --days 30

# Analysis
python -m src.cli.cli recommendations
python -m src.cli.cli analyze AAPL
python -m src.cli.cli politician-stats "Dan Crenshaw"

# Risk Management
python -m src.cli.cli risk-settings

# Positions
python -m src.cli.cli show-positions

# Status
python -m src.cli.cli status
```

## Configuration

### 1. Copy Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your API keys and credentials.

### 2. Configure Strategy Settings

Edit `config/config.yaml` to customize:

- Profit threshold (default: 20%)
- Stop loss percentage (default: 10%)
- Position sizing rules
- Conflict resolution strategy
- Execution timing

### 3. Set Up Broker Credentials (Optional)

For paper trading and live trading, you'll need broker API credentials:

```bash
cp config/credentials.yaml.example config/credentials.yaml
```

Edit `config/credentials.yaml` with your broker API credentials.

## Data Sources

The bot supports multiple data sources for congressional trades:

1. **CSV Import** (Recommended for getting started)
   - Use the sample data: `data/sample_trades.csv`
   - Or export data from websites like senatestockwatcher.com or capitoltrades.com

2. **Senate Stock Watcher API** (When available)
   - Requires API key

3. **Capitol Trades API** (When available)
   - Requires API key

4. **Direct Senate EFDS Scraping** (Advanced)
   - Requires custom implementation

## Next Steps

### Phase 1: Data Collection (Current)

1. **Collect Historical Data**
   ```bash
   python -m src.cli.cli collect trades --csv your_trades.csv
   ```

2. **Update Stock Prices**
   ```bash
   python -m src.cli.cli collect prices --days 90
   ```

3. **Analyze Trades**
   ```bash
   python -m src.cli.cli recommendations
   ```

### Phase 2: Backtesting (Coming Soon)

Test your strategy against historical data:

```bash
python -m src.cli.cli backtest --start 2020-01-01 --end 2023-12-31 --capital 100000
```

### Phase 3: Paper Trading (Coming Soon)

Simulate trading without real money:

```bash
python -m src.cli.cli start-paper-trading
```

### Phase 4: Live Trading (Coming Later)

Execute real trades (use with caution!):

```bash
python -m src.cli.cli start-live-trading
```

## Troubleshooting

### Database Issues

If you encounter database errors, try resetting:

```bash
rm data/congressional_trades.db
python -m src.cli.cli status  # This will recreate the database
```

### Import Errors

Make sure you're in the project root directory and have activated your virtual environment:

```bash
# Check current directory
pwd

# Activate virtual environment
source venv/bin/activate
```

### Missing Dependencies

Reinstall dependencies:

```bash
pip install -r requirements.txt --upgrade
```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=src --cov-report=html

# Or use Make
make test
```

## Getting Real Data

To get actual congressional trading data:

1. **Manual Export**
   - Visit [Senate Stock Watcher](https://senatestockwatcher.com) or [Capitol Trades](https://www.capitoltrades.com)
   - Export trades as CSV
   - Import using: `python -m src.cli.cli collect trades --csv yourfile.csv`

2. **API Access** (When available)
   - Sign up for API access at the data provider
   - Add API key to `.env` file
   - Enable in `config/config.yaml`

3. **Web Scraping** (Advanced)
   - Implement custom scrapers in `src/data/collectors/`
   - Handle rate limiting and CAPTCHA

## Support

For issues, questions, or contributions:

- Open an issue on GitHub
- Check the main README.md for detailed documentation
- Review the implementation plan in the project root

## License

MIT License - See LICENSE file for details
