from prometheus_client import start_http_server, Counter, Gauge, Histogram
from typing import Dict
import time

class PrometheusMonitor:
    def __init__(self, port: int = 9090):
        # Метрики торговли
        self.trades_total = Counter('trades_total', 'Total number of trades', ['strategy', 'symbol'])
        self.pnl_total = Gauge('pnl_total', 'Total PnL', ['strategy'])
        self.position_size = Gauge('position_size', 'Current position size', ['symbol'])
        self.execution_time = Histogram('trade_execution_seconds', 'Trade execution time')
        
        # Метрики производительности
        self.latency = Histogram('exchange_latency_seconds', 'Exchange API latency', ['exchange'])
        self.order_book_depth = Gauge('orderbook_depth', 'Order book depth', ['symbol'])
        self.system_memory = Gauge('system_memory_bytes', 'System memory usage')
        
        start_http_server(port)
        
    def record_trade(self, strategy: str, symbol: str):
        """Запись метрик сделки"""
        self.trades_total.labels(strategy=strategy, symbol=symbol).inc()
        
    def update_pnl(self, strategy: str, pnl: float):
        """Обновление PnL"""
        self.pnl_total.labels(strategy=strategy).set(pnl)
        
    def update_position(self, symbol: str, size: float):
        """Обновление размера позиции"""
        self.position_size.labels(symbol=symbol).set(size)
        
    def record_execution_time(self, duration: float):
        """Запись времени исполнения"""
        self.execution_time.observe(duration)
        
    def record_latency(self, exchange: str, latency: float):
        """Запись задержки API"""
        self.latency.labels(exchange=exchange).observe(latency)
        
    def update_metrics(self, metrics: Dict):
        """Обновление всех метрик"""
        for strategy, data in metrics.get('strategies', {}).items():
            self.pnl_total.labels(strategy=strategy).set(data.get('pnl', 0))
            
        for symbol, depth in metrics.get('orderbook_depth', {}).items():
            self.order_book_depth.labels(symbol=symbol).set(depth)
            
        if 'system_memory' in metrics:
            self.system_memory.set(metrics['system_memory'])