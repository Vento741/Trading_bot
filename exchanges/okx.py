import asyncio
import json
import time
from typing import Dict, List, Optional
import websockets
import base64
import hmac
from .base import BaseExchange

class OKXExchange(BaseExchange):
    def __init__(self, config: Dict):
        super().__init__(config)
        
        # API endpoints
        self.base_url = 'https://www.okx.com' if not self.testnet else 'https://testnet.okx.com'
        self.ws_url = 'wss://ws.okx.com:8443/ws/v5/public' if not self.testnet else 'wss://wspap.okx.com:8443/ws/v5/public'
        self.ws_private_url = 'wss://ws.okx.com:8443/ws/v5/private' if not self.testnet else 'wss://wspap.okx.com:8443/ws/v5/private'
        
        # Дополнительные параметры
        self.passphrase = config['passphrase']
        
        # Локальный кеш
        self.orderbook_cache = {}
        self.position_cache = {}
        self.order_cache = {}
        
        # WebSocket connections
        self.ws_public = None
        self.ws_private = None
        
    def _get_url(self, endpoint: str) -> str:
        return f"{self.base_url}{endpoint}"
        
    def _generate_signature(self, timestamp: str, method: str, 
                          request_path: str, body: str = '') -> str:
        """Generate signature for API request"""
        message = timestamp + method + request_path + body
        mac = hmac.new(
            bytes(self.api_secret, encoding='utf8'),
            bytes(message, encoding='utf-8'),
            digestmod='sha256'
        )
        return base64.b64encode(mac.digest()).decode()
        
    async def connect(self):
        """Establish connection with exchange"""
        await self._init_session()
        await self._ws_connect()
        
        # Start WebSocket handlers
        asyncio.create_task(self._ws_message_handler())
        asyncio.create_task(self._ws_keep_alive())
        
        self.logger.info("Connected to OKX")
        
    async def disconnect(self):
        """Close connection with exchange"""
        if self.ws_public:
            await self.ws_public.close()
            self.ws_public = None
            
        if self.ws_private:
            await self.ws_private.close()
            self.ws_private = None
            
        await self._close_session()
        self.logger.info("Disconnected from OKX")
        
    async def _ws_connect(self):
        """Establish WebSocket connections"""
        # Connect to public WebSocket
        self.ws_public = await websockets.connect(self.ws_url)
        
        # Connect to private WebSocket with authentication
        self.ws_private = await websockets.connect(self.ws_private_url)
        await self._ws_auth()
        
    async def _ws_auth(self):
        """Authenticate WebSocket connection"""
        timestamp = str(int(time.time()))
        signature = self._generate_signature(timestamp, 'GET', '/users/self/verify')
        
        auth_message = {
            "op": "login",
            "args": [{
                "apiKey": self.api_key,
                "passphrase": self.passphrase,
                "timestamp": timestamp,
                "sign": signature
            }]
        }
        
        await self.ws_private.send(json.dumps(auth_message))
        response = await self.ws_private.recv()
        auth_response = json.loads(response)
        
        if not auth_response.get('success'):
            raise Exception("WebSocket authentication failed")
            
    async def subscribe_orderbook(self, symbol: str):
        """Subscribe to orderbook updates"""
        channel = f"books.{symbol}"
        await self._ws_subscribe([channel])
        
    async def _ws_subscribe(self, channels: List[str]):
        """Subscribe to WebSocket channels"""
        subscribe_message = {
            "op": "subscribe",
            "args": channels
        }
        await self.ws_public.send(json.dumps(subscribe_message))
        
    async def place_order(self, symbol: str, side: str, order_type: str,
                         size: float, price: Optional[float] = None) -> Dict:
        """Place new order"""
        endpoint = '/api/v5/trade/order'
        params = {
            'instId': symbol,
            'tdMode': 'cross',  # cross margin mode
            'side': side.lower(),
            'ordType': 'limit' if price else 'market',
            'sz': str(size)
        }
        
        if price:
            params['px'] = str(price)
            
        response = await self._make_request('POST', endpoint, params, signed=True)
        
        if response['code'] == '0':
            order_id = response['data'][0]['ordId']
            self.order_cache[order_id] = {
                'symbol': symbol,
                'side': side,
                'size': size,
                'price': price,
                'status': response['data'][0]['state']
            }
            return self.order_cache[order_id]
        else:
            raise Exception(f"Order placement failed: {response}")
            
    async def cancel_order(self, symbol: str, order_id: str):
        """Cancel existing order"""
        endpoint = '/api/v5/trade/cancel-order'
        params = {
            'instId': symbol,
            'ordId': order_id
        }
        
        response = await self._make_request('POST', endpoint, params, signed=True)
        
        if response['code'] != '0':
            raise Exception(f"Order cancellation failed: {response}")
            
        if order_id in self.order_cache:
            del self.order_cache[order_id]
            
    async def get_position(self, symbol: str) -> Dict:
        """Get position information"""
        endpoint = '/api/v5/account/positions'
        params = {'instId': symbol}
        
        response = await self._make_request('GET', endpoint, params, signed=True)
        
        if response['code'] == '0':
            for position in response['data']:
                if position['instId'] == symbol:
                    position_data = {
                        'size': float(position['pos']),
                        'entry_price': float(position['avgPx']),
                        'leverage': float(position['lever']),
                        'liquidation_price': float(position['liqPx']),
                        'unrealized_pnl': float(position['upl']),
                        'margin_ratio': float(position['mgnRatio'])
                    }
                    self.position_cache[symbol] = position_data
                    return position_data
                    
            return {'size': 0.0, 'entry_price': 0.0}
        else:
            raise Exception(f"Failed to get position: {response}")
            
    async def get_balance(self) -> Dict:
        """Get account balance"""
        endpoint = '/api/v5/account/balance'
        response = await self._make_request('GET', endpoint, signed=True)
        
        if response['code'] == '0':
            balances = {}
            for currency in response['data'][0]['details']:
                balances[currency['ccy']] = {
                    'available': float(currency['availEq']),
                    'total': float(currency['eq'])
                }
            return balances
        else:
            raise Exception(f"Failed to get balance: {response}")
            
    def get_price(self, symbol: str) -> float:
        """Get current price"""
        if symbol in self.orderbook_cache:
            orderbook = self.orderbook_cache[symbol]
            if orderbook['bids'] and orderbook['asks']:
                return (orderbook['bids'][0][0] + orderbook['asks'][0][0]) / 2
        return 0.0
        
    async def _handle_message(self, message: Dict):
        """Handle incoming WebSocket message"""
        try:
            if 'arg' in message and 'channel' in message['arg']:
                channel = message['arg']['channel']
                
                if channel == 'books':
                    symbol = message['arg']['instId']
                    if 'data' in message:
                        data = message['data'][0]
                        
                        # Update local orderbook cache
                        self.orderbook_cache[symbol] = {
                            'timestamp': int(data['ts']),
                            'bids': [[float(price), float(size)] for price, size in data['bids']],
                            'asks': [[float(price), float(size)] for price, size in data['asks']]
                        }
                        
                        # Format and forward the orderbook data
                        orderbook_data = self._process_orderbook({
                            'symbol': symbol,
                            'timestamp': int(data['ts']),
                            'bids': self.orderbook_cache[symbol]['bids'],
                            'asks': self.orderbook_cache[symbol]['asks']
                        })
                        
                        await super()._handle_message(orderbook_data)
                        
                elif channel == 'orders':
                    # Process order updates
                    if 'data' in message:
                        for order_update in message['data']:
                            order_id = order_update['ordId']
                            if order_id in self.order_cache:
                                self.order_cache[order_id].update({
                                    'status': order_update['state'],
                                    'filled_size': float(order_update.get('fillSz', 0))
                                })
                                
        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}")
            await self._process_error(e)
            
    async def _maintain_orderbook(self, symbol: str):
        """Maintain orderbook accuracy"""
        while True:
            try:
                if symbol not in self.orderbook_cache or \
                   time.time() - self.orderbook_cache[symbol]['timestamp']/1000 > 30:
                    await self.subscribe_orderbook(symbol)
                await asyncio.sleep(30)
            except Exception as e:
                self.logger.error(f"Orderbook maintenance error: {str(e)}")
                await asyncio.sleep(1)
                
    async def _make_request(self, method: str, endpoint: str,
                           params: Optional[Dict] = None,
                           signed: bool = False) -> Dict:
        """Make HTTP request to exchange"""
        if not self.session:
            await self._init_session()
            
        url = self._get_url(endpoint)
        headers = {
            'Content-Type': 'application/json'
        }
        
        if signed:
            timestamp = str(int(time.time()))
            body = json.dumps(params) if params and method != 'GET' else ''
            
            signature = self._generate_signature(
                timestamp,
                method,
                endpoint,
                body
            )
            
            headers.update({
                'OK-ACCESS-KEY': self.api_key,
                'OK-ACCESS-SIGN': signature,
                'OK-ACCESS-TIMESTAMP': timestamp,
                'OK-ACCESS-PASSPHRASE': self.passphrase
            })
            
        try:
            if method == 'GET':
                response = await self.session.get(url, params=params, headers=headers)
            elif method == 'POST':
                response = await self.session.post(url, json=params, headers=headers)
            elif method == 'DELETE':
                response = await self.session.delete(url, json=params, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            response_data = await response.json()
            
            if response.status != 200:
                raise Exception(f"Request failed: {response_data}")
                
            return response_data
            
        except Exception as e:
            self.logger.error(f"Request error: {str(e)}")
            raise
            
    async def _ws_keep_alive(self):
        """Maintain WebSocket connection"""
        while True:
            try:
                if self.ws_public:
                    await self.ws_public.ping()
                if self.ws_private:
                    await self.ws_private.ping()
                await asyncio.sleep(15)
            except Exception as e:
                self.logger.error(f"WebSocket keepalive error: {str(e)}")
                await self._ws_connect()