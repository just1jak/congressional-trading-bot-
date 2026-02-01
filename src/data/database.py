"""Database models and connection management"""

from datetime import datetime, date
from typing import Optional, List
from pathlib import Path

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, ForeignKey, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.pool import StaticPool

from src.utils.logger import get_logger

logger = get_logger()
Base = declarative_base()


class CongressionalTrade(Base):
    """Model for congressional stock trades"""
    __tablename__ = 'congressional_trades'

    id = Column(Integer, primary_key=True, autoincrement=True)
    politician_name = Column(String(200), nullable=False, index=True)
    party = Column(String(10))  # R, D, I
    ticker = Column(String(20), nullable=False, index=True)
    transaction_type = Column(String(50), nullable=False)  # Purchase, Sale, Exchange
    amount_range = Column(String(100))
    estimated_amount = Column(Float)
    transaction_date = Column(Date, nullable=False, index=True)
    disclosure_date = Column(Date, nullable=False, index=True)
    asset_description = Column(Text)
    source = Column(String(50))  # API name or 'scrape'
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    executed_trades = relationship("ExecutedTrade", back_populates="congressional_trade")

    def __repr__(self):
        return f"<CongressionalTrade({self.politician_name}, {self.ticker}, {self.transaction_type}, {self.transaction_date})>"


class ExecutedTrade(Base):
    """Model for our executed trades"""
    __tablename__ = 'executed_trades'

    id = Column(Integer, primary_key=True, autoincrement=True)
    congressional_trade_id = Column(Integer, ForeignKey('congressional_trades.id'))
    ticker = Column(String(20), nullable=False, index=True)
    action = Column(String(10), nullable=False)  # buy, sell
    quantity = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float)
    entry_date = Column(DateTime, nullable=False)
    exit_date = Column(DateTime)
    exit_reason = Column(String(100))  # '20% profit', 'stop loss', 'manual'
    profit_loss = Column(Float)
    profit_loss_pct = Column(Float)
    status = Column(String(20), nullable=False, index=True)  # open, closed
    mode = Column(String(20), nullable=False)  # paper, live

    # Relationships
    congressional_trade = relationship("CongressionalTrade", back_populates="executed_trades")

    def __repr__(self):
        return f"<ExecutedTrade({self.ticker}, {self.action}, {self.quantity}, {self.status})>"


class Position(Base):
    """Model for current holdings"""
    __tablename__ = 'positions'

    ticker = Column(String(20), primary_key=True)
    quantity = Column(Integer, nullable=False)
    average_entry_price = Column(Float, nullable=False)
    current_price = Column(Float)
    unrealized_pnl = Column(Float)
    unrealized_pnl_pct = Column(Float)
    mode = Column(String(20), nullable=False)  # paper, live
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Position({self.ticker}, {self.quantity} @ ${self.average_entry_price:.2f})>"


class PoliticianPerformance(Base):
    """Model for tracking politician trading performance"""
    __tablename__ = 'politician_performance'

    politician_name = Column(String(200), primary_key=True)
    party = Column(String(10))
    total_trades = Column(Integer, default=0)
    profitable_trades = Column(Integer, default=0)
    total_return = Column(Float, default=0.0)
    total_return_pct = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    average_profit = Column(Float, default=0.0)
    average_profit_pct = Column(Float, default=0.0)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<PoliticianPerformance({self.politician_name}, {self.win_rate:.2%} win rate)>"


class BacktestRun(Base):
    """Model for backtest results"""
    __tablename__ = 'backtest_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_name = Column(String(100))
    strategy_config = Column(Text)  # JSON
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    initial_capital = Column(Float, nullable=False)
    final_value = Column(Float)
    total_return = Column(Float)
    total_return_pct = Column(Float)
    total_trades = Column(Integer)
    winning_trades = Column(Integer)
    losing_trades = Column(Integer)
    win_rate = Column(Float)
    average_profit = Column(Float)
    average_profit_pct = Column(Float)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    max_drawdown_pct = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<BacktestRun({self.strategy_name}, {self.start_date} to {self.end_date}, {self.total_return_pct:.2%})>"


class StockPrice(Base):
    """Model for cached stock prices"""
    __tablename__ = 'stock_prices'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(20), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float, nullable=False)
    volume = Column(Integer)
    adjusted_close = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<StockPrice({self.ticker}, {self.date}, ${self.close:.2f})>"


# ============================================================================
# AI OPTIMIZATION TABLES
# ============================================================================

class OptimizationMetric(Base):
    """Track performance metrics over time"""
    __tablename__ = 'optimization_metrics'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    window_days = Column(Integer)  # 1, 7, 30, 90
    metric_type = Column(String(50), nullable=False, index=True)  # 'sharpe', 'win_rate', 'drawdown', etc.
    metric_value = Column(Float, nullable=False)
    extra_metadata = Column(Text)  # JSON for additional context

    def __repr__(self):
        return f"<OptimizationMetric({self.metric_type}={self.metric_value:.4f}, window={self.window_days}d)>"


class ParameterHistory(Base):
    """Track all parameter changes"""
    __tablename__ = 'parameter_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    parameter_name = Column(String(100), nullable=False, index=True)
    old_value = Column(Text)
    new_value = Column(Text)
    reason = Column(Text)
    changed_by = Column(String(50), nullable=False)  # 'auto', 'human', 'ml_model'
    approval_request_id = Column(Integer, ForeignKey('approval_requests.id'))
    performance_before = Column(Float)
    performance_after = Column(Float)

    def __repr__(self):
        return f"<ParameterHistory({self.parameter_name}: {self.old_value} → {self.new_value})>"


class ApprovalRequest(Base):
    """Queue for human approval of major changes"""
    __tablename__ = 'approval_requests'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    change_type = Column(String(50), nullable=False)  # 'strategy_switch', 'risk_adjustment', 'parameter_change'
    current_config = Column(Text)  # JSON
    proposed_config = Column(Text)  # JSON
    reason = Column(Text)
    expected_impact = Column(Text)  # JSON
    backtest_results = Column(Text)  # JSON
    llm_analysis = Column(Text)
    urgency = Column(String(20), default='normal')  # 'low', 'normal', 'high'
    status = Column(String(20), nullable=False, default='pending', index=True)  # 'pending', 'approved', 'rejected'
    reviewed_by = Column(String(100))
    reviewed_at = Column(DateTime)

    def __repr__(self):
        return f"<ApprovalRequest({self.change_type}, {self.status})>"


class MLModelVersion(Base):
    """Track ML model versions and performance"""
    __tablename__ = 'ml_model_versions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(100), nullable=False, index=True)
    version = Column(String(50), nullable=False)
    model_type = Column(String(50), nullable=False)  # 'xgboost', 'lstm', 'random_forest'
    training_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    validation_score = Column(Float)
    test_score = Column(Float)
    is_active = Column(Boolean, default=False, index=True)
    deployed_at = Column(DateTime)
    model_path = Column(String(500))  # Path to saved model file
    training_config = Column(Text)  # JSON

    def __repr__(self):
        return f"<MLModelVersion({self.model_name} v{self.version}, score={self.test_score:.4f})>"


class SignalAccuracy(Base):
    """Track signal predictions vs actual outcomes"""
    __tablename__ = 'signal_accuracy'

    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    ticker = Column(String(20), nullable=False, index=True)
    predicted_signal = Column(String(10), nullable=False)  # 'BUY', 'SELL', 'HOLD'
    predicted_confidence = Column(Float, nullable=False)
    actual_outcome = Column(String(20))  # 'profit', 'loss', 'no_trade'
    actual_pnl_pct = Column(Float)
    conflict_resolution_method = Column(String(50))
    executed_trade_id = Column(Integer, ForeignKey('executed_trades.id'))

    def __repr__(self):
        return f"<SignalAccuracy({self.ticker}, {self.predicted_signal}, conf={self.predicted_confidence:.2f})>"


class OptimizationInsight(Base):
    """Knowledge base for AI-generated insights"""
    __tablename__ = 'optimization_insights'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    insight_type = Column(String(50), nullable=False, index=True)  # 'llm_analysis', 'pattern', 'anomaly'
    market_regime = Column(String(50))  # 'bull', 'bear', 'volatile', 'stable'
    parameters_snapshot = Column(Text)  # JSON
    performance_snapshot = Column(Text)  # JSON
    insight_text = Column(Text, nullable=False)
    tags = Column(Text)  # JSON array
    source = Column(String(50), nullable=False)  # 'claude', 'ml_model', 'rule_based'

    def __repr__(self):
        return f"<OptimizationInsight({self.insight_type}, {self.source})>"


class Database:
    """Database connection and session management"""

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database connection.

        Args:
            database_url: Database connection string (defaults to SQLite)
        """
        if database_url is None:
            # Default SQLite database
            db_path = Path("data/congressional_trades.db")
            db_path.parent.mkdir(parents=True, exist_ok=True)
            database_url = f"sqlite:///{db_path}"

        logger.info(f"Connecting to database: {database_url}")

        # Create engine
        if database_url.startswith("sqlite"):
            # SQLite-specific settings
            self.engine = create_engine(
                database_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool
            )
        else:
            # PostgreSQL or other databases
            self.engine = create_engine(database_url, pool_pre_ping=True)

        # Create session factory
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        # Create tables
        self.create_tables()

    def create_tables(self):
        """Create all database tables"""
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created successfully")

    def get_session(self) -> Session:
        """
        Get a new database session.

        Returns:
            SQLAlchemy session
        """
        return self.SessionLocal()

    def drop_all_tables(self):
        """Drop all tables (use with caution!)"""
        logger.warning("Dropping all database tables...")
        Base.metadata.drop_all(bind=self.engine)
        logger.info("All tables dropped")


# Global database instance
_db_instance: Optional[Database] = None


def get_database(database_url: Optional[str] = None) -> Database:
    """
    Get or create the global database instance.

    Args:
        database_url: Database connection string

    Returns:
        Database instance
    """
    global _db_instance

    if _db_instance is None:
        _db_instance = Database(database_url)

    return _db_instance


def init_database(database_url: Optional[str] = None) -> Database:
    """
    Initialize the database.

    Args:
        database_url: Database connection string

    Returns:
        Database instance
    """
    return get_database(database_url)
