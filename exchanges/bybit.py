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
        self.ws_public_url = 'wss://stream-testnet.bybit.com/v5/public' if self.testnet else 'wss://stream.bybit.com/v5/public'
        self.ws_private_url = 'wss://stream-testnet.bybit.com/v5/private' if self.testnet else 'wss://stream.bybit.com/v5/private'
        
        # Категория для Unified Account
        self.category = config.get('category', 'spot')
        
        # Добавляем переменные для отслеживания состояния подключения
        self.ws_public = None
        self.ws_private = None
        self.last_ping_time = 0
        self.ping_interval = 20  # seconds
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        
    def _get_url(self, endpoint: str) -> str:
        return f"{self.base_url}{endpoint}"
        
    async def connect(self):
        """Установить соединение с биржей"""
        await self._init_session()
        
        # Инициализация WebSocket подключений
        try:
            await self._ws_connect()
            # Запуск обработчиков в отдельных задачах
            asyncio.create_task(self._ws_keepalive())
            asyncio.create_task(self._ws_message_handler())
            self.logger.info("Connected to Bybit WebSocket")
        except Exception as e:
            self.logger.warning(f"WebSocket connection failed: {str(e)}. Trading will continue with REST API.")
            # Продолжаем работу даже без WebSocket
            pass
        
    async def disconnect(self):
        """Закрыть соединение с биржей"""
        if self.ws:
            await self.ws.close()
            self.ws = None
            
        await self._close_session()
        self.logger.info("Disconnected from Bybit")
        
    async def _ws_connect(self):
        """Установка WebSocket соединений с повторными попытками"""
        while self.reconnect_attempts < self.max_reconnect_attempts:
            try:
                # Public WebSocket
                self.ws_public = await websockets.connect(
                    self.ws_public_url,
                    ping_interval=None,  # Отключаем автоматический ping
                    ping_timeout=None
                )
                
                # Private WebSocket (если нужен)
                if self.api_key and self.api_secret:
                    self.ws_private = await websockets.connect(
                        self.ws_private_url,
                        ping_interval=None,
                        ping_timeout=None
                    )
                    await self._ws_authenticate()
                
                self.reconnect_attempts = 0  # Сброс счетчика после успешного подключения
                break
                
            except Exception as e:
                self.reconnect_attempts += 1
                self.logger.error(f"WebSocket connection attempt {self.reconnect_attempts} failed: {str(e)}")
                if self.reconnect_attempts >= self.max_reconnect_attempts:
                    raise
                await asyncio.sleep(2 ** self.reconnect_attempts)  # Exponential backoff
        
    async def _ws_keepalive(self):
        """Поддержание WebSocket соединения"""
        while True:
            try:
                current_time = time.time()
                if current_time - self.last_ping_time > self.ping_interval:
                    if self.ws_public:
                        await self.ws_public.ping()
                    if self.ws_private:
                        await self.ws_private.ping()
                    self.last_ping_time = current_time
                    
                await asyncio.sleep(1)
            except Exception as e:
                self.logger.error(f"WebSocket keepalive error: {str(e)}")
                try:
                    await self._ws_connect()
                except:
                    await asyncio.sleep(5)

    async def subscribe_orderbook(self, symbol: str):
        """Подписка на обновления книги ордеров"""
        try:
            channel = f"orderbook.25.{symbol}"
            subscribe_message = {
                "op": "subscribe",
                "args": [
                    {
                        "category": self.category,
                        "symbol": symbol,
                        "channel": channel
                    }
                ]
            }
            if self.ws_public:
                await self.ws_public.send(json.dumps(subscribe_message))
                self.logger.info(f"Subscribed to orderbook for {symbol}")
            else:
                self.logger.warning("WebSocket not connected, orderbook updates will not be received")
        except Exception as e:
            self.logger.error(f"Failed to subscribe to orderbook: {str(e)}")
        
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
        
    async def _ws_message_handler(self):
        """Обработка WebSocket сообщений"""
        while True:
            try:
                if self.ws_public:
                    message = await self.ws_public.recv()
                    data = json.loads(message)
                    await self._handle_message(data)
            except websockets.ConnectionClosed:
                self.logger.warning("WebSocket connection closed")
                try:
                    await self._ws_connect()
                except:
                    await asyncio.sleep(5)
            except Exception as e:
                self.logger.error(f"WebSocket message handler error: {str(e)}")
                await asyncio.sleep(1)

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