"""Streamlit Dashboard for Congressional Trading Bot"""

import streamlit as st
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.backtest.engine import BacktestEngine
from src.backtest.strategies import FollowAllStrategy, TopPerformersStrategy, LargeTradesStrategy
from src.data.database import get_database, CongressionalTrade
from src.ui.components import (
    display_metric_cards,
    plot_equity_curve,
    plot_returns_distribution,
    plot_holding_period_comparison,
    plot_drawdown,
    plot_top_performers,
    plot_win_loss_breakdown,
    plot_monthly_returns,
    display_trade_table
)

# Page config
st.set_page_config(
    page_title="Congressional Trading Bot",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main {
        padding: 0rem 1rem;
    }
    h1 {
        color: #00CC96;
    }
    .stMetric {
        background-color: #1E1E1E;
        padding: 1rem;
        border-radius: 0.5rem;
    }
    </style>
""", unsafe_allow_html=True)


def load_database_stats():
    """Load basic database statistics"""
    db = get_database()
    session = db.get_session()

    try:
        total_trades = session.query(CongressionalTrade).count()
        latest_trade = session.query(CongressionalTrade).order_by(
            CongressionalTrade.disclosure_date.desc()
        ).first()

        unique_politicians = session.query(CongressionalTrade.politician_name).distinct().count()
        unique_tickers = session.query(CongressionalTrade.ticker).distinct().count()

        return {
            'total_trades': total_trades,
            'latest_disclosure': latest_trade.disclosure_date if latest_trade else None,
            'unique_politicians': unique_politicians,
            'unique_tickers': unique_tickers
        }
    finally:
        session.close()


def run_backtest_ui(strategy_name, start_date, end_date, max_trades, min_value):
    """Run backtest and return results"""

    # Initialize strategy
    if strategy_name == "Follow All Trades":
        strategy = FollowAllStrategy(min_trade_value=min_value)
    elif strategy_name == "Top Performers":
        strategy = TopPerformersStrategy(top_n_politicians=10)
    else:  # Large Trades
        strategy = LargeTradesStrategy(min_trade_value=min_value or 50000)

    # Initialize engine
    engine = BacktestEngine()

    # Run backtest with progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()

    def update_progress(current, total):
        pct = int((current / total) * 100) if total > 0 else 0
        progress_bar.progress(pct)
        status_text.text(f"Processing trade {current}/{total}...")

    with st.spinner("Running backtest..."):
        results = engine.run_backtest(
            strategy=strategy,
            start_date=start_date,
            end_date=end_date,
            max_trades=max_trades,
            progress_callback=update_progress
        )

    progress_bar.empty()
    status_text.empty()

    return results


def main():
    """Main Streamlit application"""

    # Sidebar
    st.sidebar.title("🏛️ Congressional Trading Bot")
    st.sidebar.markdown("---")

    # Database stats
    st.sidebar.subheader("📊 Database Stats")
    db_stats = load_database_stats()

    st.sidebar.metric("Total Trades", f"{db_stats['total_trades']:,}")
    st.sidebar.metric("Politicians", f"{db_stats['unique_politicians']:,}")
    st.sidebar.metric("Tickers", f"{db_stats['unique_tickers']:,}")

    if db_stats['latest_disclosure']:
        st.sidebar.metric("Latest Disclosure",
                         db_stats['latest_disclosure'].strftime("%Y-%m-%d"))

    st.sidebar.markdown("---")

    # Navigation
    page = st.sidebar.radio(
        "Navigation",
        ["🏠 Dashboard", "🎯 Run Backtest", "📈 Trade Explorer", "⚖️ Compare Strategies"]
    )

    # Main content
    if page == "🏠 Dashboard":
        show_dashboard()
    elif page == "🎯 Run Backtest":
        show_backtest_runner()
    elif page == "📈 Trade Explorer":
        show_trade_explorer()
    else:  # Compare Strategies
        show_strategy_comparison()


def show_dashboard():
    """Dashboard overview page"""
    st.title("📊 Congressional Trading Dashboard")
    st.markdown("### Overview of Congressional Stock Trading Activity")

    # Quick stats
    db_stats = load_database_stats()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Trades", f"{db_stats['total_trades']:,}")
    with col2:
        st.metric("Politicians", f"{db_stats['unique_politicians']:,}")
    with col3:
        st.metric("Tickers", f"{db_stats['unique_tickers']:,}")
    with col4:
        if db_stats['latest_disclosure']:
            st.metric("Latest Disclosure",
                     db_stats['latest_disclosure'].strftime("%Y-%m-%d"))

    st.markdown("---")

    # Instructions
    st.markdown("""
    ## 🚀 Getting Started

    ### 1. Run Backtest
    - Navigate to **Run Backtest** page
    - Select a strategy and parameters
    - View comprehensive results with interactive charts

    ### 2. Explore Trades
    - Browse historical congressional trades
    - Filter by politician, ticker, or date range

    ### 3. Compare Strategies
    - Run multiple strategies side-by-side
    - Compare performance metrics

    ### Available Strategies

    **Follow All Trades**
    - Baseline strategy following every congressional purchase
    - Accounts for 45-day disclosure lag
    - Tests holding periods: 30, 60, 90 days

    **Top Performers**
    - Follows trades from historically best-performing politicians
    - Dynamically updates based on rolling performance

    **Large Trades**
    - Only follows trades above a value threshold
    - Hypothesis: Larger trades signal higher conviction

    """)


def show_backtest_runner():
    """Backtest runner page"""
    st.title("🎯 Run Backtest")

    # Strategy selection
    col1, col2 = st.columns([1, 1])

    with col1:
        strategy_name = st.selectbox(
            "Select Strategy",
            ["Follow All Trades", "Top Performers", "Large Trades"]
        )

    with col2:
        max_trades = st.number_input(
            "Max Trades (for testing)",
            min_value=10,
            max_value=10000,
            value=100,
            step=10,
            help="Limit number of trades for faster testing"
        )

    # Date range
    col3, col4 = st.columns(2)

    with col3:
        start_date = st.date_input(
            "Start Date",
            value=datetime(2023, 1, 1),
            help="Start date for backtest period"
        )

    with col4:
        end_date = st.date_input(
            "End Date",
            value=datetime.now(),
            help="End date for backtest period"
        )

    # Strategy-specific parameters
    min_value = None
    if strategy_name in ["Follow All Trades", "Large Trades"]:
        min_value = st.number_input(
            "Minimum Trade Value ($)",
            min_value=1000,
            max_value=1000000,
            value=15000 if strategy_name == "Follow All Trades" else 50000,
            step=5000
        )

    # Run button
    if st.button("🚀 Run Backtest", type="primary"):
        # Convert dates to datetime
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.min.time())

        # Run backtest
        results = run_backtest_ui(strategy_name, start_dt, end_dt, max_trades, min_value)

        # Store in session state
        st.session_state['backtest_results'] = results

        st.success("✅ Backtest completed!")

    # Display results if available
    if 'backtest_results' in st.session_state:
        results = st.session_state['backtest_results']

        st.markdown("---")
        st.markdown("## 📊 Results")

        # Overall metrics
        metrics = results['overall_metrics']
        display_metric_cards(metrics)

        # Tabs for different views
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📈 Performance", "📊 Analysis", "🏆 Top Performers", "📅 Trades", "📉 Risk"
        ])

        with tab1:
            st.markdown("### Equity Curve")
            if results['raw_results']:
                results_dict = [
                    {
                        'entry_date': r.entry_date,
                        'exit_date': r.exit_date,
                        'return_pct': r.return_pct,
                        'ticker': r.ticker,
                        'politician_name': r.politician_name,
                        'entry_price': r.entry_price,
                        'exit_price': r.exit_price,
                        'holding_period': r.holding_period
                    }
                    for r in results['raw_results']
                ]
                plot_equity_curve(results_dict)

                st.markdown("### Holding Period Comparison")
                plot_holding_period_comparison(results['metrics_by_holding_period'])

        with tab2:
            st.markdown("### Returns Distribution")
            if results['raw_results']:
                plot_returns_distribution(results_dict)

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("### Win/Loss Breakdown")
                    plot_win_loss_breakdown(metrics)

                with col2:
                    st.markdown("### Monthly Returns")
                    plot_monthly_returns(results_dict)

        with tab3:
            st.markdown("### Top Performing Politicians")
            if results['raw_results']:
                plot_top_performers(results_dict, n=10, by='politician')

                st.markdown("### Top Performing Tickers")
                plot_top_performers(results_dict, n=10, by='ticker')

        with tab4:
            st.markdown("### Individual Trades")
            if results['raw_results']:
                display_trade_table(results_dict, max_rows=100)

        with tab5:
            st.markdown("### Drawdown Analysis")
            if results['raw_results']:
                plot_drawdown(results_dict)

                # Risk metrics table
                st.markdown("### Risk Metrics")
                risk_data = {
                    'Metric': ['Max Drawdown', 'Sharpe Ratio', 'Worst Trade', 'Avg Loss'],
                    'Value': [
                        f"{metrics['max_drawdown']:.2f}%",
                        f"{metrics['sharpe_ratio']:.2f}",
                        f"{metrics['worst_trade']:.2f}%",
                        f"{metrics['avg_loss']:.2f}%"
                    ]
                }
                st.table(pd.DataFrame(risk_data))


def show_trade_explorer():
    """Trade explorer page"""
    st.title("📈 Trade Explorer")
    st.markdown("Browse historical congressional trades")

    db = get_database()
    session = db.get_session()

    try:
        # Filters
        col1, col2, col3 = st.columns(3)

        with col1:
            politicians = session.query(CongressionalTrade.politician_name).distinct().all()
            politician_list = ["All"] + sorted([p[0] for p in politicians if p[0]])
            selected_politician = st.selectbox("Politician", politician_list)

        with col2:
            tickers = session.query(CongressionalTrade.ticker).distinct().all()
            ticker_list = ["All"] + sorted([t[0] for t in tickers if t[0]])
            selected_ticker = st.selectbox("Ticker", ticker_list)

        with col3:
            transaction_type = st.selectbox("Transaction Type", ["All", "Purchase", "Sale"])

        # Query
        query = session.query(CongressionalTrade)

        if selected_politician != "All":
            query = query.filter(CongressionalTrade.politician_name == selected_politician)

        if selected_ticker != "All":
            query = query.filter(CongressionalTrade.ticker == selected_ticker)

        if transaction_type != "All":
            query = query.filter(CongressionalTrade.transaction_type == transaction_type)

        trades = query.order_by(CongressionalTrade.disclosure_date.desc()).limit(500).all()

        # Display
        st.markdown(f"### Found {len(trades)} trades")

        if trades:
            df = pd.DataFrame([{
                'Politician': t.politician_name,
                'Party': t.party,
                'Ticker': t.ticker,
                'Type': t.transaction_type,
                'Amount': t.amount_range or 'N/A',
                'Transaction Date': t.transaction_date.strftime("%Y-%m-%d"),
                'Disclosure Date': t.disclosure_date.strftime("%Y-%m-%d"),
                'Description': t.asset_description
            } for t in trades])

            st.dataframe(df, use_container_width=True, height=600)

    finally:
        session.close()


def show_strategy_comparison():
    """Strategy comparison page"""
    st.title("⚖️ Compare Strategies")
    st.markdown("Run multiple strategies and compare performance")

    st.info("💡 Feature coming soon! This will allow you to run all strategies simultaneously "
            "and compare their performance side-by-side.")

    # Placeholder for future implementation
    st.markdown("""
    ### Planned Features:
    - Run all 3 strategies simultaneously
    - Side-by-side performance comparison
    - Statistical significance testing
    - Strategy correlation analysis
    - Best strategy recommendation based on metrics
    """)


if __name__ == "__main__":
    main()
