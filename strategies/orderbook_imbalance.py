from typing import Dict, Optional
import time
from .base_strategy import BaseStrategy, Position

class OrderBookImbalanceStrategy(BaseStrategy):
    def __init__(self, symbols: list, **kwargs):
        super().__init__("OrderBookImbalance", symbols, **kwargs)
        
        # Strategy parameters
        self.min_imbalance_ratio = 3.0  # Minimum bid/ask ratio
        self.large_order_threshold = 100.0  # In BTC
        self.delta_threshold = 50.0  # % change in volume delta
        self.min_spread = 0.0005  # 0.05%
        self.min_liquidity = 500.0  # Minimum BTC in orderbook
        
        # Exit parameters
        self.take_profit_pct = 0.002  # 0.2%
        self.stop_loss_pct = 0.001    # 0.1%
        self.max_hold_time = 120      # 2 minutes
        
        # Volatility check
        self.max_volatility = 0.02    # 2% per 5 minutes
        self.price_history = []
        
    def calculate_volatility(self, symbol: str) -> float:
        """Calculate 5-minute volatility"""
        orderbook = self.orderbooks[symbol]
        current_price = orderbook.get_mid_price()
        current_time = time.time()
        
        # Add current price to history
        self.price_history.append((current_time, current_price))
        
        # Remove old prices
        self.price_history = [(t, p) for t, p in self.price_history 
                             if current_time - t <= 300]  # 5 minutes
        
        if len(self.price_history) < 2:
            return 0
            
        prices = [p for _, p in self.price_history]
        return (max(prices) - min(prices)) / min(prices)
        
    def check_liquidity(self, symbol: str) -> bool:
        """Check if there's enough liquidity in the orderbook"""
        orderbook = self.orderbooks[symbol]
        total_bid_liquidity = sum(level.size for level in orderbook.bids[:10])
        total_ask_liquidity = sum(level.size for level in orderbook.asks[:10])
        
        return min(total_bid_liquidity, total_ask_liquidity) >= self.min_liquidity
        
    def should_open_position(self, symbol: str) -> Optional[Dict]:
        if self.is_paused:
            return None
            
        orderbook = self.orderbooks[symbol]
        if not orderbook.bids or not orderbook.asks:
            return None
            
        # Check volatility
        if self.calculate_volatility(symbol) > self.max_volatility:
            return None
            
        # Check liquidity
        if not self.check_liquidity(symbol):
            return None
            
        # Calculate imbalance ratio
        imbalance_ratio = orderbook.get_bid_ask_ratio(10)
        
        # Check spread
        spread = (orderbook.asks[0].price - orderbook.bids[0].price) / orderbook.bids[0].price
        if spread < self.min_spread:
            return None
            
        # Check for large orders
        largest_bid = max(level.size for level in orderbook.bids[:5])
        largest_ask = max(level.size for level in orderbook.asks[:5])
        
        # Determine trading side based on imbalance
        if imbalance_ratio > self.min_imbalance_ratio and largest_bid > self.large_order_threshold:
            # Strong buying pressure
            entry_price = orderbook.asks[0].price
            return {
                'side': 'long',
                'entry_price': entry_price,
                'take_profit': entry_price * (1 + self.take_profit_pct),
                'stop_loss': entry_price * (1 - self.stop_loss_pct),
                'timestamp': time.time()
            }
        elif (1 / imbalance_ratio) > self.min_imbalance_ratio and largest_ask > self.large_order_threshold:
            # Strong selling pressure
            entry_price = orderbook.bids[0].price
            return {
                'side': 'short',
                'entry_price': entry_price,
                'take_profit': entry_price * (1 - self.take_profit_pct),
                'stop_loss': entry_price * (1 + self.stop_loss_pct),
                'timestamp': time.time()
            }
            
        return None
        
    def should_close_position(self, position: Position) -> bool:
        current_time = time.time()
        
        # Check time-based exit
        if current_time - position.timestamp > self.max_hold_time:
            self.logger.info(f"Closing position due to time limit: {self.max_hold_time}s")
            return True
            
        # Check take profit
        if position.side == 'long' and position.current_price >= position.take_profit:
            self.logger.info(f"Take profit reached: {position.current_price:.2f} >= {position.take_profit:.2f}")
            return True
        elif position.side == 'short' and position.current_price <= position.take_profit:
            self.logger.info(f"Take profit reached: {position.current_price:.2f} <= {position.take_profit:.2f}")
            return True
            
        # Check stop loss
        if position.side == 'long' and position.current_price <= position.stop_loss:
            self.logger.info(f"Stop loss reached: {position.current_price:.2f} <= {position.stop_loss:.2f}")
            return True
        elif position.side == 'short' and position.current_price >= position.stop_loss:
            self.logger.info(f"Stop loss reached: {position.current_price:.2f} >= {position.stop_loss:.2f}")
            return True
            
        return False