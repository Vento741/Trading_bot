from typing import Dict, Optional, List
import time
import numpy as np
from base_strategy import BaseStrategy, Position

class PriceActionStrategy(BaseStrategy):
    def __init__(self, symbols: list, **kwargs):
        super().__init__("PriceAction", symbols, **kwargs)
        
        # Strategy parameters
        self.min_impulse_pct = 0.003  # 0.3% minimum price movement
        self.volume_threshold = 2.0    # Volume must be 2x average
        self.retracement_min = 0.3     # Minimum price retracement
        self.retracement_max = 0.5     # Maximum price retracement
        
        # Exit parameters
        self.take_profit_pct = 0.003   # 0.3%
        self.stop_loss_pct = 0.0015    # 0.15%
        self.max_hold_time = 60        # 1 minute
        
        # Price and volume history
        self.price_history: Dict[str, List[float]] = {s: [] for s in symbols}
        self.volume_history: Dict[str, List[float]] = {s: [] for s in symbols}
        self.impulse_detection_window = 10  # 10 seconds
        
    def update_price_history(self, symbol: str, price: float, volume: float):
        """Update price and volume history"""
        current_time = time.time()
        
        # Add new data
        self.price_history[symbol].append((current_time, price))
        self.volume_history[symbol].append((current_time, volume))
        
        # Remove old data
        cutoff_time = current_time - self.impulse_detection_window
        self.price_history[symbol] = [(t, p) for t, p in self.price_history[symbol] 
                                    if t > cutoff_time]
        self.volume_history[symbol] = [(t, v) for t, v in self.volume_history[symbol]
                                     if t > cutoff_time]
        
    def detect_impulse(self, symbol: str) -> Optional[Dict]:
        """Detect price impulses and calculate metrics"""
        if len(self.price_history[symbol]) < 2:
            return None
            
        prices = [p for _, p in self.price_history[symbol]]
        volumes = [v for _, v in self.volume_history[symbol]]
        
        price_change = (prices[-1] - prices[0]) / prices[0]
        avg_volume = np.mean(volumes[:-1]) if len(volumes) > 1 else volumes[0]
        current_volume = volumes[-1]
        
        # Check if we have a valid impulse
        if abs(price_change) >= self.min_impulse_pct and current_volume >= self.volume_threshold * avg_volume:
            return {
                'direction': 'up' if price_change > 0 else 'down',
                'magnitude': abs(price_change),
                'volume_ratio': current_volume / avg_volume,
                'price': prices[-1],
                'start_price': prices[0]
            }
            
        return None
        
    def calculate_retracement(self, impulse: Dict, current_price: float) -> float:
        """Calculate how much price has retraced from the impulse"""
        if impulse['direction'] == 'up':
            price_move = impulse['price'] - impulse['start_price']
            retracement = impulse['price'] - current_price
        else:
            price_move = impulse['start_price'] - impulse['price']
            retracement = current_price - impulse['price']
            
        return abs(retracement / price_move) if price_move != 0 else 0
        
    def should_open_position(self, symbol: str) -> Optional[Dict]:
        if self.is_paused:
            return None
            
        orderbook = self.orderbooks[symbol]
        current_price = orderbook.get_mid_price()
        
        # Update price history
        current_volume = sum(level.size for level in orderbook.bids[:5])
        self.update_price_history(symbol, current_price, current_volume)
        
        # Detect impulse
        impulse = self.detect_impulse(symbol)
        if not impulse:
            return None
            
        # Calculate retracement
        retracement = self.calculate_retracement(impulse, current_price)
        
        # Check if retracement is in our target range
        if self.retracement_min <= retracement <= self.retracement_max:
            # Open position counter to the impulse direction
            if impulse['direction'] == 'up':
                entry_price = current_price
                return {
                    'side': 'long',
                    'entry_price': entry_price,
                    'take_profit': entry_price * (1 + self.take_profit_pct),
                    'stop_loss': entry_price * (1 - self.stop_loss_pct),
                    'timestamp': time.time()
                }
            else:
                entry_price = current_price
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