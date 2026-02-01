# Quick Start: AI Optimization System

## Phase 1 is Complete! 🎉

The foundation of the AI-in-the-loop optimization system has been successfully implemented. Here's how to get started.

## Installation (5 minutes)

### 1. Install Dependencies

```bash
cd "/Users/justinkobely/Library/Mobile Documents/iCloud~md~obsidian/Documents/My_Notes/0 - Programs/congressional-trading-bot"

pip install -r requirements.txt
```

**New packages installed:**
- `xgboost` - ML confidence prediction (Phase 2)
- `scikit-learn` - ML utilities
- `tensorflow` - LSTM models (Phase 5)
- `optuna` - Bayesian optimization
- `anthropic` - Claude API (Phase 4)
- `schedule` - Background tasks

### 2. Initialize the System

```bash
python3 scripts/init_optimization.py
```

This will:
- ✓ Verify all dependencies installed
- ✓ Create 6 new database tables
- ✓ Validate configuration
- ✓ Run basic tests

### 3. Verify Installation

```bash
python3 -m src.cli.cli optimize status
```

Expected output: "No optimization data available yet" (this is normal!)

## What Was Built

### New Database Tables (6)

1. **optimization_metrics** - Performance metrics over time
2. **signal_accuracy** - Signal predictions vs actual results
3. **parameter_history** - Audit trail of all changes
4. **approval_requests** - Queue for major changes
5. **ml_model_versions** - ML model tracking
6. **optimization_insights** - AI-generated learnings

### New Python Modules (2)

1. **src/optimization/metrics_collector.py** (391 lines)
   - Real-time signal tracking
   - Trade outcome recording
   - Performance metric calculation

2. **src/optimization/performance_analyzer.py** (267 lines)
   - Multi-objective scoring
   - Performance degradation detection
   - Strategy comparison

### New CLI Commands (4)

```bash
# View performance metrics
python3 -m src.cli.cli optimize status --window 30

# Manually calculate metrics
python3 -m src.cli.cli optimize collect-metrics --window 30

# Review pending approvals (Phase 3+)
python3 -m src.cli.cli optimize review-pending

# View AI insights (Phase 4+)
python3 -m src.cli.cli optimize insights --days 30
```

## How It Works

```
1. Run Trading Bot
   ↓
2. Signals Generated → Automatically Tracked ✓
   ↓
3. Trades Executed
   ↓
4. Trades Close → Record Outcome (manual for now)
   ↓
5. Calculate Metrics → CLI command
   ↓
6. View Performance → CLI command
```

## Usage Example

### Step 1: Run the Bot

```bash
# Run your normal trading workflow
python3 -m src.cli.cli recommendations --days 30
```

**Behind the scenes:** Every signal is now automatically tracked in the `signal_accuracy` table.

### Step 2: Execute Trades

Follow your normal trading process. Signals are tracked automatically.

### Step 3: Record Outcomes (After Trades Close)

Add this to your trade execution code:

```python
from src.optimization.metrics_collector import MetricsCollector

# When a trade closes
collector = MetricsCollector()
collector.record_trade_outcome(
    ticker=trade.ticker,
    pnl_pct=trade.profit_loss_pct,
    executed_trade_id=trade.id
)
```

### Step 4: Calculate Metrics

```bash
python3 -m src.cli.cli optimize collect-metrics --window 30
```

### Step 5: View Results

```bash
python3 -m src.cli.cli optimize status --window 30
```

**You'll see:**
- Composite Score (0-1, higher is better)
- Component scores (returns, Sharpe, win rate, etc.)
- Signal accuracy by strategy
- Performance degradation warnings

## Multi-Objective Score Explained

Your bot is now evaluated on 5 objectives:

```
Composite Score =
    30% × Returns (higher is better)
  + 25% × Sharpe Ratio (risk-adjusted returns)
  + 20% × Win Rate (consistency)
  + 15% × (1 - Drawdown) (capital preservation)
  + 10% × Profit Factor (efficiency)
```

**Score Ranges:**
- **0.7 - 1.0**: Excellent (green)
- **0.5 - 0.7**: Good (yellow)
- **0.0 - 0.5**: Needs improvement (red)

## Configuration

Edit `config/optimization_config.yaml` to customize:

### Change Objective Weights

```yaml
objectives:
  returns_weight: 0.30        # Your priorities
  sharpe_ratio_weight: 0.25
  win_rate_weight: 0.20
  drawdown_weight: 0.15
  profit_factor_weight: 0.10
```

### Set Parameter Bounds

```yaml
parameter_bounds:
  profit_threshold:
    min: 0.15  # Safety limits
    max: 0.30
  stop_loss:
    min: -0.20
    max: -0.05
```

### Enable/Disable Features

```yaml
optimization:
  enabled: true                    # Master switch
  real_time_enabled: true          # Hourly checks (Phase 6)
  batch_enabled: true              # Daily backtests (Phase 2)
  auto_approve_minor_changes: true # Auto-adjust <5% (Phase 3)
```

## What's Tracked Automatically

✓ **Every Signal Generated**
- Ticker, signal type (BUY/SELL/HOLD)
- Confidence score
- Conflict resolution method used
- Timestamp

✓ **Performance Metrics** (when calculated)
- Win rate, average return
- Sharpe ratio, max drawdown
- Profit factor, total trades

✓ **Signal Accuracy** (per strategy)
- dollar_weighted accuracy
- unanimous_only accuracy
- senator_track_record accuracy

## Common Questions

### Q: Why is my composite score 0?

**A:** You need closed trades with outcomes. The system needs data to calculate performance.

### Q: How many trades do I need?

**A:** Minimum 5-10 for basic metrics, 20+ for statistical significance.

### Q: Can I change the objective weights?

**A:** Yes! Edit `config/optimization_config.yaml`. Just ensure weights sum to 1.0.

### Q: Is this running in the background?

**A:** Not yet. Phase 1 is manual. Background service comes in Phase 6.

### Q: Does this change my bot's behavior?

**A:** No! Phase 1 only tracks performance. Parameter adjustment comes in Phase 3.

## What's Next

### Phase 2: ML Foundation (Weeks 3-4)
- XGBoost ML model for signal confidence
- Automated backtesting engine
- Parameter sweep optimization

### Phase 3: Safe Parameter Adjustment (Weeks 5-6)
- Automatic parameter tuning
- Human approval for major changes
- Rollback on performance degradation

### Phase 4: LLM Integration (Week 7)
- Claude API for strategic insights
- Weekly performance reports
- Trade post-mortems

### Phase 5: Advanced ML (Weeks 8-9)
- LSTM exit timing optimizer
- Random Forest strategy selector
- Market regime detection

### Phase 6: Continuous Service (Week 10)
- Background optimization daemon
- Fully automated parameter tuning
- Production deployment

## Testing

Run the test suite:

```bash
pytest tests/test_optimization/ -v
```

Expected: All tests pass ✓

## Files Created

```
config/
  └── optimization_config.yaml          (NEW)

src/optimization/                       (NEW MODULE)
  ├── __init__.py
  ├── metrics_collector.py              (391 lines)
  ├── performance_analyzer.py           (267 lines)
  └── models/                           (for ML models)

tests/test_optimization/                (NEW TESTS)
  ├── test_metrics_collector.py
  └── test_performance_analyzer.py

scripts/
  └── init_optimization.py              (NEW)

Documentation:
  ├── OPTIMIZATION_GUIDE.md             (Full guide)
  ├── PHASE1_COMPLETE.md                (Implementation summary)
  └── QUICK_START_OPTIMIZATION.md       (This file)
```

## Troubleshooting

### Import Errors

```bash
ModuleNotFoundError: No module named 'xgboost'
```

**Fix:** Install dependencies
```bash
pip install -r requirements.txt
```

### Database Errors

```bash
Table 'optimization_metrics' doesn't exist
```

**Fix:** Run initialization
```bash
python3 scripts/init_optimization.py
```

### No Data Showing

```bash
"No optimization data available yet"
```

**Fix:** This is normal! You need to:
1. Execute trades
2. Close trades
3. Record outcomes
4. Calculate metrics

## Support

- **Full Guide:** `OPTIMIZATION_GUIDE.md`
- **Implementation Details:** `PHASE1_COMPLETE.md`
- **Code Docs:** Inline docstrings in source files
- **Tests:** `tests/test_optimization/`

## Ready to Start?

```bash
# 1. Install
pip install -r requirements.txt

# 2. Initialize
python3 scripts/init_optimization.py

# 3. Verify
python3 -m src.cli.cli optimize status

# 4. Start trading and let data accumulate!
```

---

**Phase 1 Status:** ✅ COMPLETE
**Ready to Use:** ✅ YES (after installation)
**Breaking Changes:** ❌ NONE

Enjoy your AI-powered trading bot! 🚀
