import pytest
import asyncio
from datetime import datetime
import json
from typing import List, Dict

from strategies.orderbook_imbalance import OrderBookImbalanceStrategy
from models.orderbook import OrderBook, OrderBookLevel

@pytest.fixture
def strategy():
    """Фикстура для создания стратегии"""
    config = {
        'min_imbalance_ratio': 3.0,
        'large_order_threshold': 100.0,
        'min_spread': 0.0005,
        'take_profit_pct': 0.002,
        'stop_loss_pct': 0.001
    }
    return OrderBookImbalanceStrategy(['BTC-USDT'], **config)

@pytest.fixture
def sample_orderbook():
    """Фикстура с тестовыми данными книги ордеров"""
    def create_orderbook(bids: List[List[float]], asks: List[List[float]]) -> OrderBook:
        return OrderBook(
            symbol='BTC-USDT',
            timestamp=datetime.now().timestamp(),
            bids=[OrderBookLevel(price=b[0], size=b[1]) for b in bids],
            asks=[OrderBookLevel(price=a[0], size=a[1]) for a in asks],
            exchange='test'
        )
    return create_orderbook

def test_basic_imbalance_detection(strategy, sample_orderbook):
    """Тест базового определения дисбаланса"""
    # Создаем книгу ордеров с явным дисбалансом
    orderbook = sample_orderbook(
        bids=[[50000, 300], [49900, 200]],  # Большой объем на покупку
        asks=[[50100, 50], [50200, 30]]      # Малый объем на продажу
    )
    
    strategy.update_orderbook('BTC-USDT', orderbook)
    signal = strategy.should_open_position('BTC-USDT')
    
    assert signal is not None
    assert signal['side'] == 'long'
    
def test_insufficient_imbalance(strategy, sample_orderbook):
    """Тест недостаточного дисбаланса"""
    orderbook = sample_orderbook(
        bids=[[50000, 100], [49900, 100]],
        asks=[[50100, 80], [50200, 80]]
    )
    
    strategy.update_orderbook('BTC-USDT', orderbook)
    signal = strategy.should_open_position('BTC-USDT')
    
    assert signal is None
    
def test_spread_filter(strategy, sample_orderbook):
    """Тест фильтра по спреду"""
    orderbook = sample_orderbook(
        bids=[[50000, 300], [49900, 200]],
        asks=[[50500, 50], [50600, 30]]  # Большой спред
    )
    
    strategy.update_orderbook('BTC-USDT', orderbook)
    signal = strategy.should_open_position('BTC-USDT')
    
    assert signal is None
    
def test_position_sizing(strategy, sample_orderbook):
    """Тест размера позиции"""
    orderbook = sample_orderbook(
        bids=[[50000, 300], [49900, 200]],
        asks=[[50100, 50], [50200, 30]]
    )
    
    strategy.update_orderbook('BTC-USDT', orderbook)
    signal = strategy.should_open_position('BTC-USDT')
    
    assert signal is not None
    assert 'size' in signal
    assert signal['size'] > 0

@pytest.mark.asyncio
async def test_multiple_updates(strategy, sample_orderbook):
    """Тест множественных обновлений книги ордеров"""
    orderbooks = [
        sample_orderbook(
            bids=[[50000, 100], [49900, 100]],
            asks=[[50100, 100], [50200, 100]]
        ),
        sample_orderbook(
            bids=[[50000, 300], [49900, 200]],
            asks=[[50100, 50], [50200, 30]]
        ),
        sample_orderbook(
            bids=[[50000, 50], [49900, 30]],
            asks=[[50100, 300], [50200, 200]]
        )
    ]
    
    signals = []
    for ob in orderbooks:
        strategy.update_orderbook('BTC-USDT', ob)
        signal = strategy.should_open_position('BTC-USDT')
        signals.append(signal)
        await asyncio.sleep(0.1)
        
    assert any(s is not None for s in signals)
    assert len([s for s in signals if s is not None]) <= len(orderbooks)