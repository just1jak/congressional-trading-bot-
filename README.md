# Congressional Trading Bot

A Python-based trading application that tracks congressional stock trades and replicates them with automated risk management.

## Features

- **Data Collection**: Automatically collects congressional stock trade disclosures
- **Backtesting**: Test strategies against historical data
- **Paper Trading**: Simulate trading without real money
- **Automated Execution**: Execute trades with 20% profit threshold
- **Risk Management**: Position sizing, profit targets, and stop losses
- **Conflict Resolution**: Handle opposing trades from different politicians

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

```bash
# Collect recent congressional trades
python -m src.cli.cli collect-trades --days 30

# Run a backtest
python -m src.cli.cli backtest --start 2020-01-01 --end 2023-12-31 --capital 100000

# Start paper trading
python -m src.cli.cli start-paper-trading

# View current recommendations
python -m src.cli.cli show-recommendations
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

## Disclaimer

This software is for educational purposes only. Trading stocks involves risk. Past performance of congressional trades does not guarantee future results. Use at your own risk.

## License

MIT License
