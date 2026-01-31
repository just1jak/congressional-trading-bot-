"""Risk management module"""

from dataclasses import dataclass
from typing import Optional, Tuple
from datetime import datetime

from src.data.database import ExecutedTrade, Position
from src.utils.logger import get_logger
from src.utils.helpers import load_config

logger = get_logger()


@dataclass
class RiskConfig:
    """Risk management configuration"""
    profit_threshold: float = 0.20  # 20% profit target
    stop_loss: float = -0.10  # 10% stop loss
    max_position_size: float = 0.05  # 5% of portfolio per position
    max_positions: int = 10  # Maximum concurrent positions
    min_position_value: float = 1000  # Minimum dollars per position


class RiskManager:
    """Manages trading risk and position sizing"""

    def __init__(self, config: Optional[RiskConfig] = None):
        """
        Initialize risk manager.

        Args:
            config: Risk configuration (loads from file if not provided)
        """
        if config is None:
            # Load from config file
            app_config = load_config()
            risk_config = app_config.get('risk_management', {})

            self.config = RiskConfig(
                profit_threshold=risk_config.get('profit_threshold', 0.20),
                stop_loss=risk_config.get('stop_loss', -0.10),
                max_position_size=risk_config.get('max_position_size', 0.05),
                max_positions=risk_config.get('max_positions', 10),
                min_position_value=risk_config.get('min_position_value', 1000)
            )
        else:
            self.config = config

        logger.info(f"Risk Manager initialized: {self.config}")

    def should_exit_position(
        self,
        position: Position,
        current_price: float
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if a position should be closed.

        Args:
            position: Current position
            current_price: Current stock price

        Returns:
            Tuple of (should_exit, exit_reason)
        """
        # Calculate profit/loss percentage
        profit_pct = (current_price - position.average_entry_price) / position.average_entry_price

        # Check profit threshold
        if profit_pct >= self.config.profit_threshold:
            return True, f"{self.config.profit_threshold:.0%} profit threshold reached"

        # Check stop loss
        if profit_pct <= self.config.stop_loss:
            return True, f"Stop loss triggered at {profit_pct:.2%}"

        return False, None

    def should_exit_trade(
        self,
        trade: ExecutedTrade,
        current_price: float
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if an executed trade should be closed.

        Args:
            trade: Executed trade
            current_price: Current stock price

        Returns:
            Tuple of (should_exit, exit_reason)
        """
        if trade.status != 'open':
            return False, None

        # Calculate profit/loss percentage
        profit_pct = (current_price - trade.entry_price) / trade.entry_price

        # Check profit threshold
        if profit_pct >= self.config.profit_threshold:
            return True, f"{self.config.profit_threshold:.0%} profit threshold reached"

        # Check stop loss
        if profit_pct <= self.config.stop_loss:
            return True, f"Stop loss triggered at {profit_pct:.2%}"

        return False, None

    def calculate_position_size(
        self,
        account_balance: float,
        stock_price: float,
        current_positions_count: int = 0
    ) -> int:
        """
        Calculate how many shares to buy.

        Args:
            account_balance: Current account balance
            stock_price: Current stock price
            current_positions_count: Number of open positions

        Returns:
            Number of shares to buy (0 if shouldn't trade)
        """
        # Check if we have room for another position
        if current_positions_count >= self.config.max_positions:
            logger.warning(f"Max positions ({self.config.max_positions}) reached")
            return 0

        # Calculate maximum dollars to invest
        max_dollars = account_balance * self.config.max_position_size

        # Check minimum position value
        if max_dollars < self.config.min_position_value:
            logger.warning(f"Position size (${max_dollars:.2f}) below minimum (${self.config.min_position_value:.2f})")
            return 0

        # Calculate shares
        shares = int(max_dollars / stock_price)

        # Need at least 1 share
        if shares < 1:
            logger.warning(f"Cannot afford even 1 share at ${stock_price:.2f}")
            return 0

        logger.info(f"Position size: {shares} shares @ ${stock_price:.2f} = ${shares * stock_price:.2f}")
        return shares

    def calculate_profit_loss(
        self,
        entry_price: float,
        exit_price: float,
        quantity: int
    ) -> Tuple[float, float]:
        """
        Calculate profit/loss for a trade.

        Args:
            entry_price: Entry price per share
            exit_price: Exit price per share
            quantity: Number of shares

        Returns:
            Tuple of (profit_loss_dollars, profit_loss_percentage)
        """
        pl_dollars = (exit_price - entry_price) * quantity
        pl_pct = (exit_price - entry_price) / entry_price

        return pl_dollars, pl_pct

    def validate_trade(
        self,
        ticker: str,
        quantity: int,
        price: float,
        account_balance: float,
        current_positions_count: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate if a trade should be executed.

        Args:
            ticker: Stock ticker
            quantity: Number of shares
            price: Price per share
            account_balance: Current account balance
            current_positions_count: Number of open positions

        Returns:
            Tuple of (is_valid, rejection_reason)
        """
        # Check max positions
        if current_positions_count >= self.config.max_positions:
            return False, f"Max positions ({self.config.max_positions}) reached"

        # Check if we have enough cash
        total_cost = quantity * price
        if total_cost > account_balance:
            return False, f"Insufficient funds (need ${total_cost:.2f}, have ${account_balance:.2f})"

        # Check minimum position value
        if total_cost < self.config.min_position_value:
            return False, f"Position value (${total_cost:.2f}) below minimum (${self.config.min_position_value:.2f})"

        # Check position size limit
        max_allowed = account_balance * self.config.max_position_size
        if total_cost > max_allowed:
            return False, f"Position size (${total_cost:.2f}) exceeds limit (${max_allowed:.2f})"

        return True, None

    def get_risk_metrics(self) -> dict:
        """
        Get current risk management settings.

        Returns:
            Dictionary of risk metrics
        """
        return {
            'profit_threshold': f"{self.config.profit_threshold:.2%}",
            'stop_loss': f"{self.config.stop_loss:.2%}",
            'max_position_size': f"{self.config.max_position_size:.2%}",
            'max_positions': self.config.max_positions,
            'min_position_value': f"${self.config.min_position_value:.2f}"
        }
