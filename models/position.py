from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
import time

@dataclass
class Position:
    symbol: str
    side: str  # 'long' или 'short'
    entry_price: float
    size: float
    take_profit: float
    stop_loss: float
    strategy: str
    exchange: str
    
    # Дополнительные параметры
    entry_time: float = field(default_factory=lambda: time.time())
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    status: str = 'open'
    
    # История цен для анализа
    price_history: List[tuple[float, float]] = field(default_factory=list)
    
    # Параметры исполнения
    entry_slippage: float = 0.0
    execution_time: float = 0.0
    partial_fills: List[tuple[float, float]] = field(default_factory=list)
    
    # Метаданные
    tags: List[str] = field(default_factory=list)
    notes: str = ''
    
    def update_price(self, new_price: float):
        """Обновить текущую цену и историю цен"""
        self.current_price = new_price
        self.price_history.append((time.time(), new_price))
        
        # Обновить unrealized PnL
        if self.side == 'long':
            self.unrealized_pnl = (new_price - self.entry_price) * self.size
        else:
            self.unrealized_pnl = (self.entry_price - new_price) * self.size
            
    def add_partial_fill(self, price: float, size: float):
        """Добавить частичное исполнение"""
        self.partial_fills.append((price, size))
        
    def calculate_average_entry(self) -> float:
        """Рассчитать среднюю цену входа с учетом частичных исполнений"""
        if not self.partial_fills:
            return self.entry_price
            
        total_size = sum(size for _, size in self.partial_fills)
        if total_size == 0:
            return self.entry_price
            
        weighted_sum = sum(price * size for price, size in self.partial_fills)
        return weighted_sum / total_size
        
    def get_duration(self) -> float:
        """Получить длительность позиции в секундах"""
        return time.time() - self.entry_time
        
    def get_max_adverse_excursion(self) -> float:
        """Получить максимальное неблагоприятное отклонение"""
        if not self.price_history:
            return 0.0
            
        prices = [price for _, price in self.price_history]
        if self.side == 'long':
            return self.entry_price - min(prices)
        else:
            return max(prices) - self.entry_price
            
    def get_max_favorable_excursion(self) -> float:
        """Получить максимальное благоприятное отклонение"""
        if not self.price_history:
            return 0.0
            
        prices = [price for _, price in self.price_history]
        if self.side == 'long':
            return max(prices) - self.entry_price
        else:
            return self.entry_price - min(prices)
            
    def to_dict(self) -> dict:
        """Преобразовать позицию в словарь для сериализации"""
        return {
            'symbol': self.symbol,
            'side': self.side,
            'entry_price': self.entry_price,
            'current_price': self.current_price,
            'size': self.size,
            'take_profit': self.take_profit,
            'stop_loss': self.stop_loss,
            'strategy': self.strategy,
            'exchange': self.exchange,
            'entry_time': self.entry_time,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'status': self.status,
            'duration': self.get_duration(),
            'max_adverse_excursion': self.get_max_adverse_excursion(),
            'max_favorable_excursion': self.get_max_favorable_excursion(),
            'entry_slippage': self.entry_slippage,
            'execution_time': self.execution_time,
            'partial_fills': self.partial_fills,
            'tags': self.tags,
            'notes': self.notes
        }
        
    @classmethod
    def from_dict(cls, data: dict) -> 'Position':
        """Создать позицию из словаря"""
        return cls(
            symbol=data['symbol'],
            side=data['side'],
            entry_price=data['entry_price'],
            size=data['size'],
            take_profit=data['take_profit'],
            stop_loss=data['stop_loss'],
            strategy=data['strategy'],
            exchange=data['exchange'],
            entry_time=data.get('entry_time', time.time()),
            current_price=data.get('current_price', data['entry_price']),
            unrealized_pnl=data.get('unrealized_pnl', 0.0),
            realized_pnl=data.get('realized_pnl', 0.0),
            status=data.get('status', 'open'),
            entry_slippage=data.get('entry_slippage', 0.0),
            execution_time=data.get('execution_time', 0.0),
            tags=data.get('tags', []),
            notes=data.get('notes', '')
        )