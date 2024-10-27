from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import numpy as np
import time

@dataclass
class OrderBookLevel:
    price: float
    size: float
    exchange: Optional[str] = None
    timestamp: Optional[float] = None
    
    def to_tuple(self) -> Tuple[float, float]:
        return (self.price, self.size)

@dataclass
class OrderBook:
    symbol: str
    timestamp: float
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    exchange: str = ''
    depth: int = 20
    
    # Кэшированные метрики
    _cached_metrics: dict = field(default_factory=dict)
    _cache_timestamp: float = field(default_factory=time.time)
    _cache_duration: float = 1.0  # секунда
    
    def __post_init__(self):
        """Инициализация после создания"""
        self.bids = sorted(self.bids, key=lambda x: x.price, reverse=True)[:self.depth]
        self.asks = sorted(self.asks, key=lambda x: x.price)[:self.depth]
        
    def get_mid_price(self) -> float:
        """Получить среднюю цену"""
        if not self.bids or not self.asks:
            return 0.0
        return (self.bids[0].price + self.asks[0].price) / 2
        
    def get_spread(self) -> float:
        """Получить текущий спред"""
        if not self.bids or not self.asks:
            return 0.0
        return self.asks[0].price - self.bids[0].price
        
    def get_spread_percentage(self) -> float:
        """Получить спред в процентах"""
        if not self.bids or not self.asks:
            return 0.0
        mid_price = self.get_mid_price()
        if mid_price == 0:
            return 0.0
        return (self.get_spread() / mid_price) * 100
        
    def get_volume_imbalance(self, levels: int = 5) -> float:
        """Получить дисбаланс объемов"""
        if not self.bids or not self.asks:
            return 0.0
            
        bid_volume = sum(level.size for level in self.bids[:levels])
        ask_volume = sum(level.size for level in self.asks[:levels])
        
        total_volume = bid_volume + ask_volume
        if total_volume == 0:
            return 0.0
            
        return (bid_volume - ask_volume) / total_volume
        
    def get_weighted_mid_price(self, volume_weight: float = 0.5) -> float:
        """Получить средневзвешенную цену"""
        if self._should_update_cache('weighted_mid_price'):
            bid_prices = [level.price for level in self.bids[:5]]
            ask_prices = [level.price for level in self.asks[:5]]
            bid_sizes = [level.size for level in self.bids[:5]]
            ask_sizes = [level.size for level in self.asks[:5]]
            
            total_bid_size = sum(bid_sizes)
            total_ask_size = sum(ask_sizes)
            
            if total_bid_size == 0 or total_ask_size == 0:
                self._cached_metrics['weighted_mid_price'] = self.get_mid_price()
            else:
                weighted_bid = sum(p * s for p, s in zip(bid_prices, bid_sizes)) / total_bid_size
                weighted_ask = sum(p * s for p, s in zip(ask_prices, ask_sizes)) / total_ask_size
                self._cached_metrics['weighted_mid_price'] = weighted_bid * volume_weight + weighted_ask * (1 - volume_weight)
                
        return self._cached_metrics['weighted_mid_price']
        
    def get_liquidity_at_price(self, price: float, side: str) -> float:
        """Получить ликвидность на заданной цене"""
        if side.lower() == 'buy':
            levels = [level for level in self.asks if level.price <= price]
        else:
            levels = [level for level in self.bids if level.price >= price]
            
        return sum(level.size for level in levels)
        
    def calculate_impact_price(self, size: float, side: str) -> float:
        """Рассчитать цену с учетом влияния на рынок"""
        if side.lower() == 'buy':
            levels = self.asks
            remaining_size = size
            total_cost = 0.0
            
            for level in levels:
                if remaining_size <= 0:
                    break
                executed_size = min(remaining_size, level.size)
                total_cost += executed_size * level.price
                remaining_size -= executed_size
                
            if remaining_size > 0:
                return float('inf')
            return total_cost / size
            
        else:  # sell
            levels = self.bids
            remaining_size = size
            total_revenue = 0.0
            
            for level in levels:
                if remaining_size <= 0:
                    break
                executed_size = min(remaining_size, level.size)
                total_revenue += executed_size * level.price
                remaining_size -= executed_size
                
            if remaining_size > 0:
                return 0.0
            return total_revenue / size
            
    def calculate_market_depth(self, price_levels: int = 10) -> dict:
        """Рассчитать глубину рынка"""
        if self._should_update_cache('market_depth'):
            bid_depth = sum(level.size * level.price for level in self.bids[:price_levels])
            ask_depth = sum(level.size * level.price for level in self.asks[:price_levels])
            
            self._cached_metrics['market_depth'] = {
                'bid_depth': bid_depth,
                'ask_depth': ask_depth,
                'total_depth': bid_depth + ask_depth,
                'depth_ratio': bid_depth / ask_depth if ask_depth > 0 else float('inf')
            }
            
        return self._cached_metrics['market_depth']
        
    def get_price_levels_distribution(self) -> dict:
        """Получить распределение уровней цен"""
        if self._should_update_cache('price_distribution'):
            bid_prices = np.array([level.price for level in self.bids])
            ask_prices = np.array([level.price for level in self.asks])
            
            self._cached_metrics['price_distribution'] = {
                'bid_mean': float(np.mean(bid_prices)) if len(bid_prices) > 0 else 0.0,
                'bid_std': float(np.std(bid_prices)) if len(bid_prices) > 0 else 0.0,
                'ask_mean': float(np.mean(ask_prices)) if len(ask_prices) > 0 else 0.0,
                'ask_std': float(np.std(ask_prices)) if len(ask_prices) > 0 else 0.0
            }
            
        return self._cached_metrics['price_distribution']
        
    def _should_update_cache(self, metric: str) -> bool:
        """Проверить, нужно ли обновить кэш"""
        current_time = time.time()
        if metric not in self._cached_metrics or \
           current_time - self._cache_timestamp > self._cache_duration:
            self._cache_timestamp = current_time
            return True
        return False
        
    def to_dict(self) -> dict:
        """Преобразовать книгу ордеров в словарь"""
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp,
            'exchange': self.exchange,
            'bids': [(level.price, level.size) for level in self.bids],
            'asks': [(level.price, level.size) for level in self.asks],
            'depth': self.depth,
            'metrics': {
                'mid_price': self.get_mid_price(),
                'spread': self.get_spread(),
                'spread_percentage': self.get_spread_percentage(),
                'volume_imbalance': self.get_volume_imbalance(),
                'weighted_mid_price': self.get_weighted_mid_price(),
                'market_depth': self.calculate_market_depth()
            }
        }
        
    @classmethod
    def from_dict(cls, data: dict) -> 'OrderBook':
        """Создать книгу ордеров из словаря"""
        bids = [OrderBookLevel(price=p, size=s) for p, s in data['bids']]
        asks = [OrderBookLevel(price=p, size=s) for p, s in data['asks']]
        
        return cls(
            symbol=data['symbol'],
            timestamp=data['timestamp'],
            exchange=data.get('exchange', ''),
            bids=bids,
            asks=asks,
            depth=data.get('depth', 20)
        )
        
    def update(self, updates: dict):
        """Обновить книгу ордеров"""
        current_time = time.time()
        
        # Обновляем цены покупки
        if 'bids' in updates:
            new_bids = []
            for price, size in updates['bids']:
                if size > 0:
                    new_bids.append(OrderBookLevel(
                        price=price,
                        size=size,
                        timestamp=current_time
                    ))
            self.bids = sorted(new_bids, key=lambda x: x.price, reverse=True)[:self.depth]
            
        # Обновляем цены продажи
        if 'asks' in updates:
            new_asks = []
            for price, size in updates['asks']:
                if size > 0:
                    new_asks.append(OrderBookLevel(
                        price=price,
                        size=size,
                        timestamp=current_time
                    ))
            self.asks = sorted(new_asks, key=lambda x: x.price)[:self.depth]
            
        self.timestamp = current_time
        self._cached_metrics.clear()  # Сбрасываем кэш
        
    def is_valid(self) -> bool:
        """Проверить валидность книги ордеров"""
        if not self.bids or not self.asks:
            return False
            
        # Проверяем, что лучшая цена покупки меньше лучшей цены продажи
        if self.bids[0].price >= self.asks[0].price:
            return False
            
        # Проверяем сортировку
        for i in range(1, len(self.bids)):
            if self.bids[i].price > self.bids[i-1].price:
                return False
                
        for i in range(1, len(self.asks)):
            if self.asks[i].price < self.asks[i-1].price:
                return False
                
        return True
        
    def get_liquidity_profile(self, price_range_pct: float = 0.01) -> dict:
        """Получить профиль ликвидности"""
        mid_price = self.get_mid_price()
        price_range = mid_price * price_range_pct
        
        bid_liquidity = []
        ask_liquidity = []
        
        # Группируем ликвидность по ценовым уровням
        price_levels = np.linspace(
            mid_price - price_range,
            mid_price + price_range,
            20
        )
        
        for i in range(len(price_levels) - 1):
            price_low = price_levels[i]
            price_high = price_levels[i + 1]
            
            # Суммируем объемы в каждом ценовом диапазоне
            bid_volume = sum(level.size for level in self.bids
                           if price_low <= level.price < price_high)
            ask_volume = sum(level.size for level in self.asks
                           if price_low <= level.price < price_high)
                           
            bid_liquidity.append((price_low, bid_volume))
            ask_liquidity.append((price_low, ask_volume))
            
        return {
            'bid_liquidity': bid_liquidity,
            'ask_liquidity': ask_liquidity,
            'price_levels': price_levels.tolist()
        }
        
    def get_order_flow_imbalance(self, window_size: int = 10) -> float:
        """Рассчитать дисбаланс потока ордеров"""
        if len(self.bids) < window_size or len(self.asks) < window_size:
            return 0.0
            
        bid_pressure = sum(level.size for level in self.bids[:window_size])
        ask_pressure = sum(level.size for level in self.asks[:window_size])
        
        total_pressure = bid_pressure + ask_pressure
        if total_pressure == 0:
            return 0.0
            
        return (bid_pressure - ask_pressure) / total_pressure
        
    def estimate_execution_price(self, size: float, side: str) -> tuple[float, float]:
        """Оценить цену исполнения и проскальзывание"""
        if size <= 0:
            return 0.0, 0.0
            
        if side.lower() == 'buy':
            levels = self.asks
            base_price = self.asks[0].price
        else:
            levels = self.bids
            base_price = self.bids[0].price
            
        remaining_size = size
        weighted_price = 0.0
        
        for level in levels:
            if remaining_size <= 0:
                break
            executed_size = min(remaining_size, level.size)
            weighted_price += executed_size * level.price
            remaining_size -= executed_size
            
        if remaining_size > 0:
            return 0.0, 0.0
            
        avg_price = weighted_price / size
        slippage = abs(avg_price - base_price) / base_price
        
        return avg_price, slippage