import pytest
import asyncio
from typing import Dict
import json
from datetime import datetime

from exchanges.base import BaseExchange
from models.orderbook import OrderBook

class MockExchange(BaseExchange):
    """Мок-класс биржи для тестирования"""
    def __init__(self, config: Dict):
        super().__init__(config)
        self.connected = False
        self.orders = []
        
    async def connect(self):
        self.connected = True
        
    async def disconnect(self):
        self.connected = False
        
    async def subscribe_orderbook(self, symbol: str):
        pass
        
    async def place_order(self, symbol: str, side: str, order_type: str,
                         size: float, price: float = None) -> Dict:
        order = {
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'size': size,
            'price': price,
            'status': 'filled'
        }
        self.orders.append(order)
        return order
        
    async def cancel_order(self, symbol: str, order_id: str):
        pass
        
    async def get_position(self, symbol: str) -> Dict:
        return {'symbol': symbol, 'size': 0, 'entry_price': 0}
        
    async def get_balance(self) -> Dict:
        return {'USDT': {'available': 10000, 'total': 10000}}
        
    def get_price(self, symbol: str) -> float:
        return 50000.0

@pytest.fixture
async def exchange():
    """Фикстура для создания тестовой биржи"""
    config = {
        'api_key': 'test',
        'api_secret': 'test',
        'testnet': True
    }
    exchange = MockExchange(config)
    await exchange.connect()
    yield exchange
    await exchange.disconnect()

@pytest.mark.asyncio
async def test_connection(exchange):
    """Тест подключения к бирже"""
    assert exchange.connected
    await exchange.disconnect()
    assert not exchange.connected

@pytest.mark.asyncio
async def test_order_placement(exchange):
    """Тест размещения ордера"""
    order = await exchange.place_order(
        symbol='BTC-USDT',
        side='buy',
        order_type='limit',
        size=1.0,
        price=50000.0
    )
    
    assert order['symbol'] == 'BTC-USDT'
    assert order['side'] == 'buy'
    assert order['status'] == 'filled'

@pytest.mark.asyncio
async def test_balance_query(exchange):
    """Тест запроса баланса"""
    balance = await exchange.get_balance()
    assert 'USDT' in balance
    assert balance['USDT']['available'] > 0

@pytest.mark.asyncio
async def test_position_query(exchange):
    """Тест запроса позиции"""
    position = await exchange.get_position('BTC-USDT')
    assert position['symbol'] == 'BTC-USDT'
    assert 'size' in position

@pytest.mark.asyncio
async def test_error_handling(exchange):
    """Тест обработки ошибок"""
    with pytest.raises(Exception):
        await exchange.place_order(
            symbol='INVALID-PAIR',
            side='buy',
            order_type='limit',
            size=-1.0,
            price=50000.0
        )