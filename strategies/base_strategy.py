from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional
import time
import logging

@dataclass
class Position:
    symbol: str
    side: str  # 'long' or 'short'
    entry_price: float
    current_price: float
    size: float
    timestamp: float
    take_profit: float
    stop_loss: float
    
@dataclass
class OrderBookLevel:
    price: float
    size: float

class OrderBook:
    def __init__(self):
        self.bids: List[OrderBookLevel] = []
        self.asks: List[OrderBookLevel] = []
        self.timestamp: float = 0
        
    def update(self, bids: List[OrderBookLevel], asks: List[OrderBookLevel]):
        self.bids = sorted(bids, key=lambda x: x.price, reverse=True)
        self.asks = sorted(asks, key=lambda x: x.price)
        self.timestamp = time.time()
        
    def get_bid_ask_ratio(self, depth: int = 10) -> float:
        bid_vol = sum(level.size for level in self.bids[:depth])
        ask_vol = sum(level.size for level in self.asks[:depth])
        return bid_vol / ask_vol if ask_vol > 0 else float('inf')
        
    def get_mid_price(self) -> float:
        if not self.bids or not self.asks:
            return 0
        return (self.bids[0].price + self.asks[0].price) / 2

class BaseStrategy(ABC):
    def __init__(self, 
                 name: str,
                 symbols: List[str],
                 max_positions: int = 1,
                 position_size_pct: float = 0.03):
                self.name = name
                self.symbols = symbols
                self.max_positions = max_positions
                self.position_size_pct = position_size_pct
                self.positions: Dict[str, Position] = {}
                self.orderbooks: Dict[str, OrderBook] = {s: OrderBook() for s in symbols}
                self.losing_trades_count = 0
                self.total_trades = 0
                self.profitable_trades = 0
                
                # Risk management
                self.max_drawdown_pct = 40.0
                self.pause_after_losses = 10
                self.current_drawdown = 0.0
                self.initial_balance = 0.0
                self.is_paused = False
                
                self.logger = logging.getLogger(f"strategy.{name}")
        
    def update_orderbook(self, symbol: str, bids: List[OrderBookLevel], asks: List[OrderBookLevel]):
        """Update the order book for a symbol"""
        if symbol in self.orderbooks:
            self.orderbooks[symbol].update(bids, asks)
            
    def check_risk_limits(self, balance: float) -> bool:
        """Check if risk limits are breached"""
        if self.initial_balance == 0:
            self.initial_balance = balance
            
        self.current_drawdown = (self.initial_balance - balance) / self.initial_balance * 100
        
        if self.current_drawdown >= self.max_drawdown_pct:
            self.logger.warning(f"Max drawdown reached: {self.current_drawdown:.2f}%")
            return False
            
        if self.losing_trades_count >= self.pause_after_losses:
            self.logger.warning(f"Max consecutive losses reached: {self.losing_trades_count}")
            self.is_paused = True
            return False
            
        return True
        
    def on_trade_closed(self, profitable: bool):
        """Update statistics after trade closure"""
        self.total_trades += 1
        if profitable:
            self.profitable_trades += 1
            self.losing_trades_count = 0
        else:
            self.losing_trades_count += 1
            
    @abstractmethod
    def should_open_position(self, symbol: str) -> Optional[Dict]:
        """Return trade parameters if should open position, None otherwise"""
        pass
        
    @abstractmethod
    def should_close_position(self, position: Position) -> bool:
        """Return True if position should be closed"""
        pass
        
    def get_win_rate(self) -> float:
        """Calculate win rate"""
        if self.total_trades == 0:
            return 0
        return self.profitable_trades / self.total_trades * 100