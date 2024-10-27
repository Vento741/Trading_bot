from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
import numpy as np

@dataclass
class MarketData:
    symbol: str
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float
    exchange: str
    timeframe: str
    
    # Дополнительные данные
    trades_count: Optional[int] = None
    vwap: Optional[float] = None
    buy_volume: Optional[float] = None
    sell_volume: Optional[float] = None
    
    def calculate_returns(self) -> float:
        """Расчет доходности"""
        return (self.close - self.open) / self.open
        
    def calculate_range(self) -> float:
        """Расчет диапазона цен"""
        return self.high - self.low
        
    def calculate_volume_imbalance(self) -> float:
        """Расчет дисбаланса объемов"""
        if self.buy_volume is None or self.sell_volume is None:
            return 0.0
        total_volume = self.buy_volume + self.sell_volume
        if total_volume == 0:
            return 0.0
        return (self.buy_volume - self.sell_volume) / total_volume

@dataclass
class Candle:
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    @property
    def body_size(self) -> float:
        """Размер тела свечи"""
        return abs(self.close - self.open)
        
    @property
    def upper_wick(self) -> float:
        """Размер верхней тени"""
        return self.high - max(self.open, self.close)
        
    @property
    def lower_wick(self) -> float:
        """Размер нижней тени"""
        return min(self.open, self.close) - self.low
        
    @property
    def is_bullish(self) -> bool:
        """Является ли свеча бычьей"""
        return self.close > self.open

@dataclass
class MarketDataAggregator:
    symbol: str
    timeframe: str
    max_candles: int = 1000
    candles: List[Candle] = field(default_factory=list)
    
    def add_candle(self, candle: Candle):
        """Добавление новой свечи"""
        self.candles.append(candle)
        if len(self.candles) > self.max_candles:
            self.candles.pop(0)
            
    def get_ohlcv(self) -> tuple:
        """Получение OHLCV данных"""
        if not self.candles:
            return None
            
        return (
            [c.open for c in self.candles],
            [c.high for c in self.candles],
            [c.low for c in self.candles],
            [c.close for c in self.candles],
            [c.volume for c in self.candles]
        )
        
    def calculate_vwap(self) -> float:
        """Расчет VWAP"""
        if not self.candles:
            return 0.0
            
        cumulative_pv = 0
        cumulative_volume = 0
        
        for candle in self.candles:
            typical_price = (candle.high + candle.low + candle.close) / 3
            cumulative_pv += typical_price * candle.volume
            cumulative_volume += candle.volume
            
        return cumulative_pv / cumulative_volume if cumulative_volume > 0 else 0.0
        
    def calculate_volatility(self, window: int = 20) -> float:
        """Расчет волатильности"""
        if len(self.candles) < window:
            return 0.0
            
        closes = [c.close for c in self.candles[-window:]]
        returns = np.diff(np.log(closes))
        return float(np.std(returns) * np.sqrt(252))