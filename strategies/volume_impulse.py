from typing import Dict, Optional, List
import numpy as np
import time
from .base_strategy import BaseStrategy, Position
from models.orderbook import OrderBook

class VolumeImpulseStrategy(BaseStrategy):
    def __init__(self, symbols: list, **kwargs):
        super().__init__("VolumeImpulse", symbols, **kwargs)
        
        # Параметры стратегии из конфига
        config = kwargs.get('config', {})
        self.volume_threshold = config.get('volume_threshold', 2.5)
        self.price_change_threshold = config.get('price_change_threshold', 0.002)
        self.consolidation_periods = config.get('consolidation_periods', 5)
        self.take_profit_pct = config.get('take_profit_pct', 0.003)
        self.stop_loss_pct = config.get('stop_loss_pct', 0.002)
        self.max_hold_time = config.get('max_hold_time', 180)
        
        # История цен и объемов
        self.price_history: Dict[str, List[float]] = {s: [] for s in symbols}
        self.volume_history: Dict[str, List[float]] = {s: [] for s in symbols}
        self.history_window = 100
        
        # Настройка логгера
        self.logger.info(f"Initialized VolumeImpulse strategy with parameters: {config}")
        
    def update_market_data(self, symbol: str, orderbook: OrderBook):
        """Обновление рыночных данных"""
        current_time = time.time()
        current_price = orderbook.get_mid_price()
        current_volume = sum(level.size for level in orderbook.bids[:5])
        
        self.price_history[symbol].append(current_price)
        self.volume_history[symbol].append(current_volume)
        
        # Ограничение размера истории
        if len(self.price_history[symbol]) > self.history_window:
            self.price_history[symbol] = self.price_history[symbol][-self.history_window:]
            self.volume_history[symbol] = self.volume_history[symbol][-self.history_window:]
            
    def detect_volume_impulse(self, symbol: str) -> Optional[Dict]:
        """Определение импульса объема"""
        if len(self.volume_history[symbol]) < self.consolidation_periods + 1:
            return None
            
        recent_volumes = self.volume_history[symbol][-self.consolidation_periods-1:]
        avg_volume = np.mean(recent_volumes[:-1])
        current_volume = recent_volumes[-1]
        
        recent_prices = self.price_history[symbol][-self.consolidation_periods-1:]
        price_change = (recent_prices[-1] - recent_prices[0]) / recent_prices[0]
        
        if current_volume > self.volume_threshold * avg_volume and \
           abs(price_change) >= self.price_change_threshold:
            return {
                'direction': 'up' if price_change > 0 else 'down',
                'volume_ratio': current_volume / avg_volume,
                'price_change': price_change
            }
        return None
        
    def should_open_position(self, symbol: str) -> Optional[Dict]:
        """Проверка условий для открытия позиции"""
        if self.is_paused:
            return None
            
        orderbook = self.orderbooks[symbol]
        if not orderbook or not orderbook.bids or not orderbook.asks:
            return None
            
        self.update_market_data(symbol, orderbook)
        impulse = self.detect_volume_impulse(symbol)
        
        if impulse:
            current_price = orderbook.get_mid_price()
            
            # Генерация сигнала
            signal = {
                'symbol': symbol,
                'side': 'long' if impulse['direction'] == 'up' else 'short',
                'entry_price': current_price,
                'take_profit': current_price * (1 + self.take_profit_pct if impulse['direction'] == 'up' 
                                              else 1 - self.take_profit_pct),
                'stop_loss': current_price * (1 - self.stop_loss_pct if impulse['direction'] == 'up'
                                            else 1 + self.stop_loss_pct),
                'volume_ratio': impulse['volume_ratio'],
                'timestamp': time.time()
            }
            
            self.logger.info(f"Generated signal for {symbol}: {signal}")
            return signal
            
        return None
        
    def should_close_position(self, position: Position) -> bool:
        """Проверка условий для закрытия позиции"""
        current_time = time.time()
        
        # Проверка тайм-аута
        if current_time - position.entry_time > self.max_hold_time:
            self.logger.info(f"Closing position due to timeout: {self.max_hold_time}s")
            return True
            
        # Проверка разворота объема
        symbol = position.symbol
        if len(self.volume_history[symbol]) >= 2:
            last_volume = self.volume_history[symbol][-1]
            prev_volume = self.volume_history[symbol][-2]
            if last_volume > prev_volume * self.volume_threshold:
                last_price = self.price_history[symbol][-1]
                prev_price = self.price_history[symbol][-2]
                price_change = (last_price - prev_price) / prev_price
                
                if (position.side == 'long' and price_change < -self.price_change_threshold) or \
                   (position.side == 'short' and price_change > self.price_change_threshold):
                    self.logger.info(f"Closing position due to volume reversal")
                    return True
                    
        # Проверка take profit и stop loss
        if position.side == 'long':
            if position.current_price >= position.take_profit or \
               position.current_price <= position.stop_loss:
                return True
        else:
            if position.current_price <= position.take_profit or \
               position.current_price >= position.stop_loss:
                return True
                
        return False