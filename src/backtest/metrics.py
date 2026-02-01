"""Performance metrics calculation for backtesting"""

import numpy as np
from typing import List, Dict, Optional
from datetime import datetime


def calculate_metrics(results: List[Dict]) -> Dict:
    """
    Calculate comprehensive performance metrics from backtest results.

    Args:
        results: List of trade results with entry/exit prices and dates

    Returns:
        Dictionary of performance metrics
    """
    if not results:
        return {
            'total_trades': 0,
            'total_return': 0.0,
            'avg_return': 0.0,
            'win_rate': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'best_trade': 0.0,
            'worst_trade': 0.0,
        }

    # Extract returns
    returns = [r['return_pct'] for r in results if r.get('return_pct') is not None]

    if not returns:
        return {
            'total_trades': len(results),
            'total_return': 0.0,
            'avg_return': 0.0,
            'win_rate': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'best_trade': 0.0,
            'worst_trade': 0.0,
        }

    # Basic metrics
    total_trades = len(returns)
    total_return = sum(returns)
    avg_return = np.mean(returns)

    # Win rate
    wins = [r for r in returns if r > 0]
    win_rate = len(wins) / total_trades if total_trades > 0 else 0.0

    # Sharpe ratio (annualized, assuming daily returns)
    # Risk-free rate assumed to be 0 for simplicity
    if len(returns) > 1:
        std_dev = np.std(returns, ddof=1)
        sharpe_ratio = (avg_return / std_dev * np.sqrt(252)) if std_dev > 0 else 0.0
    else:
        sharpe_ratio = 0.0

    # Maximum drawdown
    cumulative_returns = np.cumsum(returns)
    running_max = np.maximum.accumulate(cumulative_returns)
    drawdown = running_max - cumulative_returns
    max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0.0

    # Best and worst trades
    best_trade = max(returns) if returns else 0.0
    worst_trade = min(returns) if returns else 0.0

    # Profit factor (gross profits / gross losses)
    gross_profit = sum([r for r in returns if r > 0])
    gross_loss = abs(sum([r for r in returns if r < 0]))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    # Average win and average loss
    avg_win = np.mean(wins) if wins else 0.0
    losses = [r for r in returns if r < 0]
    avg_loss = np.mean(losses) if losses else 0.0

    return {
        'total_trades': total_trades,
        'total_return': total_return,
        'avg_return': avg_return,
        'win_rate': win_rate,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown,
        'best_trade': best_trade,
        'worst_trade': worst_trade,
        'profit_factor': profit_factor,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'total_wins': len(wins),
        'total_losses': len(losses),
    }


def calculate_holding_period_metrics(results: List[Dict], holding_periods: List[int]) -> Dict[int, Dict]:
    """
    Calculate metrics for different holding periods.

    Args:
        results: List of trade results
        holding_periods: List of holding periods in days (e.g., [30, 60, 90])

    Returns:
        Dictionary mapping holding period to metrics
    """
    metrics_by_period = {}

    for period in holding_periods:
        # Filter results for this holding period
        period_results = [r for r in results if r.get('holding_period') == period]
        metrics_by_period[period] = calculate_metrics(period_results)

    return metrics_by_period


def calculate_ticker_metrics(results: List[Dict]) -> Dict[str, Dict]:
    """
    Calculate metrics grouped by ticker.

    Args:
        results: List of trade results

    Returns:
        Dictionary mapping ticker to metrics
    """
    # Group by ticker
    by_ticker = {}
    for result in results:
        ticker = result.get('ticker')
        if ticker:
            if ticker not in by_ticker:
                by_ticker[ticker] = []
            by_ticker[ticker].append(result)

    # Calculate metrics for each ticker
    ticker_metrics = {}
    for ticker, ticker_results in by_ticker.items():
        ticker_metrics[ticker] = calculate_metrics(ticker_results)

    return ticker_metrics


def calculate_politician_metrics(results: List[Dict]) -> Dict[str, Dict]:
    """
    Calculate metrics grouped by politician.

    Args:
        results: List of trade results

    Returns:
        Dictionary mapping politician name to metrics
    """
    # Group by politician
    by_politician = {}
    for result in results:
        politician = result.get('politician_name')
        if politician:
            if politician not in by_politician:
                by_politician[politician] = []
            by_politician[politician].append(result)

    # Calculate metrics for each politician
    politician_metrics = {}
    for politician, pol_results in by_politician.items():
        politician_metrics[politician] = calculate_metrics(pol_results)

    return politician_metrics
