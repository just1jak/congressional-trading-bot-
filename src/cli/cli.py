"""Command-line interface for Congressional Trading Bot"""

import click
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from datetime import datetime, date, timedelta
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.database import init_database, get_database
from src.data.collectors.congressional_trades import CongressionalTradeCollector
from src.data.collectors.stock_prices import StockPriceCollector
from src.strategy.signal_generator import SignalGenerator, Signal
from src.strategy.risk_manager import RiskManager
from src.utils.logger import setup_logger, get_logger
from src.utils.helpers import format_currency, format_percentage

console = Console()


@click.group()
@click.option('--debug', is_flag=True, help='Enable debug logging')
def cli(debug):
    """Congressional Trading Bot - Track and replicate congressional stock trades"""
    # Setup logging
    setup_logger()

    if debug:
        logger = get_logger()
        logger.level("DEBUG")

    # Initialize database
    init_database()


# Data Collection Commands
@cli.group()
def collect():
    """Data collection commands"""
    pass


@collect.command('trades')
@click.option('--days', default=30, help='Number of days to look back')
@click.option('--csv', type=click.Path(exists=True), help='Import from CSV file')
def collect_trades(days, csv):
    """Collect congressional trades"""
    logger = get_logger()

    with console.status("[bold green]Collecting congressional trades..."):
        db = get_database()
        collector = CongressionalTradeCollector(db=db.get_session())

        if csv:
            # Import from CSV
            count = collector.import_from_csv(csv)
            console.print(f"[green]✓[/green] Imported {count} trades from CSV")
        else:
            # Fetch from APIs
            trades = collector.fetch_recent_trades(days_back=days)
            count = collector.store_trades(trades)
            console.print(f"[green]✓[/green] Collected and stored {count} new trades")


@collect.command('prices')
@click.option('--ticker', help='Update prices for specific ticker')
@click.option('--days', default=30, help='Number of days to fetch')
def collect_prices(ticker, days):
    """Update stock price data"""
    logger = get_logger()

    with console.status("[bold green]Updating stock prices..."):
        db = get_database()
        collector = StockPriceCollector(db=db.get_session())

        if ticker:
            # Update single ticker
            tickers = [ticker]
        else:
            # Get all tickers from recent trades
            trade_collector = CongressionalTradeCollector(db=db.get_session())
            start_date = date.today() - timedelta(days=days)
            trades = trade_collector.get_historical_trades(start_date=start_date)
            tickers = list(set(t.ticker for t in trades))

        count = collector.update_prices_for_tickers(tickers, days_back=days)
        console.print(f"[green]✓[/green] Updated {count} price records for {len(tickers)} tickers")


# Scraping Commands
@cli.group()
def scrape():
    """Scrape data from official government sources"""
    pass


@scrape.command('house')
@click.option('--start-year', type=int, required=True, help='First year to scrape (e.g., 2021)')
@click.option('--end-year', type=int, help='Last year to scrape (defaults to current year)')
def scrape_house(start_year, end_year):
    """
    Scrape House of Representatives trade data from official XML files.

    This downloads annual disclosure files from disclosures.house.gov
    and parses all Periodic Transaction Reports (PTRs).

    Example: python -m src.cli.cli scrape house --start-year 2021 --end-year 2023
    """
    logger = get_logger()

    from datetime import datetime
    if end_year is None:
        end_year = datetime.now().year

    console.print(f"\n[bold cyan]Scraping House Disclosures ({start_year}-{end_year})[/bold cyan]\n")
    console.print("This will download official XML files from disclosures.house.gov")
    console.print("and may take several minutes depending on the year range.\n")

    # Progress tracking
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console
    ) as progress:

        task = progress.add_task(
            f"[cyan]Scraping {start_year}-{end_year}...",
            total=100
        )

        db = get_database()
        collector = CongressionalTradeCollector(db=db.get_session())

        def update_progress(current, total):
            percent = (current / total) * 100
            progress.update(task, completed=percent)

        try:
            count = collector.scrape_house_data(
                start_year=start_year,
                end_year=end_year,
                progress_callback=update_progress
            )

            progress.update(task, completed=100)

            console.print(f"\n[green]✓[/green] Successfully scraped {count} House trades!")
            console.print(f"\n[dim]Run 'python -m src.cli.cli status' to see updated database stats[/dim]")

        except Exception as e:
            console.print(f"\n[red]✗[/red] Error scraping data: {e}")
            logger.error(f"Scraping failed: {e}", exc_info=True)


@scrape.command('available-years')
def scrape_available_years():
    """Check which years of House data are available"""
    logger = get_logger()

    with console.status("[bold green]Checking available years..."):
        db = get_database()
        collector = CongressionalTradeCollector(db=db.get_session())
        years = collector.get_house_available_years()

    if years:
        console.print(f"\n[bold cyan]Available House Disclosure Years:[/bold cyan]\n")

        from datetime import datetime
        current_year = datetime.now().year

        for year in years:
            marker = "[green]●[/green]" if year == current_year else "[dim]○[/dim]"
            note = " [dim](current year)[/dim]" if year == current_year else ""
            console.print(f"  {marker} {year}{note}")

        console.print(f"\n[dim]To scrape: python -m src.cli.cli scrape house --start-year {years[0]} --end-year {years[-1]}[/dim]")
    else:
        console.print("[yellow]No years found (check internet connection)[/yellow]")


@scrape.command('senate')
@click.option('--days', type=int, default=90, help='Number of days to look back')
@click.option('--max-filings', type=int, default=50, help='Maximum number of filings to process')
def scrape_senate(days, max_filings):
    """
    Scrape Senate PTR (Periodic Transaction Report) filings.

    This downloads PDF disclosure files from efdsearch.senate.gov
    and extracts stock transaction data.

    Example: python -m src.cli.cli scrape senate --days 30 --max-filings 25
    """
    logger = get_logger()

    console.print(f"\n[bold cyan]Scraping Senate PTR Filings ({days} days)[/bold cyan]\n")
    console.print("This will download and parse PDF files from efdsearch.senate.gov")
    console.print(f"Processing up to {max_filings} recent filings.\n")

    # Check if pdfplumber is installed
    try:
        import pdfplumber
    except ImportError:
        console.print("[red]Error: pdfplumber not installed[/red]")
        console.print("Install with: [bold]pip install pdfplumber[/bold]\n")
        return

    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console
    ) as progress:

        task = progress.add_task(
            f"[cyan]Scraping Senate filings...",
            total=100
        )

        db = get_database()
        collector = CongressionalTradeCollector(db=db.get_session())

        try:
            count = collector.scrape_senate_data(
                days_back=days,
                max_filings=max_filings
            )

            progress.update(task, completed=100)

            console.print(f"\n[green]✓[/green] Successfully scraped {count} Senate trades!")
            console.print(f"\n[dim]Run 'python -m src.cli.cli status' to see updated database stats[/dim]")

        except Exception as e:
            console.print(f"\n[red]✗[/red] Error scraping data: {e}")
            logger.error(f"Scraping failed: {e}", exc_info=True)


@scrape.command('senator')
@click.argument('last_name')
@click.option('--days', type=int, default=90, help='Number of days to look back')
def scrape_senator(last_name, days):
    """
    Scrape trades for a specific senator by last name.

    Example: python -m src.cli.cli scrape senator Warren --days 30
    """
    logger = get_logger()

    # Check if pdfplumber is installed
    try:
        import pdfplumber
    except ImportError:
        console.print("[red]Error: pdfplumber not installed[/red]")
        console.print("Install with: [bold]pip install pdfplumber[/bold]\n")
        return

    console.print(f"\n[bold cyan]Scraping trades for Senator {last_name}[/bold cyan]\n")

    with console.status(f"[bold green]Searching for {last_name} filings..."):
        db = get_database()
        collector = CongressionalTradeCollector(db=db.get_session())

        try:
            count = collector.scrape_senator_trades(
                senator_last_name=last_name,
                days_back=days
            )

            console.print(f"\n[green]✓[/green] Successfully scraped {count} trades for Senator {last_name}!")

            if count == 0:
                console.print(f"\n[yellow]No trades found. This could mean:[/yellow]")
                console.print(f"  • No PTR filings in the last {days} days")
                console.print(f"  • Senator name misspelled")
                console.print(f"  • No stock transactions to report")

        except Exception as e:
            console.print(f"\n[red]✗[/red] Error: {e}")
            logger.error(f"Scraping failed: {e}", exc_info=True)


# Analysis Commands
@cli.command()
@click.option('--days', default=30, help='Number of days to analyze')
@click.option('--count', default=10, help='Number of recommendations to show')
def recommendations(days, count):
    """Show top trade recommendations"""
    logger = get_logger()

    with console.status("[bold green]Analyzing congressional trades..."):
        db = get_database()
        signal_gen = SignalGenerator(db=db.get_session())

        signals = signal_gen.get_top_recommendations(count=count, lookback_days=days)

    if not signals:
        console.print("[yellow]No trade recommendations found[/yellow]")
        return

    # Display recommendations table
    table = Table(title=f"Top {len(signals)} Trade Recommendations")
    table.add_column("Ticker", style="cyan", no_wrap=True)
    table.add_column("Signal", style="bold")
    table.add_column("Confidence", style="magenta")
    table.add_column("Supporting Trades", justify="right")
    table.add_column("Reason")

    for sig in signals:
        signal_color = "green" if sig.signal == Signal.BUY else "red"
        table.add_row(
            sig.ticker,
            f"[{signal_color}]{sig.signal.value}[/{signal_color}]",
            f"{sig.confidence:.2%}",
            str(len(sig.supporting_trades)),
            sig.reason[:60] + "..." if len(sig.reason) > 60 else sig.reason
        )

    console.print(table)


@cli.command()
@click.argument('ticker')
@click.option('--days', default=30, help='Number of days to analyze')
def analyze(ticker, days):
    """Analyze congressional trades for a specific ticker"""
    logger = get_logger()

    db = get_database()
    signal_gen = SignalGenerator(db=db.get_session())
    trade_collector = CongressionalTradeCollector(db=db.get_session())

    # Get trades
    trades = trade_collector.get_trades_for_ticker(ticker, days_back=days)

    if not trades:
        console.print(f"[yellow]No congressional trades found for {ticker}[/yellow]")
        return

    # Display trades
    console.print(f"\n[bold cyan]{ticker} - Recent Congressional Trades[/bold cyan]\n")

    table = Table()
    table.add_column("Date", style="cyan")
    table.add_column("Politician", style="white")
    table.add_column("Party")
    table.add_column("Type", style="bold")
    table.add_column("Amount", justify="right")

    for trade in trades:
        trade_type_color = "green" if trade.transaction_type.lower() in ['purchase', 'buy'] else "red"
        party_color = "blue" if trade.party == 'D' else "red" if trade.party == 'R' else "white"

        table.add_row(
            str(trade.transaction_date),
            trade.politician_name,
            f"[{party_color}]{trade.party}[/{party_color}]",
            f"[{trade_type_color}]{trade.transaction_type}[/{trade_type_color}]",
            trade.amount_range
        )

    console.print(table)

    # Get signal
    signal = signal_gen.analyze_ticker(ticker, lookback_days=days)

    console.print(f"\n[bold]Signal:[/bold] ", end="")
    signal_color = "green" if signal.signal == Signal.BUY else "red" if signal.signal == Signal.SELL else "yellow"
    console.print(f"[{signal_color}]{signal.signal.value}[/{signal_color}]")
    console.print(f"[bold]Confidence:[/bold] {signal.confidence:.2%}")
    console.print(f"[bold]Reason:[/bold] {signal.reason}\n")


@cli.command('politician-stats')
@click.argument('politician_name')
def politician_stats(politician_name):
    """Show trading statistics for a politician"""
    logger = get_logger()

    db = get_database()
    trade_collector = CongressionalTradeCollector(db=db.get_session())

    trades = trade_collector.get_historical_trades(politician_name=politician_name)

    if not trades:
        console.print(f"[yellow]No trades found for {politician_name}[/yellow]")
        return

    # Calculate statistics
    total_trades = len(trades)
    buys = [t for t in trades if t.transaction_type.lower() in ['purchase', 'buy']]
    sells = [t for t in trades if t.transaction_type.lower() in ['sale', 'sell']]

    total_buy_value = sum(t.estimated_amount for t in buys if t.estimated_amount is not None)
    total_sell_value = sum(t.estimated_amount for t in sells if t.estimated_amount is not None)

    # Get unique tickers
    tickers = set(t.ticker for t in trades)

    # Display stats
    console.print(f"\n[bold cyan]{politician_name} - Trading Statistics[/bold cyan]\n")

    stats = Table(show_header=False, box=None)
    stats.add_column("Metric", style="bold")
    stats.add_column("Value")

    stats.add_row("Total Trades", str(total_trades))
    stats.add_row("Buy Trades", f"[green]{len(buys)}[/green]")
    stats.add_row("Sell Trades", f"[red]{len(sells)}[/red]")
    stats.add_row("Unique Tickers", str(len(tickers)))
    stats.add_row("Total Buy Value", f"[green]{format_currency(total_buy_value)}[/green]")
    stats.add_row("Total Sell Value", f"[red]{format_currency(total_sell_value)}[/red]")

    if trades:
        stats.add_row("Date Range", f"{min(t.transaction_date for t in trades)} to {max(t.transaction_date for t in trades)}")

    console.print(stats)


@cli.command()
@click.option('--start', required=True, help='Start date (YYYY-MM-DD)')
@click.option('--end', required=True, help='End date (YYYY-MM-DD)')
@click.option('--capital', default=100000, help='Initial capital')
@click.option('--politician', help='Filter by politician name')
def backtest(start, end, capital, politician):
    """Run backtest on historical data"""
    logger = get_logger()

    console.print("[yellow]Backtesting framework coming in Phase 2![/yellow]")
    console.print(f"Parameters: {start} to {end}, ${capital:,.0f} capital")

    # TODO: Implement backtesting in Phase 2


@cli.command()
def show_positions():
    """Show current open positions"""
    logger = get_logger()

    db = get_database()
    session = db.get_session()

    from src.data.database import Position
    positions = session.query(Position).all()

    if not positions:
        console.print("[yellow]No open positions[/yellow]")
        return

    table = Table(title="Current Positions")
    table.add_column("Ticker", style="cyan")
    table.add_column("Quantity", justify="right")
    table.add_column("Entry Price", justify="right")
    table.add_column("Current Price", justify="right")
    table.add_column("P&L", justify="right")
    table.add_column("P&L %", justify="right")
    table.add_column("Mode")

    for pos in positions:
        pl_color = "green" if pos.unrealized_pnl and pos.unrealized_pnl > 0 else "red"

        table.add_row(
            pos.ticker,
            str(pos.quantity),
            format_currency(pos.average_entry_price),
            format_currency(pos.current_price) if pos.current_price else "N/A",
            f"[{pl_color}]{format_currency(pos.unrealized_pnl) if pos.unrealized_pnl else 'N/A'}[/{pl_color}]",
            f"[{pl_color}]{format_percentage(pos.unrealized_pnl_pct) if pos.unrealized_pnl_pct else 'N/A'}[/{pl_color}]",
            pos.mode
        )

    console.print(table)


@cli.command('risk-settings')
def risk_settings():
    """Show current risk management settings"""
    risk_mgr = RiskManager()
    metrics = risk_mgr.get_risk_metrics()

    console.print("\n[bold cyan]Risk Management Settings[/bold cyan]\n")

    table = Table(show_header=False, box=None)
    table.add_column("Setting", style="bold")
    table.add_column("Value")

    for key, value in metrics.items():
        table.add_row(key.replace('_', ' ').title(), str(value))

    console.print(table)


@cli.command()
def status():
    """Show bot status and statistics"""
    logger = get_logger()

    db = get_database()
    session = db.get_session()

    from src.data.database import CongressionalTrade, ExecutedTrade, Position

    # Get counts
    total_congressional_trades = session.query(CongressionalTrade).count()
    total_executed_trades = session.query(ExecutedTrade).count()
    open_positions = session.query(Position).count()

    # Get date ranges
    latest_congressional_trade = session.query(CongressionalTrade).order_by(
        CongressionalTrade.disclosure_date.desc()
    ).first()

    console.print("\n[bold cyan]Congressional Trading Bot Status[/bold cyan]\n")

    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="bold")
    table.add_column("Value")

    table.add_row("Congressional Trades in DB", str(total_congressional_trades))
    table.add_row("Executed Trades", str(total_executed_trades))
    table.add_row("Open Positions", str(open_positions))

    if latest_congressional_trade:
        table.add_row("Latest Trade Disclosure", str(latest_congressional_trade.disclosure_date))

    console.print(table)


@cli.command()
def version():
    """Show version information"""
    from src import __version__
    console.print(f"Congressional Trading Bot v{__version__}")


# Optimization Commands
@cli.group()
def optimize():
    """AI optimization system commands"""
    pass


@optimize.command('status')
@click.option('--window', default=30, help='Time window in days')
def optimization_status(window):
    """Show AI optimization metrics and status"""
    logger = get_logger()

    try:
        from src.optimization.performance_analyzer import PerformanceAnalyzer
        from src.optimization.metrics_collector import MetricsCollector

        analyzer = PerformanceAnalyzer()
        collector = MetricsCollector()

        with console.status("[bold green]Analyzing performance..."):
            # Get performance summary
            summary = analyzer.get_performance_summary(window_days=window)

            if not summary:
                console.print("[yellow]No optimization data available yet[/yellow]")
                console.print("Run the bot and execute some trades to start collecting metrics.")
                return

        # Display composite score
        console.print(f"\n[bold cyan]AI Optimization Status ({window}d window)[/bold cyan]\n")

        score_table = Table(show_header=False, box=None)
        score_table.add_column("Metric", style="bold")
        score_table.add_column("Value")

        composite_score = summary.get('composite_score', 0)
        score_color = "green" if composite_score > 0.7 else "yellow" if composite_score > 0.5 else "red"
        score_table.add_row("Composite Score", f"[{score_color}]{composite_score:.4f}[/{score_color}]")

        # Component scores
        components = summary.get('component_scores', {})
        for component, value in components.items():
            score_table.add_row(f"  {component.replace('_', ' ').title()}", f"{value:.4f}")

        console.print(score_table)

        # Raw metrics
        console.print("\n[bold]Performance Metrics:[/bold]\n")
        metrics_table = Table(show_header=False, box=None)
        metrics_table.add_column("Metric", style="bold")
        metrics_table.add_column("Value")

        raw_metrics = summary.get('raw_metrics', {})
        metrics_table.add_row("Win Rate", f"{raw_metrics.get('win_rate', 0):.2%}")
        metrics_table.add_row("Avg Return", f"{raw_metrics.get('avg_return_pct', 0):.2%}")
        metrics_table.add_row("Sharpe Ratio", f"{raw_metrics.get('sharpe_ratio', 0):.2f}")
        metrics_table.add_row("Max Drawdown", f"{raw_metrics.get('max_drawdown', 0):.2%}")
        metrics_table.add_row("Profit Factor", f"{raw_metrics.get('profit_factor', 0):.2f}")
        metrics_table.add_row("Total Trades", f"{int(raw_metrics.get('total_trades', 0))}")

        console.print(metrics_table)

        # Signal accuracy by method
        signal_accuracy = summary.get('signal_accuracy', {})
        if signal_accuracy:
            console.print("\n[bold]Signal Accuracy by Strategy:[/bold]\n")
            acc_table = Table()
            acc_table.add_column("Strategy", style="cyan")
            acc_table.add_column("Accuracy", justify="right")
            acc_table.add_column("Signals", justify="right")
            acc_table.add_column("Avg P&L", justify="right")

            for method, stats in signal_accuracy.items():
                acc_color = "green" if stats['accuracy'] > 0.6 else "yellow" if stats['accuracy'] > 0.5 else "red"
                acc_table.add_row(
                    method,
                    f"[{acc_color}]{stats['accuracy']:.2%}[/{acc_color}]",
                    str(stats['total_signals']),
                    f"{stats['avg_pnl_pct']:.2%}"
                )

            console.print(acc_table)

        # Performance degradation warning
        if summary.get('performance_degraded'):
            console.print(f"\n[bold red]⚠️  Warning:[/bold red] {summary.get('degradation_reason')}")

    except ImportError:
        console.print("[red]Optimization module not fully installed. Run: pip install -r requirements.txt[/red]")
    except Exception as e:
        logger.error(f"Error displaying optimization status: {e}", exc_info=True)
        console.print(f"[red]Error: {e}[/red]")


@optimize.command('review-pending')
def review_pending():
    """Review parameter changes awaiting approval"""
    logger = get_logger()

    try:
        from src.data.database import ApprovalRequest

        db = get_database()
        session = db.get_session()

        pending = (
            session.query(ApprovalRequest)
            .filter(ApprovalRequest.status == 'pending')
            .order_by(ApprovalRequest.timestamp.desc())
            .all()
        )

        if not pending:
            console.print("[green]No pending approval requests[/green]")
            return

        console.print(f"\n[bold cyan]Pending Approval Requests ({len(pending)})[/bold cyan]\n")

        for req in pending:
            table = Table(title=f"Request #{req.id} - {req.change_type}", box=None)
            table.add_column("Field", style="bold")
            table.add_column("Value")

            table.add_row("Timestamp", str(req.timestamp))
            table.add_row("Urgency", req.urgency)
            table.add_row("Reason", req.reason or "N/A")

            if req.llm_analysis:
                table.add_row("AI Analysis", req.llm_analysis[:200] + "..." if len(req.llm_analysis) > 200 else req.llm_analysis)

            console.print(table)
            console.print()

        console.print("[dim]Use 'optimize approve <id>' or 'optimize reject <id>' to process requests[/dim]")
        console.print("[dim](Approval/rejection commands coming in Phase 3)[/dim]\n")

    except Exception as e:
        logger.error(f"Error reviewing pending requests: {e}", exc_info=True)
        console.print(f"[red]Error: {e}[/red]")


@optimize.command('insights')
@click.option('--days', default=30, help='Days to look back')
@click.option('--limit', default=10, help='Number of insights to show')
def show_insights(days, limit):
    """Show AI-generated insights"""
    logger = get_logger()

    try:
        from src.data.database import OptimizationInsight
        from datetime import timedelta

        db = get_database()
        session = db.get_session()

        cutoff = datetime.now() - timedelta(days=days)

        insights = (
            session.query(OptimizationInsight)
            .filter(OptimizationInsight.timestamp >= cutoff)
            .order_by(OptimizationInsight.timestamp.desc())
            .limit(limit)
            .all()
        )

        if not insights:
            console.print(f"[yellow]No insights found in the last {days} days[/yellow]")
            console.print("[dim]Insights will be generated after LLM integration (Phase 4)[/dim]")
            return

        console.print(f"\n[bold cyan]AI Insights (last {days} days)[/bold cyan]\n")

        for insight in insights:
            console.print(f"[bold]{insight.insight_type}[/bold] - {insight.timestamp.strftime('%Y-%m-%d %H:%M')}")
            console.print(f"Source: {insight.source}")
            if insight.market_regime:
                console.print(f"Market Regime: {insight.market_regime}")
            console.print(f"\n{insight.insight_text}\n")
            console.print("─" * 80 + "\n")

    except Exception as e:
        logger.error(f"Error showing insights: {e}", exc_info=True)
        console.print(f"[red]Error: {e}[/red]")


@optimize.command('collect-metrics')
@click.option('--window', default=30, help='Time window in days')
def collect_metrics(window):
    """Manually trigger metrics collection and calculation"""
    logger = get_logger()

    try:
        from src.optimization.metrics_collector import MetricsCollector

        collector = MetricsCollector()

        with console.status(f"[bold green]Calculating metrics for {window}d window..."):
            metrics = collector.calculate_and_store_metrics(window_days=window)

        if metrics:
            console.print(f"\n[green]✓[/green] Metrics calculated and stored\n")

            table = Table()
            table.add_column("Metric", style="bold cyan")
            table.add_column("Value", justify="right")

            for metric_name, value in metrics.items():
                if 'pct' in metric_name or 'rate' in metric_name:
                    table.add_row(metric_name, f"{value:.2%}")
                else:
                    table.add_row(metric_name, f"{value:.4f}")

            console.print(table)
        else:
            console.print("[yellow]No trades available to calculate metrics[/yellow]")

    except Exception as e:
        logger.error(f"Error collecting metrics: {e}", exc_info=True)
        console.print(f"[red]Error: {e}[/red]")


# Backtest Commands
@cli.group()
def backtest():
    """Backtesting commands for trading strategies"""
    pass


@backtest.command('run')
@click.option('--strategy', type=click.Choice(['follow-all', 'top-performers', 'large-trades']),
              default='follow-all', help='Strategy to backtest')
@click.option('--start-date', type=click.DateTime(formats=["%Y-%m-%d"]),
              help='Start date for backtest (YYYY-MM-DD)')
@click.option('--end-date', type=click.DateTime(formats=["%Y-%m-%d"]),
              help='End date for backtest (YYYY-MM-DD)')
@click.option('--max-trades', type=int, help='Maximum number of trades to test (for quick testing)')
@click.option('--min-value', type=float, help='Minimum trade value for follow-all strategy')
def run_backtest(strategy, start_date, end_date, max_trades, min_value):
    """Run a backtest for a trading strategy"""
    logger = get_logger()

    from src.backtest.engine import BacktestEngine
    from src.backtest.strategies import FollowAllStrategy, TopPerformersStrategy, LargeTradesStrategy
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

    console.print(f"\n[bold cyan]Running Backtest: {strategy.title()}[/bold cyan]\n")

    # Initialize strategy
    if strategy == 'follow-all':
        strat = FollowAllStrategy(min_trade_value=min_value)
    elif strategy == 'top-performers':
        strat = TopPerformersStrategy(top_n_politicians=10)
    else:  # large-trades
        strat = LargeTradesStrategy(min_trade_value=min_value or 50000)

    console.print(f"Strategy: {strat.description}\n")

    # Initialize engine
    engine = BacktestEngine()

    # Progress tracking
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console
    ) as progress:

        task = progress.add_task(
            "[cyan]Running backtest...",
            total=100
        )

        def update_progress(current, total):
            pct = (current / total * 100) if total > 0 else 0
            progress.update(task, completed=pct)

        try:
            # Run backtest
            results = engine.run_backtest(
                strategy=strat,
                start_date=start_date,
                end_date=end_date,
                max_trades=max_trades,
                progress_callback=update_progress
            )

            progress.update(task, completed=100)

            # Display results
            console.print(f"\n[bold green]✓ Backtest Complete[/bold green]\n")

            # Overall metrics table
            metrics = results['overall_metrics']

            table = Table(title="Overall Performance Metrics")
            table.add_column("Metric", style="bold cyan")
            table.add_column("Value", justify="right", style="white")

            table.add_row("Total Trades", str(metrics['total_trades']))
            table.add_row("Winning Trades", str(metrics['total_wins']))
            table.add_row("Losing Trades", str(metrics['total_losses']))
            table.add_row("Win Rate", f"{metrics['win_rate']:.1%}")
            table.add_row("─" * 20, "─" * 20)
            table.add_row("Avg Return", f"{metrics['avg_return']:.2f}%",
                         style="green" if metrics['avg_return'] > 0 else "red")
            table.add_row("Total Return", f"{metrics['total_return']:.2f}%",
                         style="green" if metrics['total_return'] > 0 else "red")
            table.add_row("Best Trade", f"{metrics['best_trade']:.2f}%", style="green")
            table.add_row("Worst Trade", f"{metrics['worst_trade']:.2f}%", style="red")
            table.add_row("─" * 20, "─" * 20)
            table.add_row("Sharpe Ratio", f"{metrics['sharpe_ratio']:.2f}")
            table.add_row("Max Drawdown", f"{metrics['max_drawdown']:.2f}%", style="red")
            table.add_row("Profit Factor", f"{metrics['profit_factor']:.2f}")

            console.print(table)

            # Holding period comparison
            console.print("\n[bold cyan]Performance by Holding Period[/bold cyan]\n")

            period_table = Table()
            period_table.add_column("Holding Period", style="bold")
            period_table.add_column("Trades", justify="right")
            period_table.add_column("Avg Return", justify="right")
            period_table.add_column("Win Rate", justify="right")
            period_table.add_column("Sharpe Ratio", justify="right")

            for period, period_metrics in results['metrics_by_holding_period'].items():
                avg_ret = period_metrics['avg_return']
                period_table.add_row(
                    f"{period} days",
                    str(period_metrics['total_trades']),
                    f"{avg_ret:.2f}%",
                    f"{period_metrics['win_rate']:.1%}",
                    f"{period_metrics['sharpe_ratio']:.2f}",
                    style="green" if avg_ret > 0 else "red"
                )

            console.print(period_table)

            # Sample trades
            if results['raw_results']:
                console.print("\n[bold cyan]Sample Trades (First 10)[/bold cyan]\n")

                sample_table = Table()
                sample_table.add_column("Ticker", style="bold")
                sample_table.add_column("Entry Date")
                sample_table.add_column("Exit Date")
                sample_table.add_column("Return", justify="right")
                sample_table.add_column("Hold Period")

                for r in results['raw_results'][:10]:
                    ret = r.return_pct
                    sample_table.add_row(
                        r.ticker,
                        r.entry_date.strftime("%Y-%m-%d"),
                        r.exit_date.strftime("%Y-%m-%d"),
                        f"{ret:.2f}%",
                        f"{r.holding_period}d",
                        style="green" if ret > 0 else "red"
                    )

                console.print(sample_table)

            console.print(f"\n[dim]Tested {results['total_trades_tested']} trades, "
                        f"{results['successful_trades']} with valid price data[/dim]\n")

        except Exception as e:
            logger.error(f"Backtest failed: {e}", exc_info=True)
            console.print(f"\n[red]✗ Error: {e}[/red]")


if __name__ == '__main__':
    cli()
