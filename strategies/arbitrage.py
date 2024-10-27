from typing import Dict, Optional, List, Tuple
import numpy as np
import time
from .base_strategy import BaseStrategy, Position

class ArbitrageStrategy(BaseStrategy):
    def __init__(self, symbol_pairs: List[Tuple[str, str]], **kwargs):
        """
        Initialize with pairs of correlated symbols
        Example: [("BTC-USDT", "BTC-BUSD"), ("ETH-USDT", "ETH-BUSD")]
        """
        symbols = [sym for pair in symbol_pairs for sym in pair]
        super().__init__("Arbitrage", symbols, **kwargs)
        
        self.symbol_pairs = symbol_pairs
        
        # Strategy parameters
        self.min_spread_pct = 0.002  # 0.2% minimum spread
        self.min_liquidity = 200.0   # Minimum BTC equivalent
        self.correlation_threshold = 0.8
        
        # Exit parameters
        self.take_profit_pct = 0.001  # 0.1%
        self.stop_loss_pct = 0.0008   # 0.08%
        self.max_hold_time = 30       # 30 seconds
        
        # Price history for correlation
        self.price_history: Dict[str, List[Tuple[float, float]]] = {
            s: [] for s in symbols
        }
        self.correlation_window = 300  # 5 minutes
        
    def update_price_history(self, symbol: str, price: float):
        """Update price history for correlation calculation"""
        current_time = time.time()
        self.price_history[symbol].append((current_time, price))
        
        # Remove old prices
        cutoff_time = current_time - self.correlation_window
        self.price_history[symbol] = [
            (t, p) for t, p in self.price_history[symbol]
            if t > cutoff_time
        ]
        
    def calculate_correlation(self, symbol1: str, symbol2: str) -> float:
        """Calculate price correlation between two symbols"""
        prices1 = [p for _, p in self.price_history[symbol1]]
        prices2 = [p for _, p in self.price_history[symbol2]]
        
        if len(prices1) < 10 or len(prices2) < 10:
            return 0
            
        # Ensure equal length
        min_len = min(len(prices1), len(prices2))
        prices1 = prices1[-min_len:]
        prices2 = prices2[-min_len:]
        
        return float(np.corrcoef(prices1, prices2)[0, 1])
        
    def check_liquidity(self, symbol: str) -> bool:
        """Check if there's enough liquidity"""
        orderbook = self.orderbooks[symbol]
        total_bids = sum(level.size for level in orderbook.bids[:5])
        total_asks = sum(level.size for level in orderbook.asks[:5])
        return min(total_bids, total_asks) >= self.min_liquidity
        
    def calculate_spread(self, symbol1: str, symbol2: str) -> float:
        """Calculate the spread between two symbols"""
        ob1 = self.orderbooks[symbol1]
        ob2 = self.orderbooks[symbol2]
        
        if not ob1.bids or not ob1.asks or not ob2.bids or not ob2.asks:
            return 0
            
        mid1 = ob1.get_mid_price()
        mid2 = ob2.get_mid_price()
        
        return abs(mid1 - mid2) / mid1
        
    def should_open_position(self, symbol: str) -> Optional[Dict]:
        if self.is_paused:
            return None
            
        # Find the paired symbol
        pair = next((pair for pair in self.symbol_pairs if symbol in pair), None)
        if not pair:
            return None
            
        symbol2 = pair[1] if pair[0] == symbol else pair[0]
        
        # Update price histories
        price1 = self.orderbooks[symbol].get_mid_price()
        price2 = self.orderbooks[symbol2].get_mid_price()
        self.update_price_history(symbol, price1)
        self.update_price_history(symbol2, price2)
        
        # Check correlation
        correlation = self.calculate_correlation(symbol, symbol2)
        if correlation < self.correlation_threshold:
            return None
            
        # Check liquidity
        if not self.check_liquidity(symbol) or not self.check_liquidity(symbol2):
            return None
            
        # Calculate spread
        spread = self.calculate_spread(symbol, symbol2)
        if spread < self.min_spread_pct:
            return None
            
        # Determine which symbol to trade
        if price1 > price2:
            # Short symbol1, long symbol2
            entry_price = self.orderbooks[symbol].bids[0].price
            return {
                'side': 'short',
                'entry_price': entry_price,
                'take_profit': entry_price * (1 - self.take_profit_pct),
                'stop_loss': entry_price * (1 + self.stop_loss_pct),
                'timestamp': time.time(),
                'paired_symbol': symbol2
            }
        else:
            # Long symbol1, short symbol2
            entry_price = self.orderbooks[symbol].asks[0].price
            return {
                'side': 'long',
                'entry_price': entry_price,
                'take_profit': entry_price * (1 + self.take_profit_pct),
                'stop_loss': entry_price * (1 - self.stop_loss_pct),
                'timestamp': time.time(),
                'paired_symbol': symbol2
            }
            
    def should_close_position(self, position: Position) -> bool:
        current_time = time.time()
        
        # Check time-based exit
        if current_time - position.timestamp > self.max_hold_time:
            self.logger.info(f"Closing position due to time limit: {self.max_hold_time}s")
            return True
            
        # Get paired symbol price
        paired_symbol = position.paired_symbol
        if not paired_symbol:
            return True
            
        paired_price = self.orderbooks[paired_symbol].get_mid_price()
        current_spread = abs(position.current_price - paired_price) / position.current_price
        
        # Close if spread has reduced significantly
        if current_spread < self.min_spread_pct * 0.3:
            self.logger.info(f"Spread has converged: {current_spread:.4f}")
            return True
            
        # Regular take profit and stop loss checks
        if position.side == 'long' and position.current_price >= position.take_profit:
            self.logger.info(f"Take profit reached: {position.current_price:.2f}")
            return True
        elif position.side == 'short' and position.current_price <= position.take_profit:
            self.logger.info(f"Take profit reached: {position.current_price:.2f}")
            return True
            
        if position.side == 'long' and position.current_price <= position.stop_loss:
            self.logger.info(f"Stop loss reached: {position.current_price:.2f}")
            return True
        elif position.side == 'short' and position.current_price >= position.stop_loss:
            self.logger.info(f"Stop loss reached: {position.current_price:.2f}")
            return True
            
        return False