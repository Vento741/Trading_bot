from typing import Dict, List, Optional
from abc import ABC, abstractmethod
import asyncio
import time
import hmac
import hashlib
import json
import aiohttp
import websockets
from utils.logger import setup_logger

class BaseExchange(ABC):
    def __init__(self, config: Dict):
        self.config = config
        self.api_key = config['api_key']
        self.api_secret = config['api_secret']
        self.testnet = config.get('testnet', False)
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.callbacks = []
        
        self.logger = setup_logger(f"exchange.{self.__class__.__name__.lower()}")
        
    @abstractmethod
    async def connect(self):
        """Установить соединение с биржей"""
        pass
        
    @abstractmethod
    async def disconnect(self):
        """Закрыть соединение с биржей"""
        pass
        
    @abstractmethod
    async def subscribe_orderbook(self, symbol: str):
        """Подписаться на обновления книги ордеров"""
        pass
        
    @abstractmethod
    async def place_order(self, symbol: str, side: str, order_type: str,
                         size: float, price: Optional[float] = None) -> Dict:
        """Разместить ордер"""
        pass
        
    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str):
        """Отменить ордер"""
        pass
        
    @abstractmethod
    async def get_position(self, symbol: str) -> Dict:
        """Получить информацию о позиции"""
        pass
        
    @abstractmethod
    async def get_balance(self) -> Dict:
        """Получить баланс аккаунта"""
        pass
        
    @abstractmethod
    def get_price(self, symbol: str) -> float:
        """Получить текущую цену"""
        pass
        
    async def _init_session(self):
        """Инициализировать HTTP сессию"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
    async def _close_session(self):
        """Закрыть HTTP сессию"""
        if self.session:
            await self.session.close()
            self.session = None
            
    def _generate_signature(self, params: Dict, timestamp: int) -> str:
        """Сгенерировать подпись для запроса"""
        payload = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        payload = f"{timestamp}{self.api_key}{payload}"
        return hmac.new(
            self.api_secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
    async def _make_request(self, method: str, endpoint: str, 
                          params: Optional[Dict] = None,
                          signed: bool = False) -> Dict:
        """Выполнить HTTP запрос к бирже"""
        if not self.session:
            await self._init_session()
            
        url = self._get_url(endpoint)
        headers = {}
        
        if signed:
            timestamp = int(time.time() * 1000)
            signature = self._generate_signature(params or {}, timestamp)
            headers.update({
                'api-key': self.api_key,
                'api-signature': signature,
                'api-timestamp': str(timestamp)
            })
            
        try:
            if method == 'GET':
                response = await self.session.get(url, params=params, headers=headers)
            elif method == 'POST':
                response = await self.session.post(url, json=params, headers=headers)
            elif method == 'DELETE':
                response = await self.session.delete(url, params=params, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            response_data = await response.json()
            
            if response.status != 200:
                raise Exception(f"Request failed: {response_data}")
                
            return response_data
            
        except Exception as e:
            self.logger.error(f"Request error: {str(e)}")
            raise
            
    def add_callback(self, callback):
        """Добавить callback для обработки данных"""
        self.callbacks.append(callback)
        
    async def _handle_message(self, msg: Dict):
        """Обработать входящее сообщение"""
        for callback in self.callbacks:
            try:
                await callback(msg)
            except Exception as e:
                self.logger.error(f"Callback error: {str(e)}")
                
    @abstractmethod
    def _get_url(self, endpoint: str) -> str:
        """Получить полный URL для запроса"""
        pass
        
    @abstractmethod
    async def _ws_connect(self):
        """Установить WebSocket соединение"""
        pass
        
    @abstractmethod
    async def _ws_subscribe(self, channels: List[str]):
        """Подписаться на WebSocket каналы"""
        pass
        
    async def _ws_keep_alive(self):
        """Поддержание WebSocket соединения"""
        while True:
            try:
                if self.ws:
                    await self.ws.ping()
                await asyncio.sleep(30)
            except Exception as e:
                self.logger.error(f"WebSocket keepalive error: {str(e)}")
                await self._ws_connect()
                
    async def _ws_message_handler(self):
        """Обработка WebSocket сообщений"""
        while True:
            try:
                if not self.ws:
                    await self._ws_connect()
                    
                message = await self.ws.recv()
                data = json.loads(message)
                await self._handle_message(data)
                
            except websockets.ConnectionClosed:
                self.logger.warning("WebSocket connection closed")
                await asyncio.sleep(1)
                await self._ws_connect()
            except Exception as e:
                self.logger.error(f"WebSocket message handler error: {str(e)}")
                await asyncio.sleep(1)
                
    def _process_orderbook(self, data: Dict) -> Dict:
        """Обработать данные книги ордеров"""
        return {
            'type': 'orderbook',
            'exchange': self.__class__.__name__.lower(),
            'symbol': data['symbol'],
            'timestamp': data['timestamp'],
            'bids': data['bids'],
            'asks': data['asks']
        }
        
    async def _process_error(self, error: Exception):
        """Обработать ошибку"""
        self.logger.error(f"Exchange error: {str(error)}")
        
        # Notify callbacks about error
        error_message = {
            'type': 'error',
            'exchange': self.__class__.__name__.lower(),
            'message': str(error),
            'timestamp': int(time.time() * 1000)
        }
        
        await self._handle_message(error_message)