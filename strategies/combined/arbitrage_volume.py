from typing import Dict, Optional, List, Tuple
from ..base_strategy import BaseStrategy, Position
from ..arbitrage import ArbitrageStrategy
from ..volume_impulse import VolumeImpulseStrategy
import time
import numpy as np

class ArbitrageVolumeStrategy(BaseStrategy):
    def __init__(self, symbol_pairs: List[Tuple[str, str]], **kwargs):
        symbols = [sym for pair in symbol_pairs for sym in pair]
        super().__init__("ArbitrageVolume", symbols, **kwargs)
        
        self.symbol_pairs = symbol_pairs
        self.arbitrage_strategy = ArbitrageStrategy(symbol_pairs)
        self.volume_strategy = VolumeImpulseStrategy(symbols)
        
        # Strategy parameters
        self.min_spread_pct = 0.0015    # 0.15% minimum spread
        self.min_volume_ratio = 2.0      # Minimum volume spike ratio
        self.confirmation_window = 10     # seconds
        
        # Exit parameters
        self.take_profit_pct = 0.002     # 0.2%
        self.stop_loss_pct = 0.001       # 0.1%
        self.max_hold_time = 45          # 45 seconds
        
        # Volume confirmation thresholds
        self.volume_thresholds = {
            'high': 3.0,    # High volume confirmation
            'medium': 2.0,  # Medium volume confirmation
            'low': 1.5      # Low volume confirmation
        }
        
    def calculate_volume_profile(self, symbol: str) -> Dict:
        """Calculate volume profile for symbol"""
        orderbook = self.orderbooks[symbol]
        
        bid_volumes = [level.size for level in orderbook.bids[:5]]
        ask_volumes = [level.size for level in orderbook.asks[:5]]
        
        return {
            'total_bid_volume': sum(bid_volumes),
            'total_ask_volume': sum(ask_volumes),
            'max_bid_volume': max(bid_volumes),
            'max_ask_volume': max(ask_volumes),
            'bid_volume_std': np.std(bid_volumes),
            'ask_volume_std': np.std(ask_volumes)
        }
        
    def validate_volume_confirmation(self, symbol1: str, symbol2: str) -> str:
        """Validate volume profiles of both symbols"""
        profile1 = self.calculate_volume_profile(symbol1)
        profile2 = self.calculate_volume_profile(symbol2)
        
        # Calculate volume ratios
        bid_ratio = max(profile1['total_bid_volume'] / profile2['total_bid_volume'],
                       profile2['total_bid_volume'] / profile1['total_bid_volume'])
        
        ask_ratio = max(profile1['total_ask_volume'] / profile2['total_ask_volume'],
                       profile2['total_ask_volume'] / profile1['total_ask_volume'])
        
        # Determine confirmation level
        if bid_ratio >= self.volume_thresholds['high'] and \
           ask_ratio >= self.volume_thresholds['high']:
            return 'high'
        elif bid_ratio >= self.volume_thresholds['medium'] and \
             ask_ratio >= self.volume_thresholds['medium']:
            return 'medium'
        elif bid_ratio >= self.volume_thresholds['low'] and \
             ask_ratio >= self.volume_thresholds['low']:
            return 'low'
        else:
            return 'none'
            
    def should_open_position(self, symbol: str) -> Optional[Dict]:
        if self.is_paused:
            return None
            
        # Find paired symbol
        pair = next((pair for pair in self.symbol_pairs if symbol in pair), None)
        if not pair:
            return None
            
        symbol2 = pair[1] if pair[0] == symbol else pair[0]
        
        # Get arbitrage signal
        arb_signal = self.arbitrage_strategy.should_open_position(symbol)
        if not arb_signal:
            return None
            
        # Get volume confirmation
        volume_confirmation = self.validate_volume_confirmation(symbol, symbol2)
        if volume_confirmation == 'none':
            return None
            
        # Adjust parameters based on confirmation level
        if volume_confirmation == 'high':
            take_profit_pct = self.take_profit_pct * 1.5
            stop_loss_pct = self.stop_loss_pct * 0.8
        elif volume_confirmation == 'medium':
            take_profit_pct = self.take_profit_pct * 1.25
            stop_loss_pct = self.stop_loss_pct * 0.9
        else:  # low
            take_profit_pct = self.take_profit_pct
            stop_loss_pct = self.stop_loss_pct
            
        # Create enhanced signal
        entry_price = arb_signal['entry_price']
        return {
            'side': arb_signal['side'],
            'entry_price': entry_price,
            'take_profit': entry_price * (1 + take_profit_pct) if arb_signal['side'] == 'long' \
                         else entry_price * (1 - take_profit_pct),
            'stop_loss': entry_price * (1 - stop_loss_pct) if arb_signal['side'] == 'long' \
                        else entry_price * (1 + stop_loss_pct),
            'timestamp': time.time(),
            'paired_symbol': symbol2,
            'confidence': volume_confirmation,
            'spread': arb_signal.get('spread', 0)
        }
        
    def should_close_position(self, position: Position) -> bool:
        current_time = time.time()
        
        # Time-based exit
        if current_time - position.timestamp > self.max_hold_time:
            self.logger.info(f"Closing position due to time limit")
            return True
            
        # Get paired symbol price
        paired_symbol = position.paired_symbol
        if not paired_symbol:
            return True
            
        # Calculate current spread
        current_price = position.current_price
        paired_price = self.orderbooks[paired_symbol].get_mid_price()
        current_spread = abs(current_price - paired_price) / current_price
        
        # Dynamic exit based on confidence level
        if position.confidence == 'high':
            # Hold positions longer for high-confidence trades
            if current_spread < self.min_spread_pct * 0.2:
                self.logger.info(f"Closing high-confidence position, spread converged")
                return True
        elif position.confidence == 'medium':
            if current_spread < self.min_spread_pct * 0.4:
                self.logger.info(f"Closing medium-confidence position, spread converged")
                return True
        else:  # low confidence
            if current_spread < self.min_spread_pct * 0.6:
                self.logger.info(f"Closing low-confidence position, spread converged")
                return True
                
        # Regular take profit and stop loss checks
        if position.side == 'long':
            if position.current_price >= position.take_profit:
                self.logger.info(f"Take profit reached for long position")
                return True
            if position.current_price <= position.stop_loss:
                self.logger.info(f"Stop loss reached for long position")
                return True
        else:
            if position.current_price <= position.take_profit:
                self.logger.info(f"Take profit reached for short position")
                return True
            if position.current_price >= position.stop_loss:
                self.logger.info(f"Stop loss reached for short position")
                return True
                
        return False
        
    def on_trade_closed(self, profitable: bool):
        """Update statistics and adjust parameters"""
        super().on_trade_closed(profitable)
        
        # Update sub-strategies
        self.arbitrage_strategy.on_trade_closed(profitable)
        self.volume_strategy.on_trade_closed(profitable)
        
        # Adjust thresholds based on performance
        if not profitable:
            # Increase requirements for each confidence level
            for level in self.volume_thresholds:
                self.volume_thresholds[level] *= 1.1
            self.min_spread_pct *= 1.1
        else:
            # Gradually relax requirements if profitable
            for level in self.volume_thresholds:
                self.volume_thresholds[level] = max(
                    self.volume_thresholds[level] * 0.95,
                    self.initial_thresholds[level]
                )
            self.min_spread_pct = max(
                self.min_spread_pct * 0.95,
                0.0015  # Minimum allowed spread
            )
            
    def calculate_position_size(self, signal: Dict) -> float:
        """Calculate position size based on confidence and spread"""
        base_size = self.position_size_pct
        
        # Adjust size based on confidence
        confidence_multipliers = {
            'high': 1.0,
            'medium': 0.7,
            'low': 0.5
        }
        
        # Adjust size based on spread
        spread_multiplier = min(signal['spread'] / self.min_spread_pct, 1.5)
        
        return base_size * confidence_multipliers[signal['confidence']] * spread_multiplier