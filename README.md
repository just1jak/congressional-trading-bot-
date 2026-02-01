# Congressional Trading Bot

A Python-based trading application that tracks congressional stock trades and replicates them with automated risk management.

## Features

### Data Collection
- **House Scraping**: Download all House trades from official XML files (2012-present)
- **Senate Scraping**: Parse Senate PTR PDFs from EFDS (PDF parsing with AI)
- **Coverage**: All 535 members of Congress (435 House + 100 Senate)
- **Real-time Updates**: Scrape recent filings on-demand

### Trading & Analysis
- **Backtesting**: Test strategies against historical data
- **Paper Trading**: Simulate trading without real money
- **Automated Execution**: Execute trades with 20% profit threshold
- **Risk Management**: Position sizing, profit targets, and stop losses
- **Conflict Resolution**: Handle opposing trades from different politicians

### AI Optimization (NEW!)
- **Real-time Metrics**: Track signal accuracy and performance
- **Multi-objective Scoring**: Evaluate on returns, Sharpe, win rate, drawdown
- **Strategy Comparison**: See which conflict resolution method works best
- **Performance Monitoring**: Detect degradation and optimize parameters

## Project Status

**Phase 1**: Data Collection & Storage (In Progress)

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your API keys
```

## Quick Start

### Scrape Congressional Data

```bash
# Scrape House trades (fast, XML-based)
python3 -m src.cli.cli scrape house --start-year 2023

# Scrape Senate trades (PDF parsing)
python3 -m src.cli.cli scrape senate --days 90 --max-filings 50

# Scrape specific senator
python3 -m src.cli.cli scrape senator Warren --days 90

# Check what's available
python3 -m src.cli.cli scrape available-years
```

### View & Analyze

```bash
# View current recommendations
python3 -m src.cli.cli recommendations --days 30

# Analyze specific stock
python3 -m src.cli.cli analyze NVDA --days 30

# View politician stats
python3 -m src.cli.cli politician-stats "Nancy Pelosi"

# Check bot status
python3 -m src.cli.cli status
```

### AI Optimization

```bash
# View optimization metrics
python3 -m src.cli.cli optimize status --window 30

# Collect metrics
python3 -m src.cli.cli optimize collect-metrics --window 30

# View AI insights
python3 -m src.cli.cli optimize insights --days 30
```

## Configuration

Edit `config/config.yaml` to customize:
- Profit threshold (default: 20%)
- Stop loss percentage
- Position sizing rules
- Execution timing preferences
- Conflict resolution strategy

## Project Structure

```
congressional-trading-bot/
├── src/
│   ├── data/              # Data collection and storage
│   ├── strategy/          # Trading strategy logic
│   ├── backtesting/       # Backtesting framework
│   ├── trading/           # Order execution
│   └── cli/               # Command-line interface
├── tests/                 # Unit tests
├── data/                  # Database and cached data
├── logs/                  # Application logs
└── results/               # Backtest results
```

## Documentation

- **[SENATE_SCRAPING_GUIDE.md](SENATE_SCRAPING_GUIDE.md)** - Complete guide to Senate PDF scraping
- **[OPTIMIZATION_GUIDE.md](OPTIMIZATION_GUIDE.md)** - AI optimization system documentation
- **[QUICK_START_OPTIMIZATION.md](QUICK_START_OPTIMIZATION.md)** - Quick reference for optimization
- **[SCRAPING_GUIDE.md](SCRAPING_GUIDE.md)** - House scraping documentation

## Who Can You Track?

### House (435 members) - ✅ Fully Automated
- Nancy Pelosi (D-CA)
- Kevin McCarthy (R-CA)
- Alexandria Ocasio-Cortez (D-NY)
- Marjorie Taylor Greene (R-GA)
- All other House representatives

### Senate (100 members) - ✅ Fully Automated
- Elizabeth Warren (D-MA)
- Ted Cruz (R-TX)
- Bernie Sanders (I-VT)
- Tommy Tuberville (R-AL)
- All other Senators

## Data Sources

- **House:** disclosures.house.gov (XML files, 2012-present)
- **Senate:** efdsearch.senate.gov (PTR PDFs, 2012-present)
- **Both chambers:** Official government disclosure systems

## Disclaimer

This software is for educational purposes only. Trading stocks involves risk. Past performance of congressional trades does not guarantee future results. Use at your own risk.

All data comes from public disclosure filings required under the STOCK Act.

## License

MIT License
