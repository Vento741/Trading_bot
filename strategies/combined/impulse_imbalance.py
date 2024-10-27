from typing import Dict, Optional, List
from ..base_strategy import BaseStrategy, Position
from ..orderbook_imbalance import OrderBookImbalanceStrategy
from ..volume_impulse import VolumeImpulseStrategy
import time

class ImpulseImbalanceStrategy(BaseStrategy):
    def __init__(self, symbols: list, **kwargs):
        super().__init__("ImpulseImbalance", symbols, **kwargs)
        
        # Initialize sub-strategies
        self.imbalance_strategy = OrderBookImbalanceStrategy(symbols)
        self.impulse_strategy = VolumeImpulseStrategy(symbols)
        
        # Combined strategy parameters
        self.confirmation_window = 15  # seconds
        self.min_volume_ratio = 2.5
        self.min_imbalance_ratio = 2.5
        
        # Position parameters
        self.take_profit_pct = 0.004   # 0.4%
        self.stop_loss_pct = 0.002     # 0.2%
        self.max_hold_time = 60        # 1 minute
        
        # Signal tracking
        self.pending_signals: Dict[str, Dict] = {}
        
    def update_orderbook(self, symbol: str, bids: List, asks: List):
        """Update orderbook for both strategies"""
        self.imbalance_strategy.update_orderbook(symbol, bids, asks)
        self.impulse_strategy.update_orderbook(symbol, bids, asks)
        
    def check_dxy_correlation(self, symbol: str) -> bool:
        """Check correlation with DXY index if available"""
        # В реальной системе здесь бы шла проверка корреляции с индексом доллара
        return True
        
    def validate_market_conditions(self, symbol: str) -> bool:
        """Validate overall market conditions"""
        orderbook = self.orderbooks[symbol]
        
        # Check spread
        spread = (orderbook.asks[0].price - orderbook.bids[0].price) / orderbook.bids[0].price
        if spread > 0.001:  # max 0.1% spread
            return False
            
        # Check liquidity
        total_bid_liquidity = sum(level.size for level in orderbook.bids[:5])
        total_ask_liquidity = sum(level.size for level in orderbook.asks[:5])
        min_liquidity = 100  # min 100 BTC equivalent
        if min(total_bid_liquidity, total_ask_liquidity) < min_liquidity:
            return False
            
        return True
        
    def should_open_position(self, symbol: str) -> Optional[Dict]:
        if self.is_paused:
            return None
            
        current_time = time.time()
        
        # Clean up old pending signals
        self.pending_signals = {
            sym: signal for sym, signal in self.pending_signals.items()
            if current_time - signal['timestamp'] <= self.confirmation_window
        }
        
        # Check market conditions
        if not self.validate_market_conditions(symbol):
            return None
            
        # Get signals from both strategies
        imbalance_signal = self.imbalance_strategy.should_open_position(symbol)
        impulse_signal = self.impulse_strategy.should_open_position(symbol)
        
        if imbalance_signal and impulse_signal:
            # Check if signals agree on direction
            if imbalance_signal['side'] == impulse_signal['side']:
                # Enhanced entry parameters
                entry_price = max(imbalance_signal['entry_price'], 
                                impulse_signal['entry_price']) if imbalance_signal['side'] == 'long' else \
                            min(imbalance_signal['entry_price'],
                                impulse_signal['entry_price'])
                
                return {
                    'side': imbalance_signal['side'],
                    'entry_price': entry_price,
                    'take_profit': entry_price * (1 + self.take_profit_pct) if imbalance_signal['side'] == 'long' \
                                 else entry_price * (1 - self.take_profit_pct),
                    'stop_loss': entry_price * (1 - self.stop_loss_pct) if imbalance_signal['side'] == 'long' \
                                else entry_price * (1 + self.stop_loss_pct),
                    'timestamp': current_time,
                    'confidence': 'high'
                }
        
        # Store single signals for potential confirmation
        if imbalance_signal and symbol not in self.pending_signals:
            self.pending_signals[symbol] = {
                'type': 'imbalance',
                'signal': imbalance_signal,
                'timestamp': current_time
            }
        elif impulse_signal and symbol not in self.pending_signals:
            self.pending_signals[symbol] = {
                'type': 'impulse',
                'signal': impulse_signal,
                'timestamp': current_time
            }
            
        return None
        
    def should_close_position(self, position: Position) -> bool:
        """Check both strategies for close signals"""
        if position.confidence == 'high':
            # More conservative exit for high-confidence trades
            current_time = time.time()
            
            # Time-based exit
            if current_time - position.timestamp > self.max_hold_time:
                self.logger.info(f"Closing high-confidence position due to time limit")
                return True
                
            # Enhanced take profit and stop loss checks
            if position.side == 'long':
                if position.current_price >= position.take_profit:
                    self.logger.info(f"Take profit reached for high-confidence long position")
                    return True
                if position.current_price <= position.stop_loss:
                    self.logger.info(f"Stop loss reached for high-confidence long position")
                    return True
            else:
                if position.current_price <= position.take_profit:
                    self.logger.info(f"Take profit reached for high-confidence short position")
                    return True
                if position.current_price >= position.stop_loss:
                    self.logger.info(f"Stop loss reached for high-confidence short position")
                    return True
                    
            # Check for reversal signals
            imbalance_close = self.imbalance_strategy.should_close_position(position)
            impulse_close = self.impulse_strategy.should_close_position(position)
            
            # Close if either strategy suggests closing
            if imbalance_close or impulse_close:
                self.logger.info(f"Closing due to reversal signal from sub-strategy")
                return True
                
        else:
            # Regular position management
            return super().should_close_position(position)
            
        return False
        
    def on_trade_closed(self, profitable: bool):
        """Update statistics and adjust parameters if needed"""
        super().on_trade_closed(profitable)
        
        # Update sub-strategies
        self.imbalance_strategy.on_trade_closed(profitable)
        self.impulse_strategy.on_trade_closed(profitable)
        
        # Adjust parameters based on performance
        if not profitable:
            # Increase confirmation requirements
            self.min_volume_ratio *= 1.1
            self.min_imbalance_ratio *= 1.1
        else:
            # Gradually return to default values
            self.min_volume_ratio = max(2.5, self.min_volume_ratio * 0.95)
            self.min_imbalance_ratio = max(2.5, self.min_imbalance_ratio * 0.95)