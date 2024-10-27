import asyncio
import hmac
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
        self.ws_public_url = 'wss://stream-testnet.bybit.com/v5/public/spot' if self.testnet else 'wss://stream.bybit.com/v5/public/spot'
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
        if self.ws_public:
            await self.ws_public.close()
            self.ws_public = None
        
        if self.ws_private:
            await self.ws_private.close()
            self.ws_private = None
            
        await self._close_session()
        self.logger.info("Disconnected from Bybit")
        
    async def _ws_connect(self):
        """Установка WebSocket соединений с повторными попытками"""
        while self.reconnect_attempts < self.max_reconnect_attempts:
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0',
                    'Content-Type': 'application/json'
                }
                
                # Подключение к публичному WebSocket
                self.ws_public = await websockets.connect(
                    self.ws_public_url,
                    ping_interval=None,
                    ping_timeout=None,
                    extra_headers=headers,
                    max_size=2**23  # 8MB
                )
                
                # Только для приватного WebSocket
                if self.ws_private:
                    await self._ws_authenticate()
                
                self.reconnect_attempts = 0
                break
                
            except Exception as e:
                self.reconnect_attempts += 1
                self.logger.error(f"WebSocket connection attempt {self.reconnect_attempts} failed: {str(e)}")
                if self.reconnect_attempts >= self.max_reconnect_attempts:
                    raise
                await asyncio.sleep(2 ** self.reconnect_attempts)
        
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
            formatted_symbol = symbol.replace('-', '').upper()
            subscribe_message = {
                "op": "subscribe",
                "args": [
                    f"orderbook.25.{formatted_symbol}"
                ]
            }
            
            if self.ws_public:
                await self.ws_public.send(json.dumps(subscribe_message))
                self.logger.info(f"Subscribed to orderbook for {formatted_symbol}")
            else:
                self.logger.warning(f"WebSocket not connected, using REST API for {formatted_symbol}")
                asyncio.create_task(self._rest_orderbook_updates(formatted_symbol))
                
        except Exception as e:
            self.logger.error(f"Failed to subscribe to orderbook: {str(e)}")
            # Запускаем REST API обновления как fallback
            asyncio.create_task(self._rest_orderbook_updates(symbol))
                      
    async def _rest_orderbook_updates(self, symbol: str):
        """Получение обновлений книги ордеров через REST API"""
        while True:
            try:
                endpoint = f"/v5/market/orderbook"
                params = {
                    "category": self.category,
                    "symbol": symbol.replace('-', ''),
                    "limit": 25
                }
                response = await self._make_request('GET', endpoint, params)
                
                if response and response.get('result'):
                    data = response['result']
                    orderbook_data = {
                        'type': 'orderbook',
                        'exchange': 'bybit',
                        'symbol': symbol,
                        'timestamp': int(time.time() * 1000),
                        'bids': [[float(p), float(s)] for p, s in data.get('b', [])],
                        'asks': [[float(p), float(s)] for p, s in data.get('a', [])]
                    }
                    await self._handle_message(orderbook_data)
                    
            except Exception as e:
                self.logger.error(f"Error in REST orderbook update: {str(e)}")
                
            await asyncio.sleep(1)  # Обновление каждую секунду

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

    async def _ws_authenticate(self):
        """Аутентификация WebSocket соединения"""
        try:
            if not self.api_key or not self.api_secret:
                return
                
            timestamp = int(time.time() * 1000)
            param_str = f"{timestamp}GET/realtime"
            signature = self._generate_signature(param_str)
            
            auth_message = {
                "op": "auth",
                "args": [
                    self.api_key,
                    timestamp,
                    signature
                ]
            }
            
            await self.ws_private.send(json.dumps(auth_message))
            response = await self.ws_private.recv()
            auth_response = json.loads(response)
            
            if not auth_response.get('success'):
                raise Exception("WebSocket authentication failed")
                
            self.logger.info("WebSocket authentication successful")
            
        except Exception as e:
            self.logger.error(f"WebSocket authentication error: {str(e)}")
            raise
            
    def _generate_signature(self, param_str: str) -> str:
        """Генерация подписи для аутентификации"""
        return hmac.new(
            bytes(self.api_secret, encoding='utf8'),
            bytes(param_str, encoding='utf-8'),
            digestmod='sha256'
        ).hexdigest()

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