from typing import List, Optional, Dict
import numpy as np
from datetime import datetime
import pandas as pd

class MarketUtils:
    @staticmethod
    def calculate_indicators(prices: List[float], window: int = 20) -> Dict:
        """Расчет технических индикаторов"""
        if len(prices) < window:
            return {}
            
        prices_array = np.array(prices)
        
        # SMA
        sma = np.mean(prices_array[-window:])
        
        # EMA
        ema = pd.Series(prices).ewm(span=window).mean().iloc[-1]
        
        # Bollinger Bands
        std = np.std(prices_array[-window:])
        upper_band = sma + (std * 2)
        lower_band = sma - (std * 2)
        
        # RSI
        diff = np.diff(prices_array)
        gains = np.where(diff > 0, diff, 0)
        losses = np.where(diff < 0, -diff, 0)
        avg_gain = np.mean(gains[-window:])
        avg_loss = np.mean(losses[-window:])
        rs = avg_gain / avg_loss if avg_loss != 0 else 0
        rsi = 100 - (100 / (1 + rs))
        
        return {
            'sma': sma,
            'ema': ema,
            'upper_band': upper_band,
            'lower_band': lower_band,
            'rsi': rsi
        }
        
    @staticmethod
    def detect_patterns(candles: List[Dict]) -> List[str]:
        """Определение паттернов свечей"""
        patterns = []
        if len(candles) < 3:
            return patterns
            
        # Doji
        last_candle = candles[-1]
        if abs(last_candle['open'] - last_candle['close']) < \
           (last_candle['high'] - last_candle['low']) * 0.1:
            patterns.append('doji')
            
        # Hammer
        if last_candle['low'] < min(last_candle['open'], last_candle['close']) and \
           (last_candle['high'] - max(last_candle['open'], last_candle['close'])) < \
           (min(last_candle['open'], last_candle['close']) - last_candle['low']) * 0.3:
            patterns.append('hammer')
            
        # Engulfing
        prev_candle = candles[-2]
        if last_candle['open'] > prev_candle['close'] and \
           last_candle['close'] < prev_candle['open']:
            patterns.append('bearish_engulfing')
        elif last_candle['open'] < prev_candle['close'] and \
             last_candle['close'] > prev_candle['open']:
            patterns.append('bullish_engulfing')
            
        return patterns
        
    @staticmethod
    def calculate_support_resistance(
        prices: List[float],
        window: int = 20,
        threshold: float = 0.02
    ) -> tuple:
        """Расчет уровней поддержки и сопротивления"""
        if len(prices) < window:
            return [], []
            
        prices_array = np.array(prices)
        highs = []
        lows = []
        
        for i in range(window, len(prices_array)-window):
            if all(prices_array[i] > prices_array[i-window:i]) and \
               all(prices_array[i] > prices_array[i+1:i+window]):
                highs.append(prices_array[i])
            if all(prices_array[i] < prices_array[i-window:i]) and \
               all(prices_array[i] < prices_array[i+1:i+window]):
                lows.append(prices_array[i])
                
        # Группировка близких уровней
        support = []
        resistance = []
        
        for high in sorted(highs, reverse=True):
            if not resistance or \
               abs(high - resistance[-1]) / resistance[-1] > threshold:
                resistance.append(high)
                
        for low in sorted(lows):
            if not support or \
               abs(low - support[-1]) / support[-1] > threshold:
                support.append(low)
                
        return support, resistance
        
    @staticmethod
    def calculate_pivot_points(high: float, low: float, close: float) -> Dict:
        """Расчет точек разворота"""
        pivot = (high + low + close) / 3
        r1 = 2 * pivot - low
        r2 = pivot + (high - low)
        r3 = high + 2 * (pivot - low)
        s1 = 2 * pivot - high
        s2 = pivot - (high - low)
        s3 = low - 2 * (high - pivot)
        
        return {
            'pivot': pivot,
            'r1': r1,
            'r2': r2,
            'r3': r3,
            's1': s1,
            's2': s2,
            's3': s3
        }