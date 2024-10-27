from typing import Dict, List, Optional, Union
import asyncpg
import asyncio
from datetime import datetime, timedelta
import json
import pandas as pd
from models.position import Position
from models.orderbook import OrderBook
from utils.logger import setup_logger

class DatabaseRepository:
    def __init__(self, config: Dict):
        self.config = config
        self.pool: Optional[asyncpg.Pool] = None
        self.logger = setup_logger('database_repository')
        
    async def initialize(self):
        """Инициализация подключения к базе данных"""
        try:
            self.pool = await asyncpg.create_pool(
                user=self.config['user'],
                password=self.config['password'],
                database=self.config['database'],
                host=self.config['host'],
                port=self.config['port'],
                min_size=5,
                max_size=20
            )
            
            await self._create_tables()
            self.logger.info("Database connection established")
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {str(e)}")
            raise
            
    async def close(self):
        """Закрытие подключения к базе данных"""
        if self.pool:
            await self.pool.close()
            
    async def _create_tables(self):
        """Создание необходимых таблиц"""
        async with self.pool.acquire() as conn:
            # Таблица позиций
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS positions (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    side VARCHAR(10) NOT NULL,
                    entry_price DECIMAL NOT NULL,
                    size DECIMAL NOT NULL,
                    take_profit DECIMAL,
                    stop_loss DECIMAL,
                    strategy VARCHAR(50) NOT NULL,
                    exchange VARCHAR(20) NOT NULL,
                    entry_time TIMESTAMP NOT NULL,
                    exit_time TIMESTAMP,
                    status VARCHAR(20) NOT NULL,
                    realized_pnl DECIMAL,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица ордеров
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    position_id INTEGER REFERENCES positions(id),
                    symbol VARCHAR(20) NOT NULL,
                    side VARCHAR(10) NOT NULL,
                    order_type VARCHAR(20) NOT NULL,
                    size DECIMAL NOT NULL,
                    price DECIMAL,
                    status VARCHAR(20) NOT NULL,
                    exchange VARCHAR(20) NOT NULL,
                    exchange_order_id VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица торговых данных
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    price DECIMAL NOT NULL,
                    size DECIMAL NOT NULL,
                    side VARCHAR(10) NOT NULL,
                    exchange VARCHAR(20) NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица метрик
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS metrics (
                    id SERIAL PRIMARY KEY,
                    metric_name VARCHAR(50) NOT NULL,
                    metric_value DECIMAL NOT NULL,
                    symbol VARCHAR(20),
                    strategy VARCHAR(50),
                    timestamp TIMESTAMP NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
    async def save_position(self, position: Position) -> int:
        """Сохранение позиции в базу данных"""
        async with self.pool.acquire() as conn:
            position_id = await conn.fetchval('''
                INSERT INTO positions (
                    symbol, side, entry_price, size, take_profit, stop_loss,
                    strategy, exchange, entry_time, status, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING id
            ''', position.symbol, position.side, position.entry_price,
                position.size, position.take_profit, position.stop_loss,
                position.strategy, position.exchange,
                datetime.fromtimestamp(position.entry_time),
                position.status, json.dumps(position.to_dict()))
                
            return position_id
            
    async def update_position(self, position_id: int, updates: Dict):
        """Обновление позиции"""
        set_clauses = []
        values = []
        for i, (key, value) in enumerate(updates.items(), start=1):
            set_clauses.append(f"{key} = ${i}")
            values.append(value)
            
        query = f'''
            UPDATE positions
            SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ${len(values) + 1}
        '''
        values.append(position_id)
        
        async with self.pool.acquire() as conn:
            await conn.execute(query, *values)
            
    async def get_position(self, position_id: int) -> Optional[Dict]:
        """Получение позиции по ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow('''
                SELECT * FROM positions WHERE id = $1
            ''', position_id)
            
            if row:
                return dict(row)
            return None
            
    async def get_open_positions(self) -> List[Dict]:
        """Получение открытых позиций"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT * FROM positions
                WHERE status = 'open'
                ORDER BY entry_time DESC
            ''')
            
            return [dict(row) for row in rows]
            
    async def save_order(self, order: Dict) -> int:
        """Сохранение ордера"""
        async with self.pool.acquire() as conn:
            order_id = await conn.fetchval('''
                INSERT INTO orders (
                    position_id, symbol, side, order_type, size,
                    price, status, exchange, exchange_order_id
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
            ''', order.get('position_id'), order['symbol'],
                order['side'], order['order_type'], order['size'],
                order.get('price'), order['status'],
                order['exchange'], order.get('exchange_order_id'))
                
            return order_id
            
    async def save_trade(self, trade: Dict):
        """Сохранение сделки"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO trades (
                    symbol, price, size, side, exchange,
                    timestamp, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ''', trade['symbol'], trade['price'], trade['size'],
                trade['side'], trade['exchange'],
                datetime.fromtimestamp(trade['timestamp']),
                json.dumps(trade.get('metadata', {})))
                
    async def save_metric(self, metric: Dict):
        """Сохранение метрики"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO metrics (
                    metric_name, metric_value, symbol,
                    strategy, timestamp, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6)
            ''', metric['name'], metric['value'],
                metric.get('symbol'), metric.get('strategy'),
                datetime.fromtimestamp(metric['timestamp']),
                json.dumps(metric.get('metadata', {})))
                
    async def get_trades_history(
        self,
        symbol: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[Dict]:
        """Получение истории сделок"""
        conditions = []
        values = []
        
        if symbol:
            conditions.append(f"symbol = ${len(values) + 1}")
            values.append(symbol)
            
        if start_time:
            conditions.append(f"timestamp >= ${len(values) + 1}")
            values.append(start_time)
            
        if end_time:
            conditions.append(f"timestamp <= ${len(values) + 1}")
            values.append(end_time)
            
        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(f'''
                SELECT * FROM trades
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT {limit}
            ''', *values)
            
            return [dict(row) for row in rows]
            
    async def get_metrics(
        self,
        metric_name: Optional[str] = None,
        symbol: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> pd.DataFrame:
        """Получение метрик в виде DataFrame"""
        conditions = []
        values = []
        
        if metric_name:
            conditions.append(f"metric_name = ${len(values) + 1}")
            values.append(metric_name)
            
        if symbol:
            conditions.append(f"symbol = ${len(values) + 1}")
            values.append(symbol)
            
        if start_time:
            conditions.append(f"timestamp >= ${len(values) + 1}")
            values.append(start_time)
            
        if end_time:
            conditions.append(f"timestamp <= ${len(values) + 1}")
            values.append(end_time)
            
        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(f'''
                SELECT * FROM metrics
                WHERE {where_clause}
                ORDER BY timestamp ASC
            ''', *values)
            
            return pd.DataFrame([dict(row) for row in rows])
            
    async def get_performance_summary(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict:
        """Получение сводки по производительности"""
        conditions = ["status = 'closed'"]
        values = []
        
        if start_time:
            conditions.append(f"exit_time >= ${len(values) + 1}")
            values.append(start_time)
            
        if end_time:
            conditions.append(f"exit_time <= ${len(values) + 1}")
            values.append(end_time)
            
        where_clause = " AND ".join(conditions)
        
        async with self.pool.acquire() as conn:
            summary = await conn.fetchrow(f'''
                SELECT
                    COUNT(*) as total_trades,
                    COUNT(CASE WHEN realized_pnl > 0 THEN 1 END) as profitable_trades,
                    SUM(realized_pnl) as total_pnl,
                    AVG(realized_pnl) as avg_pnl,
                    MAX(realized_pnl) as max_profit,
                    MIN(realized_pnl) as max_loss,
                    AVG(EXTRACT(EPOCH FROM (exit_time - entry_time))) as avg_duration
                FROM positions
                WHERE {where_clause}
            ''', *values)
            
            return dict(summary)
            
    async def cleanup_old_data(self, days: int = 30):
        """Очистка старых данных"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        async with self.pool.acquire() as conn:
            await conn.execute('''
                DELETE FROM trades
                WHERE timestamp < $1
            ''', cutoff_date)
            
            await conn.execute('''
                DELETE FROM metrics
                WHERE timestamp < $1
            ''', cutoff_date)
            
            self.logger.info(f"Cleaned up data older than {cutoff_date}")

class RepositoryManager:
    """Менеджер для работы с репозиторием"""
    _instance = None
    
    def __new__(cls, config: Optional[Dict] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.repository = None
            cls._instance.config = config
        return cls._instance
        
    async def get_repository(self) -> DatabaseRepository:
        """Получение экземпляра репозитория"""
        if self.repository is None:
            if self.config is None:
                raise ValueError("Database configuration not provided")
                
            self.repository = DatabaseRepository(self.config)
            await self.repository.initialize()
            
        return self.repository
        
    async def close(self):
        """Закрытие соединения с базой данных"""
        if self.repository:
            await self.repository.close()
            self.repository = None