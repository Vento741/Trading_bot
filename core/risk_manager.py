from typing import Dict, List, Optional
from dataclasses import dataclass
import time
import numpy as np
from models.position import Position
from utils.logger import setup_logger

@dataclass
class RiskMetrics:
    total_exposure: float
    max_drawdown: float
    daily_loss: float
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    correlation_matrix: Dict[str, Dict[str, float]]

class RiskManager:
    def __init__(self, config: Dict):
        self.max_position_size = config['max_position_size']
        self.max_total_risk = config['max_total_risk']
        self.max_correlated_positions = config['max_correlated_positions']
        self.max_drawdown_pct = config['max_drawdown_pct']
        self.pause_after_losses = config['pause_after_losses']
        
        self.initial_balance = 0.0
        self.current_balance = 0.0
        self.peak_balance = 0.0
        self.positions: Dict[str, Position] = {}
        
        # Performance tracking
        self.trades_history: List[Dict] = []
        self.daily_pnl: List[float] = []
        self.consecutive_losses = 0
        
        # Risk state
        self.is_trading_allowed = True
        self.trading_paused_until = 0
        
        self.logger = setup_logger('risk_manager')
        
    def update_balance(self, new_balance: float):
        """Update balance and related metrics"""
        if self.initial_balance == 0:
            self.initial_balance = new_balance
            
        self.current_balance = new_balance
        self.peak_balance = max(self.peak_balance, new_balance)
        
    def calculate_drawdown(self) -> float:
        """Calculate current drawdown percentage"""
        if self.peak_balance == 0:
            return 0
        return ((self.peak_balance - self.current_balance) / self.peak_balance) * 100
        
    def calculate_correlation(self, symbol1: str, symbol2: str, window: int = 100) -> float:
        """Calculate correlation between two symbols"""
        if symbol1 not in self.positions or symbol2 not in self.positions:
            return 0
            
        pos1 = self.positions[symbol1]
        pos2 = self.positions[symbol2]
        
        if len(pos1.price_history) < window or len(pos2.price_history) < window:
            return 0
            
        returns1 = np.diff(pos1.price_history[-window:]) / pos1.price_history[-window-1:-1]
        returns2 = np.diff(pos2.price_history[-window:]) / pos2.price_history[-window-1:-1]
        
        return float(np.corrcoef(returns1, returns2)[0, 1])
        
    def calculate_risk_metrics(self) -> RiskMetrics:
        """Calculate comprehensive risk metrics"""
        # Calculate total exposure
        total_exposure = sum(abs(pos.size * pos.current_price) 
                           for pos in self.positions.values())
        
        # Calculate daily metrics
        daily_pnl = self.daily_pnl[-1] if self.daily_pnl else 0
        
        # Calculate win rate
        if self.trades_history:
            profitable_trades = sum(1 for trade in self.trades_history if trade['pnl'] > 0)
            win_rate = profitable_trades / len(self.trades_history)
        else:
            win_rate = 0
            
        # Calculate profit factor
        gross_profit = sum(trade['pnl'] for trade in self.trades_history if trade['pnl'] > 0)
        gross_loss = abs(sum(trade['pnl'] for trade in self.trades_history if trade['pnl'] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss != 0 else 0
        
        # Calculate Sharpe ratio
        if len(self.daily_pnl) > 1:
            returns = np.array(self.daily_pnl)
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(365) if np.std(returns) != 0 else 0
        else:
            sharpe_ratio = 0
            
        # Calculate correlation matrix
        correlation_matrix = {}
        symbols = list(self.positions.keys())
        for i, sym1 in enumerate(symbols):
            correlation_matrix[sym1] = {}
            for sym2 in symbols[i+1:]:
                correlation_matrix[sym1][sym2] = self.calculate_correlation(sym1, sym2)
                
        return RiskMetrics(
            total_exposure=total_exposure,
            max_drawdown=self.calculate_drawdown(),
            daily_loss=abs(min(0, daily_pnl)),
            win_rate=win_rate,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe_ratio,
            correlation_matrix=correlation_matrix
        )
        
    def can_open_position(self, symbol: str, size: float, price: float) -> bool:
        """Check if new position can be opened"""
        # Check if trading is allowed
        if not self.is_trading_allowed:
            self.logger.warning("Trading is currently disabled")
            return False
            
        # Check if trading is paused
        if time.time() < self.trading_paused_until:
            self.logger.warning("Trading is paused due to consecutive losses")
            return False
            
        # Check drawdown limit
        current_drawdown = self.calculate_drawdown()
        if current_drawdown >= self.max_drawdown_pct:
            self.logger.warning(f"Max drawdown reached: {current_drawdown:.2f}%")
            return False
            
        # Check position size limit
        position_value = size * price
        if position_value / self.current_balance > self.max_position_size:
            self.logger.warning("Position size exceeds maximum allowed")
            return False
            
        # Check total exposure
        total_exposure = sum(abs(pos.size * pos.current_price) 
                           for pos in self.positions.values())
        new_total_exposure = total_exposure + position_value
        if new_total_exposure / self.current_balance > self.max_total_risk:
            self.logger.warning("Total exposure would exceed maximum allowed")
            return False
            
        # Check correlated positions
        correlated_count = 0
        for pos_symbol, position in self.positions.items():
            correlation = self.calculate_correlation(symbol, pos_symbol)
            if abs(correlation) > 0.7:  # High correlation threshold
                correlated_count += 1
                
        if correlated_count >= self.max_correlated_positions:
            self.logger.warning("Too many correlated positions")
            return False
            
        return True
        
    def on_trade_closed(self, trade_result: Dict):
        """Handle trade closure and update metrics"""
        self.trades_history.append(trade_result)
        
        if trade_result['pnl'] < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= self.pause_after_losses:
                pause_duration = 300  # 5 minutes
                self.trading_paused_until = time.time() + pause_duration
                self.logger.warning(f"Trading paused for {pause_duration}s due to consecutive losses")
        else:
            self.consecutive_losses = 0
            
        # Update daily PnL
        if self.daily_pnl:
            self.daily_pnl[-1] += trade_result['pnl']
        else:
            self.daily_pnl.append(trade_result['pnl'])
            
    def adjust_position_size(self, base_size: float, symbol: str) -> float:
        """Adjust position size based on risk metrics"""
        metrics = self.calculate_risk_metrics()
        
        # Reduce size based on drawdown
        drawdown_factor = max(0, 1 - metrics.max_drawdown / self.max_drawdown_pct)
        
        # Reduce size based on correlation
        correlation_penalty = 1.0
        for pos_symbol in self.positions:
            correlation = abs(self.calculate_correlation(symbol, pos_symbol))
            correlation_penalty = min(correlation_penalty, 1 - correlation)
            
        # Adjust size based on recent performance
        performance_factor = min(1.0, metrics.profit_factor / 2)
        
        adjusted_size = base_size * drawdown_factor * correlation_penalty * performance_factor
        
        # Ensure minimum and maximum limits
        min_size = base_size * 0.2  # Minimum 20% of base size
        max_size = base_size * 1.5  # Maximum 150% of base size
        
        return max(min_size, min(adjusted_size, max_size))
        
    def should_emergency_close(self) -> bool:
        """Check if emergency position closure is needed"""
        metrics = self.calculate_risk_metrics()
        
        # Check critical drawdown
        if metrics.max_drawdown >= self.max_drawdown_pct * 1.1:  # 10% buffer
            self.logger.error(f"Emergency close triggered: Critical drawdown {metrics.max_drawdown:.2f}%")
            return True
            
        # Check extreme daily loss
        daily_loss_limit = self.current_balance * 0.1  # 10% daily loss limit
        if metrics.daily_loss > daily_loss_limit:
            self.logger.error(f"Emergency close triggered: Daily loss limit exceeded")
            return True
            
        # Check extreme exposure
        if metrics.total_exposure > self.current_balance * self.max_total_risk * 1.2:  # 20% buffer
            self.logger.error(f"Emergency close triggered: Exposure limit exceeded")
            return True
            
        return False