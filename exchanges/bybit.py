import asyncio
import json
import time
from typing import Dict, List, Optional
import websockets
from .base import BaseExchange

class BybitExchange(BaseExchange):
    def __init__(self, config: Dict):
        super().__init__(config)
        
        # API endpoints для Unified Account
        self.base_url = 'https://api-testnet.bybit.com' if self.testnet else 'https://api.bybit.com'
        self.ws_url = 'wss://stream-testnet.bybit.com/v5' if self.testnet else 'wss://stream.bybit.com/v5'
        
        # Категория для Unified Account
        self.category = 'spot'  # или 'linear' для фьючерсов

        # Local cache
        self.orderbook_cache = {}
        self.position_cache = {}
        self.order_cache = {}
        
    def _get_url(self, endpoint: str) -> str:
        return f"{self.base_url}{endpoint}"
        
    async def connect(self):
        """Установить соединение с биржей"""
        await self._init_session()
        await self._ws_connect()
        
        # Start WebSocket handlers
        asyncio.create_task(self._ws_message_handler())
        asyncio.create_task(self._ws_keep_alive())
        
        self.logger.info("Connected to Bybit")
        
    async def disconnect(self):
        """Закрыть соединение с биржей"""
        if self.ws:
            await self.ws.close()
            self.ws = None
            
        await self._close_session()
        self.logger.info("Disconnected from Bybit")
        
    async def _ws_connect(self):
        """Установить WebSocket соединение"""
        self.ws = await websockets.connect(self.ws_url)
        
    async def subscribe_orderbook(self, symbol: str):
        """Подписаться на обновления книги ордеров"""
        channel = f"orderbook.25.{symbol}"
        await self._ws_subscribe([channel])
        
    async def _ws_subscribe(self, channels: List[str]):
        """Подписка на WebSocket каналы для Unified Account"""
        subscribe_message = {
            "op": "subscribe",
            "args": [
                {
                    "category": self.category,
                    "topic": channel,
                }
                for channel in channels
            ]
        }
        await self.ws.send(json.dumps(subscribe_message))
        
    async def place_order(self, symbol: str, side: str, order_type: str,
                         size: float, price: Optional[float] = None) -> Dict:
        """Размещение ордера через Unified Trading Account API"""
        endpoint = '/v5/order/create'
        
        params = {
            'category': self.category,
            'symbol': symbol,
            'side': side.upper(),
            'orderType': order_type.upper(),
            'qty': str(size),
            'timeInForce': 'GTC'
        }
        
        if price:
            params['price'] = str(price)
            
        response = await self._make_request('POST', endpoint, params, signed=True)
        
        if response.get('retCode') == 0:
            order_id = response['result']['orderId']
            self.order_cache[order_id] = {
                'symbol': symbol,
                'side': side,
                'size': size,
                'price': price,
                'status': response['result']['orderStatus']
            }
            return self.order_cache[order_id]
        else:
            raise Exception(f"Order placement failed: {response}")
            
    async def cancel_order(self, symbol: str, order_id: str):
        """Отменить ордер"""
        endpoint = '/v2/private/order/cancel'
        params = {
            'symbol': symbol,
            'order_id': order_id
        }
        
        response = await self._make_request('POST', endpoint, params, signed=True)
        
        if 'ret_code' in response and response['ret_code'] == 0:
            if order_id in self.order_cache:
                del self.order_cache[order_id]
        else:
            raise Exception(f"Order cancellation failed: {response}")
            
    async def get_position(self, symbol: str) -> Dict:
        """Получение позиции через Unified Account API"""
        endpoint = '/v5/position/list'
        params = {
            'category': self.category,
            'symbol': symbol
        }
        
        response = await self._make_request('GET', endpoint, params, signed=True)
        
        if response.get('retCode') == 0:
            positions = response['result']['list']
            if positions:
                position = positions[0]
                self.position_cache[symbol] = {
                    'size': float(position['size']),
                    'entry_price': float(position['avgPrice']),
                    'leverage': float(position['leverage']),
                    'liquidation_price': float(position.get('liqPrice', 0)),
                    'unrealized_pnl': float(position['unrealisedPnl'])
                }
                return self.position_cache[symbol]
        return {'size': 0, 'entry_price': 0}
            
    async def get_balance(self) -> Dict:
        """Получить баланс аккаунта"""
        endpoint = '/v2/private/wallet/balance'
        response = await self._make_request('GET', endpoint, signed=True)
        
        if 'ret_code' in response and response['ret_code'] == 0:
            return {
                currency: {
                    'available': float(data['available_balance']),
                    'total': float(data['wallet_balance'])
                }
                for currency, data in response['result'].items()
            }
        else:
            raise Exception(f"Failed to get balance: {response}")
            
    def get_price(self, symbol: str) -> float:
        """Получить текущую цену"""
        if symbol in self.orderbook_cache:
            orderbook = self.orderbook_cache[symbol]
            if orderbook['bids'] and orderbook['asks']:
                return (orderbook['bids'][0][0] + orderbook['asks'][0][0]) / 2
        return 0.0
        
    async def _handle_message(self, message: Dict):
        """Обработать входящее WebSocket сообщение"""
        if 'topic' in message and message['topic'].startswith('orderbook'):
            symbol = message['topic'].split('.')[-1]
            data = message['data']
            
            # Update local orderbook cache
            self.orderbook_cache[symbol] = {
                'timestamp': data['timestamp'],
                'bids': [[float(price), float(size)] for price, size in data['bids']],
                'asks': [[float(price), float(size)] for price, size in data['asks']]
            }
            
            # Format and forward the orderbook data
            orderbook_data = self._process_orderbook({
                'symbol': symbol,
                'timestamp': data['timestamp'],
                'bids': self.orderbook_cache[symbol]['bids'],
                'asks': self.orderbook_cache[symbol]['asks']
            })
            
            await super()._handle_message(orderbook_data)
            
        elif 'topic' in message and message['topic'].startswith('trade'):
            # Process trade data if needed
            pass
            
    async def _maintain_orderbook(self, symbol: str):
        """Поддерживать актуальность книги ордеров"""
        while True:
            try:
                if symbol not in self.orderbook_cache or \
                   time.time() - self.orderbook_cache[symbol]['timestamp'] > 30:
                    # Переподписаться на книгу ордеров
                    await self.subscribe_orderbook(symbol)
                await asyncio.sleep(30)
            except Exception as e:
                self.logger.error(f"Orderbook maintenance error: {str(e)}")
                await asyncio.sleep(1)