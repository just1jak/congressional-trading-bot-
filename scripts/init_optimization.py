#!/usr/bin/env python3
"""
Initialize the AI optimization system.

This script:
1. Verifies all dependencies are installed
2. Creates database tables
3. Validates configuration
4. Runs initial tests
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table
import os

console = Console()


def check_dependencies():
    """Check if all required packages are installed"""
    console.print("\n[bold cyan]1. Checking Dependencies[/bold cyan]\n")

    required_packages = [
        ('xgboost', 'XGBoost'),
        ('sklearn', 'scikit-learn'),
        ('optuna', 'Optuna'),
        ('anthropic', 'Anthropic'),
        ('schedule', 'schedule'),
        ('sqlalchemy', 'SQLAlchemy'),
        ('yaml', 'PyYAML')
    ]

    missing = []
    for package, name in required_packages:
        try:
            __import__(package)
            console.print(f"  [green]✓[/green] {name}")
        except ImportError:
            console.print(f"  [red]✗[/red] {name} - Missing")
            missing.append(name)

    if missing:
        console.print(f"\n[red]Missing packages: {', '.join(missing)}[/red]")
        console.print("Install with: [bold]pip install -r requirements.txt[/bold]\n")
        return False

    console.print("\n[green]All dependencies installed![/green]")
    return True


def initialize_database():
    """Create database tables"""
    console.print("\n[bold cyan]2. Initializing Database[/bold cyan]\n")

    try:
        from src.data.database import init_database

        db = init_database()
        console.print("  [green]✓[/green] Database initialized")
        console.print("  [green]✓[/green] All tables created (including optimization tables)")

        # Check for existing data
        session = db.get_session()
        from src.data.database import (
            CongressionalTrade,
            ExecutedTrade,
            OptimizationMetric
        )

        trade_count = session.query(CongressionalTrade).count()
        executed_count = session.query(ExecutedTrade).count()
        metric_count = session.query(OptimizationMetric).count()

        console.print(f"\n  Existing data:")
        console.print(f"    Congressional trades: {trade_count}")
        console.print(f"    Executed trades: {executed_count}")
        console.print(f"    Optimization metrics: {metric_count}")

        session.close()
        return True

    except Exception as e:
        console.print(f"  [red]✗[/red] Error: {e}")
        return False


def validate_configuration():
    """Validate configuration files"""
    console.print("\n[bold cyan]3. Validating Configuration[/bold cyan]\n")

    try:
        import yaml
        from pathlib import Path

        # Check main config
        main_config_path = Path("config/config.yaml")
        if main_config_path.exists():
            console.print(f"  [green]✓[/green] Main config found")
        else:
            console.print(f"  [yellow]⚠[/yellow] Main config not found (optional)")

        # Check optimization config
        opt_config_path = Path("config/optimization_config.yaml")
        if opt_config_path.exists():
            with open(opt_config_path) as f:
                config = yaml.safe_load(f)

            console.print(f"  [green]✓[/green] Optimization config found")

            # Validate weights sum to 1.0
            objectives = config.get('objectives', {})
            total_weight = sum([
                objectives.get('returns_weight', 0),
                objectives.get('sharpe_ratio_weight', 0),
                objectives.get('win_rate_weight', 0),
                objectives.get('drawdown_weight', 0),
                objectives.get('profit_factor_weight', 0)
            ])

            if abs(total_weight - 1.0) < 0.01:
                console.print(f"  [green]✓[/green] Objective weights sum to 1.0")
            else:
                console.print(f"  [yellow]⚠[/yellow] Objective weights sum to {total_weight:.2f} (should be 1.0)")

            # Check if optimization enabled
            if config.get('optimization', {}).get('enabled', False):
                console.print(f"  [green]✓[/green] Optimization enabled")
            else:
                console.print(f"  [yellow]⚠[/yellow] Optimization disabled in config")

        else:
            console.print(f"  [red]✗[/red] Optimization config not found")
            return False

        # Check for Claude API key (optional for Phase 1)
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if api_key:
            console.print(f"  [green]✓[/green] ANTHROPIC_API_KEY found (for Phase 4)")
        else:
            console.print(f"  [dim]○[/dim] ANTHROPIC_API_KEY not set (needed for Phase 4)")

        return True

    except Exception as e:
        console.print(f"  [red]✗[/red] Error: {e}")
        return False


def run_basic_tests():
    """Run basic functionality tests"""
    console.print("\n[bold cyan]4. Running Basic Tests[/bold cyan]\n")

    try:
        from src.optimization.metrics_collector import MetricsCollector
        from src.optimization.performance_analyzer import PerformanceAnalyzer

        # Test MetricsCollector
        collector = MetricsCollector()
        console.print(f"  [green]✓[/green] MetricsCollector initialized")

        # Test PerformanceAnalyzer
        analyzer = PerformanceAnalyzer()
        console.print(f"  [green]✓[/green] PerformanceAnalyzer initialized")

        # Test normalization functions
        test_sharpe = analyzer._normalize_sharpe(1.5)
        assert 0 <= test_sharpe <= 1
        console.print(f"  [green]✓[/green] Normalization functions working")

        # Test composite score calculation (even with no data)
        score, components = analyzer.calculate_composite_score(window_days=30)
        console.print(f"  [green]✓[/green] Composite score calculation working")

        if score == 0:
            console.print(f"    [dim]Note: Score is 0 (no trade data yet)[/dim]")

        return True

    except Exception as e:
        console.print(f"  [red]✗[/red] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def display_next_steps():
    """Show next steps for the user"""
    console.print("\n[bold cyan]Next Steps[/bold cyan]\n")

    steps = [
        "1. Run the trading bot and execute some trades (paper or live)",
        "2. After trades close, run: [bold]python -m src.cli.cli optimize collect-metrics[/bold]",
        "3. View optimization status: [bold]python -m src.cli.cli optimize status[/bold]",
        "4. Let the system accumulate data (20+ closed trades recommended)",
        "5. Review signal accuracy by strategy",
        "",
        "[dim]Phase 2+ Features:[/dim]",
        "• ML confidence predictor (Week 3-4)",
        "• Automated parameter adjustment (Week 5-6)",
        "• Claude LLM analysis (Week 7)",
        "• Advanced ML models (Week 8-9)",
        "• Continuous optimization service (Week 10)"
    ]

    for step in steps:
        if step:
            console.print(f"  {step}")
        else:
            console.print()


def main():
    """Main initialization function"""
    console.print("\n[bold]Congressional Trading Bot - AI Optimization System[/bold]")
    console.print("[bold]Phase 1: Foundation Setup[/bold]\n")

    success = True

    # Run all checks
    success &= check_dependencies()
    success &= initialize_database()
    success &= validate_configuration()
    success &= run_basic_tests()

    # Display results
    if success:
        console.print("\n[bold green]✓ Optimization System Initialized Successfully![/bold green]\n")
        display_next_steps()
    else:
        console.print("\n[bold red]✗ Initialization Failed[/bold red]")
        console.print("Please fix the errors above and try again.\n")
        sys.exit(1)


if __name__ == '__main__':
    main()
