from typing import Dict, List, Optional, Type
import asyncio
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from queue import Queue

from strategies.base_strategy import BaseStrategy
from strategies.combined.impulse_imbalance import ImpulseImbalanceStrategy
from strategies.combined.arbitrage_volume import ArbitrageVolumeStrategy
from core.risk_manager import RiskManager
from exchanges.base import BaseExchange
from models.position import Position
from models.orderbook import OrderBook
from utils.logger import setup_logger
from utils.metrics import MetricsCollector

class TradingEngine:
    def __init__(self, config: Dict):
        self.config = config
        self.logger = setup_logger('trading_engine')
        
        # Инициализация компонентов
        self.risk_manager = RiskManager(config.get('risk', {}))
        self.metrics_collector = MetricsCollector()
        
        # Инициализация бирж
        self.exchanges = {}
        self.initialize_exchanges()
        
        # Инициализация стратегий
        self.strategies = {}
        self.initialize_strategies()
        
        # Торговое состояние
        self.is_running = False
        self.positions = {}
        self.pending_orders = {}
        
        # Очереди для асинхронной обработки
        self.market_data_queue = Queue()
        self.order_queue = Queue()
        self.signal_queue = Queue()
        
        # Отслеживание производительности
        self.start_time = None
        self.total_trades = 0
        self.profitable_trades = 0
        
        # Thread pool для параллельной обработки
        self.executor = ThreadPoolExecutor(max_workers=4)
        
    def initialize_exchanges(self):
        """Инициализация подключений к биржам"""
        exchange_configs = self.config.get('exchanges', {})
        for exchange_name, exchange_config in exchange_configs.items():
            try:
                exchange_class = self.get_exchange_class(exchange_name)
                self.exchanges[exchange_name] = exchange_class(exchange_config)
                self.logger.info(f"Initialized exchange: {exchange_name}")
            except Exception as e:
                self.logger.error(f"Failed to initialize exchange {exchange_name}: {str(e)}")
            
    def initialize_strategies(self):
        """Инициализация торговых стратегий"""
        trading_config = self.config.get('trading', {})
        strategy_configs = self.config.get('strategies', {})
        
        # Получаем торговые пары из конфигурации
        pairs = trading_config.get('pairs', [])
        
        for strategy_name, strategy_config in strategy_configs.items():
            try:
                # Создаем экземпляр стратегии с конфигурацией
                if strategy_name == 'ImpulseImbalance':
                    self.strategies[strategy_name] = ImpulseImbalanceStrategy(
                        symbols=pairs,
                        config=strategy_config
                    )
                elif strategy_name == 'ArbitrageVolume':
                    self.strategies[strategy_name] = ArbitrageVolumeStrategy(
                        symbol_pairs=trading_config.get('pair_mappings', []),
                        config=strategy_config
                    )
                self.logger.info(f"Initialized strategy: {strategy_name}")
            except Exception as e:
                self.logger.error(f"Failed to initialize strategy {strategy_name}: {str(e)}")
                
    async def start(self):
        """Запуск торгового движка"""
        self.logger.info("Starting trading engine...")
        self.is_running = True
        self.start_time = time.time()
        
        try:
            # Запуск подключений к биржам
            await self.connect_exchanges()
            
            # Запуск обработчиков
            await asyncio.gather(
                self.market_data_loop(),
                self.signal_processing_loop(),
                self.order_processing_loop(),
                self.position_monitoring_loop()
            )
        except Exception as e:
            self.logger.error(f"Error in trading engine: {str(e)}")
            await self.stop()
            
    async def stop(self):
        """Остановка торгового движка"""
        self.logger.info("Stopping trading engine...")
        self.is_running = False
        
        # Закрытие всех позиций
        await self.close_all_positions()
        
        # Отключение от бирж
        await self.disconnect_exchanges()
        
        # Остановка thread pool
        self.executor.shutdown(wait=True)
        
    async def connect_exchanges(self):
        """Подключение ко всем биржам"""
        for exchange_name, exchange in self.exchanges.items():
            try:
                await exchange.connect()
                self.logger.info(f"Connected to {exchange_name}")
            except Exception as e:
                self.logger.error(f"Failed to connect to {exchange_name}: {str(e)}")
                raise
                
    async def disconnect_exchanges(self):
        """Отключение от всех бирж"""
        for exchange_name, exchange in self.exchanges.items():
            try:
                await exchange.disconnect()
                self.logger.info(f"Disconnected from {exchange_name}")
            except Exception as e:
                self.logger.error(f"Error disconnecting from {exchange_name}: {str(e)}")
                
    async def market_data_loop(self):
        """Обработка рыночных данных"""
        while self.is_running:
            try:
                while not self.market_data_queue.empty():
                    data = self.market_data_queue.get()
                    await self.process_market_data(data)
                    
                await asyncio.sleep(0.001)
            except Exception as e:
                self.logger.error(f"Error in market data loop: {str(e)}")
                
    async def process_market_data(self, data: Dict):
        """Обработка входящих рыночных данных"""
        exchange_name = data.get('exchange')
        symbol = data.get('symbol')
        
        if not exchange_name or not symbol:
            return
            
        # Обновление книги ордеров
        if data.get('type') == 'orderbook':
            orderbook = OrderBook(
                symbol=symbol,
                timestamp=data.get('timestamp', time.time()),
                bids=data.get('bids', []),
                asks=data.get('asks', [])
            )
            
            # Обновление стратегий
            for strategy in self.strategies.values():
                strategy.update_orderbook(symbol, orderbook)
                
            # Генерация сигналов
            await self.generate_signals(symbol)
            
    def get_exchange_class(self, exchange_name: str):
        """Получение класса биржи по имени"""
        if exchange_name.lower() == 'bybit':
            from exchanges.bybit import BybitExchange
            return BybitExchange
        elif exchange_name.lower() == 'okx':
            from exchanges.okx import OKXExchange
            return OKXExchange
        else:
            raise ValueError(f"Unsupported exchange: {exchange_name}")
            
    async def close_all_positions(self):
        """Закрытие всех открытых позиций"""
        for position in list(self.positions.values()):
            try:
                await self.close_position(position.symbol, 'system_shutdown')
            except Exception as e:
                self.logger.error(f"Error closing position {position.symbol}: {str(e)}")
                
    def get_statistics(self) -> Dict:
        """Получение торговой статистики"""
        return {
            'total_trades': self.total_trades,
            'profitable_trades': self.profitable_trades,
            'win_rate': self.profitable_trades / self.total_trades if self.total_trades > 0 else 0,
            'running_time': time.time() - self.start_time if self.start_time else 0,
            'open_positions': len(self.positions),
            'risk_metrics': self.risk_manager.calculate_risk_metrics(),
            'performance_metrics': self.metrics_collector.get_metrics()
        }

    # [Остальные методы остаются без изменений]
            
    async def signal_processing_loop(self):
        """Process trading signals"""
        while self.is_running:
            try:
                while not self.signal_queue.empty():
                    signal = self.signal_queue.get()
                    await self.process_signal(signal)
                    
                await asyncio.sleep(0.001)
            except Exception as e:
                self.logger.error(f"Error in signal processing loop: {str(e)}")
                
    async def process_signal(self, signal: Dict):
        """Process trading signal"""
        symbol = signal['symbol']
        strategy_name = signal['strategy']
        
        # Check risk limits
        size = self.risk_manager.adjust_position_size(
            signal['size'],
            symbol
        )
        
        if not self.risk_manager.can_open_position(symbol, size, signal['entry_price']):
            return
            
        # Create and submit order
        order = {
            'symbol': symbol,
            'side': signal['side'],
            'type': 'LIMIT',
            'size': size,
            'price': signal['entry_price'],
            'take_profit': signal['take_profit'],
            'stop_loss': signal['stop_loss'],
            'strategy': strategy_name
        }
        
        self.order_queue.put(order)
        
    async def order_processing_loop(self):
        """Process order queue"""
        while self.is_running:
            try:
                while not self.order_queue.empty():
                    order = self.order_queue.get()
                    await self.execute_order(order)
                    
                await asyncio.sleep(0.001)
            except Exception as e:
                self.logger.error(f"Error in order processing loop: {str(e)}")
                
    async def execute_order(self, order: Dict):
        """Execute trading order"""
        try:
            exchange = self.exchanges[order['exchange']]
            
            # Submit order to exchange
            order_result = await exchange.place_order(
                symbol=order['symbol'],
                side=order['side'],
                order_type=order['type'],
                size=order['size'],
                price=order['price']
            )
            
            if order_result['status'] == 'filled':
                # Create new position
                position = Position(
                    symbol=order['symbol'],
                    side=order['side'],
                    entry_price=order_result['price'],
                    size=order_result['filled_size'],
                    take_profit=order['take_profit'],
                    stop_loss=order['stop_loss'],
                    strategy=order['strategy']
                )
                
                self.positions[order['symbol']] = position
                self.metrics_collector.record_trade_open(position)
                
        except Exception as e:
            self.logger.error(f"Error executing order: {str(e)}")
            
    async def position_monitoring_loop(self):
        """Monitor open positions"""
        while self.is_running:
            try:
                for symbol, position in list(self.positions.items()):
                    strategy = self.strategies[position.strategy]
                    
                    # Update position with current price
                    current_price = self.get_current_price(symbol)
                    position.update_price(current_price)
                    
                    # Check if position should be closed
                    if strategy.should_close_position(position) or \
                       self.risk_manager.should_emergency_close():
                        await self.close_position(position)
                        
                await asyncio.sleep(0.1)  # Check positions every 100ms
            except Exception as e:
                self.logger.error(f"Error in position monitoring: {str(e)}")
                
    async def close_position(self, position: Position):
        """Close trading position"""
        try:
            exchange = self.exchanges[position.exchange]
            
            close_order = await exchange.place_order(
                symbol=position.symbol,
                side='sell' if position.side == 'buy' else 'buy',
                order_type='MARKET',
                size=position.size
            )
            
            if close_order['status'] == 'filled':
                # Calculate PnL
                pnl = self.calculate_pnl(position, close_order['price'])
                
                # Update metrics
                self.metrics_collector.record_trade_close(position, pnl)
                
                # Update risk manager
                self.risk_manager.on_trade_closed({
                    'symbol': position.symbol,
                    'pnl': pnl,
                    'duration': time.time() - position.entry_time
                })
                
                # Remove position
                del self.positions[position.symbol]
                
        except Exception as e:
            self.logger.error(f"Error closing position: {str(e)}")
            
    def calculate_pnl(self, position: Position, close_price: float) -> float:
        """Calculate position PnL"""
        if position.side == 'buy':
            return (close_price - position.entry_price) * position.size
        else:
            return (position.entry_price - close_price) * position.size
            
    async def generate_signals(self, symbol: str):
        """Generate trading signals from strategies"""
        for strategy_name, strategy in self.strategies.items():
            signal = strategy.should_open_position(symbol)
            if signal:
                signal['strategy'] = strategy_name
                signal['symbol'] = symbol
                self.signal_queue.put(signal)
                
    def get_current_price(self, symbol: str) -> float:
        """Get current price for symbol"""
        # Get price from primary exchange
        primary_exchange = self.exchanges[self.config['primary_exchange']]
        return primary_exchange.get_price(symbol)
        
    def get_exchange_class(self, exchange_name: str) -> Type[BaseExchange]:
        """Get exchange class by name"""
        if exchange_name.lower() == 'bybit':
            from exchanges.bybit import BybitExchange
            return BybitExchange
        elif exchange_name.lower() == 'okx':
            from exchanges.okx import OKXExchange
            return OKXExchange
        else:
            raise ValueError(f"Unsupported exchange: {exchange_name}")
            