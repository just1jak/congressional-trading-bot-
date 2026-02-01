"""Reusable Streamlit components for visualizations"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from typing import List, Dict
from datetime import datetime


def display_metric_cards(metrics: Dict):
    """Display key metrics in card layout"""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Trades",
            f"{metrics['total_trades']:,}",
            delta=None
        )

    with col2:
        avg_return = metrics['avg_return']
        st.metric(
            "Avg Return",
            f"{avg_return:.2f}%",
            delta=f"{avg_return:.2f}%",
            delta_color="normal"
        )

    with col3:
        st.metric(
            "Win Rate",
            f"{metrics['win_rate']:.1%}",
            delta=None
        )

    with col4:
        st.metric(
            "Sharpe Ratio",
            f"{metrics['sharpe_ratio']:.2f}",
            delta=None
        )


def plot_equity_curve(results: List[Dict]):
    """Plot cumulative returns over time (equity curve)"""
    if not results:
        st.warning("No results to plot")
        return

    # Convert to DataFrame
    df = pd.DataFrame(results)
    df['entry_date'] = pd.to_datetime(df['entry_date'])
    df = df.sort_values('entry_date')

    # Calculate cumulative returns
    df['cumulative_return'] = (1 + df['return_pct'] / 100).cumprod() - 1

    # Create figure
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['entry_date'],
        y=df['cumulative_return'] * 100,
        mode='lines',
        name='Strategy Returns',
        line=dict(color='#00CC96', width=2),
        fill='tozeroy',
        fillcolor='rgba(0, 204, 150, 0.1)'
    ))

    # Add zero line
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

    fig.update_layout(
        title="Equity Curve - Cumulative Returns Over Time",
        xaxis_title="Date",
        yaxis_title="Cumulative Return (%)",
        hovermode='x unified',
        template='plotly_dark',
        height=500
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_returns_distribution(results: List[Dict]):
    """Plot histogram of trade returns"""
    if not results:
        st.warning("No results to plot")
        return

    df = pd.DataFrame(results)
    returns = df['return_pct'].dropna()

    fig = go.Figure()

    fig.add_trace(go.Histogram(
        x=returns,
        nbinsx=50,
        name='Returns',
        marker_color='#636EFA',
        opacity=0.75
    ))

    # Add mean line
    mean_return = returns.mean()
    fig.add_vline(
        x=mean_return,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Mean: {mean_return:.2f}%",
        annotation_position="top"
    )

    fig.update_layout(
        title="Distribution of Trade Returns",
        xaxis_title="Return (%)",
        yaxis_title="Frequency",
        template='plotly_dark',
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_holding_period_comparison(period_metrics: Dict[int, Dict]):
    """Bar chart comparing performance across holding periods"""
    if not period_metrics:
        st.warning("No period metrics to plot")
        return

    periods = list(period_metrics.keys())
    avg_returns = [period_metrics[p]['avg_return'] for p in periods]
    win_rates = [period_metrics[p]['win_rate'] * 100 for p in periods]
    sharpe_ratios = [period_metrics[p]['sharpe_ratio'] for p in periods]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=[f"{p}d" for p in periods],
        y=avg_returns,
        name='Avg Return (%)',
        marker_color='#00CC96',
        yaxis='y'
    ))

    fig.add_trace(go.Bar(
        x=[f"{p}d" for p in periods],
        y=win_rates,
        name='Win Rate (%)',
        marker_color='#AB63FA',
        yaxis='y'
    ))

    fig.update_layout(
        title="Performance by Holding Period",
        xaxis_title="Holding Period",
        yaxis_title="Value (%)",
        template='plotly_dark',
        height=400,
        barmode='group'
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_drawdown(results: List[Dict]):
    """Plot drawdown over time"""
    if not results:
        st.warning("No results to plot")
        return

    df = pd.DataFrame(results)
    df['entry_date'] = pd.to_datetime(df['entry_date'])
    df = df.sort_values('entry_date')

    # Calculate cumulative returns and drawdown
    cumulative = (1 + df['return_pct'] / 100).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max * 100

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['entry_date'],
        y=drawdown,
        mode='lines',
        name='Drawdown',
        line=dict(color='#EF553B', width=2),
        fill='tozeroy',
        fillcolor='rgba(239, 85, 59, 0.2)'
    ))

    fig.update_layout(
        title="Drawdown Over Time",
        xaxis_title="Date",
        yaxis_title="Drawdown (%)",
        template='plotly_dark',
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_top_performers(results: List[Dict], n: int = 10, by: str = 'politician'):
    """Bar chart of top performing politicians or tickers"""
    if not results:
        st.warning("No results to plot")
        return

    df = pd.DataFrame(results)

    # Group by politician or ticker
    if by == 'politician':
        grouped = df.groupby('politician_name')['return_pct'].agg(['mean', 'count'])
        grouped = grouped[grouped['count'] >= 3]  # At least 3 trades
        title = f"Top {n} Politicians by Average Return"
        xlabel = "Politician"
    else:  # ticker
        grouped = df.groupby('ticker')['return_pct'].agg(['mean', 'count'])
        grouped = grouped[grouped['count'] >= 2]  # At least 2 trades
        title = f"Top {n} Tickers by Average Return"
        xlabel = "Ticker"

    # Sort and take top N
    top = grouped.sort_values('mean', ascending=False).head(n)

    fig = go.Figure()

    colors = ['#00CC96' if x > 0 else '#EF553B' for x in top['mean']]

    fig.add_trace(go.Bar(
        x=top.index,
        y=top['mean'],
        text=[f"{v:.1f}%" for v in top['mean']],
        textposition='outside',
        marker_color=colors,
        hovertemplate='%{x}<br>Avg Return: %{y:.2f}%<br>Trades: %{customdata}<extra></extra>',
        customdata=top['count']
    ))

    fig.update_layout(
        title=title,
        xaxis_title=xlabel,
        yaxis_title="Average Return (%)",
        template='plotly_dark',
        height=500,
        showlegend=False
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_win_loss_breakdown(metrics: Dict):
    """Pie chart showing win/loss/breakeven breakdown"""
    wins = metrics['total_wins']
    losses = metrics['total_losses']

    fig = go.Figure(data=[go.Pie(
        labels=['Winning Trades', 'Losing Trades'],
        values=[wins, losses],
        hole=.3,
        marker_colors=['#00CC96', '#EF553B']
    )])

    fig.update_layout(
        title="Win/Loss Breakdown",
        template='plotly_dark',
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_monthly_returns(results: List[Dict]):
    """Heatmap of monthly returns"""
    if not results:
        st.warning("No results to plot")
        return

    df = pd.DataFrame(results)
    df['entry_date'] = pd.to_datetime(df['entry_date'])
    df['year'] = df['entry_date'].dt.year
    df['month'] = df['entry_date'].dt.month

    # Calculate monthly returns
    monthly = df.groupby(['year', 'month'])['return_pct'].mean().reset_index()

    # Pivot for heatmap
    heatmap_data = monthly.pivot(index='year', columns='month', values='return_pct')

    fig = go.Figure(data=go.Heatmap(
        z=heatmap_data.values,
        x=['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
        y=heatmap_data.index,
        colorscale='RdYlGn',
        zmid=0,
        text=heatmap_data.values,
        texttemplate='%{text:.1f}%',
        textfont={"size": 10},
        colorbar=dict(title="Return (%)")
    ))

    fig.update_layout(
        title="Monthly Average Returns Heatmap",
        xaxis_title="Month",
        yaxis_title="Year",
        template='plotly_dark',
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)


def display_trade_table(results: List[Dict], max_rows: int = 50):
    """Display table of individual trades"""
    if not results:
        st.warning("No trades to display")
        return

    df = pd.DataFrame(results)

    # Format for display
    display_df = df[['ticker', 'politician_name', 'entry_date', 'exit_date',
                     'entry_price', 'exit_price', 'return_pct', 'holding_period']].copy()

    display_df['entry_date'] = pd.to_datetime(display_df['entry_date']).dt.strftime('%Y-%m-%d')
    display_df['exit_date'] = pd.to_datetime(display_df['exit_date']).dt.strftime('%Y-%m-%d')
    display_df['entry_price'] = display_df['entry_price'].map('${:.2f}'.format)
    display_df['exit_price'] = display_df['exit_price'].map('${:.2f}'.format)
    display_df['return_pct'] = display_df['return_pct'].map('{:.2f}%'.format)
    display_df['holding_period'] = display_df['holding_period'].astype(str) + 'd'

    display_df.columns = ['Ticker', 'Politician', 'Entry Date', 'Exit Date',
                          'Entry Price', 'Exit Price', 'Return', 'Hold Period']

    st.dataframe(display_df.head(max_rows), use_container_width=True, height=400)
