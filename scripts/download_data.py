import argparse
import sys
import asyncio
import aiohttp
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json
from typing import List, Dict, Optional
import logging
import time

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import TRADING_CONFIG
from utils.logger import setup_logger

logger = setup_logger('data_downloader')

class DataDownloader:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.base_url = {
            'bybit': 'https://api.bybit.com',
            'okx': 'https://www.okx.com'
        }
        self.data_dir = Path('data/historical')
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
    async def initialize(self):
        """Инициализация HTTP сессии"""
        self.session = aiohttp.ClientSession()
        
    async def close(self):
        """Закрытие HTTP сессии"""
        if self.session:
            await self.session.close()
            
    async def download_orderbook_data(
        self,
        symbol: str,
        exchange: str,
        start_date: datetime,
        end_date: datetime,
        interval: int = 1  # интервал в секундах
    ) -> pd.DataFrame:
        """Загрузка исторических данных книги ордеров"""
        
        data = []
        current_date = start_date
        
        while current_date <= end_date:
            try:
                if exchange == 'bybit':
                    orderbook = await self._get_bybit_orderbook(symbol)
                else:  # okx
                    orderbook = await self._get_okx_orderbook(symbol)
                    
                if orderbook:
                    data.append({
                        'timestamp': current_date.timestamp(),
                        'symbol': symbol,
                        'bids': json.dumps(orderbook['bids']),
                        'asks': json.dumps(orderbook['asks'])
                    })
                    
                current_date += timedelta(seconds=interval)
                await asyncio.sleep(interval)  # Соблюдаем ограничения API
                
            except Exception as e:
                logger.error(f"Error downloading data for {symbol} at {current_date}: {str(e)}")
                await asyncio.sleep(5)  # Пауза при ошибке
                
        return pd.DataFrame(data)
        
    async def _get_bybit_orderbook(self, symbol: str) -> Dict:
        """Получение книги ордеров с Bybit"""
        try:
            url = f"{self.base_url['bybit']}/v5/market/orderbook"
            params = {
                'category': 'spot',
                'symbol': symbol,
                'limit': 25  # глубина стакана
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data['retCode'] == 0:
                        return {
                            'bids': [[float(p), float(s)] for p, s in data['result']['b']],
                            'asks': [[float(p), float(s)] for p, s in data['result']['a']]
                        }
                    
            return None
            
        except Exception as e:
            logger.error(f"Bybit API error: {str(e)}")
            return None
            
    async def _get_okx_orderbook(self, symbol: str) -> Dict:
        """Получение книги ордеров с OKX"""
        try:
            url = f"{self.base_url['okx']}/api/v5/market/books"
            params = {
                'instId': symbol,
                'sz': 25
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data['code'] == '0':
                        return {
                            'bids': [[float(b[0]), float(b[1])] for b in data['data'][0]['bids']],
                            'asks': [[float(a[0]), float(a[1])] for a in data['data'][0]['asks']]
                        }
                    
            return None
            
        except Exception as e:
            logger.error(f"OKX API error: {str(e)}")
            return None
            
    async def download_trades(
        self,
        symbol: str,
        exchange: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Загрузка исторических сделок"""
        data = []
        current_date = start_date
        
        while current_date <= end_date:
            try:
                if exchange == 'bybit':
                    trades = await self._get_bybit_trades(symbol)
                else:  # okx
                    trades = await self._get_okx_trades(symbol)
                    
                if trades:
                    data.extend(trades)
                    
                current_date += timedelta(minutes=1)
                await asyncio.sleep(1)  # Соблюдаем ограничения API
                
            except Exception as e:
                logger.error(f"Error downloading trades for {symbol} at {current_date}: {str(e)}")
                await asyncio.sleep(5)
                
        return pd.DataFrame(data)
        
    async def _get_bybit_trades(self, symbol: str) -> List[Dict]:
        """Получение последних сделок с Bybit"""
        try:
            url = f"{self.base_url['bybit']}/v5/market/recent-trade"
            params = {
                'category': 'spot',
                'symbol': symbol,
                'limit': 100
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data['retCode'] == 0:
                        return [{
                            'timestamp': int(trade['time']),
                            'price': float(trade['price']),
                            'size': float(trade['size']),
                            'side': trade['side'].lower(),
                            'symbol': symbol
                        } for trade in data['result']['list']]
                    
            return []
            
        except Exception as e:
            logger.error(f"Bybit trades API error: {str(e)}")
            return []
            
    async def _get_okx_trades(self, symbol: str) -> List[Dict]:
        """Получение последних сделок с OKX"""
        try:
            url = f"{self.base_url['okx']}/api/v5/market/trades"
            params = {
                'instId': symbol,
                'limit': 100
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data['code'] == '0':
                        return [{
                            'timestamp': int(trade['ts']),
                            'price': float(trade['px']),
                            'size': float(trade['sz']),
                            'side': trade['side'].lower(),
                            'symbol': symbol
                        } for trade in data['data']]
                    
            return []
            
        except Exception as e:
            logger.error(f"OKX trades API error: {str(e)}")
            return []
            
    def save_data(self, df: pd.DataFrame, symbol: str, start_date: datetime, end_date: datetime):
        """Сохранение данных в CSV"""
        filename = f"{symbol}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"
        filepath = self.data_dir / filename
        df.to_csv(filepath, index=False)
        logger.info(f"Data saved to {filepath}")
        
    async def download_all_data(
        self,
        symbols: List[str] = None,
        exchanges: List[str] = None,
        days: int = 7
    ):
        """Загрузка всех необходимых данных"""
        if not symbols:
            symbols = TRADING_CONFIG['pairs']
        if not exchanges:
            exchanges = ['bybit', 'okx']
            
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        await self.initialize()
        
        try:
            for symbol in symbols:
                for exchange in exchanges:
                    logger.info(f"Downloading data for {symbol} from {exchange}")
                    
                    # Загрузка книги ордеров
                    orderbook_data = await self.download_orderbook_data(
                        symbol,
                        exchange,
                        start_date,
                        end_date
                    )
                    
                    if not orderbook_data.empty:
                        self.save_data(
                            orderbook_data,
                            f"{symbol}_{exchange}_orderbook",
                            start_date,
                            end_date
                        )
                        
                    # Загрузка сделок
                    trades_data = await self.download_trades(
                        symbol,
                        exchange,
                        start_date,
                        end_date
                    )
                    
                    if not trades_data.empty:
                        self.save_data(
                            trades_data,
                            f"{symbol}_{exchange}_trades",
                            start_date,
                            end_date
                        )
                        
        finally:
            await self.close()

async def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description='Download historical market data')
    parser.add_argument('--symbols', nargs='+', help='List of symbols to download')
    parser.add_argument('--exchanges', nargs='+', help='List of exchanges to download from')
    parser.add_argument('--days', type=int, default=7, help='Number of days of historical data')
    args = parser.parse_args()
    
    try:
        downloader = DataDownloader()
        await downloader.download_all_data(
            symbols=args.symbols,
            exchanges=args.exchanges,
            days=args.days
        )
        logger.info("Data download completed successfully")
        
    except Exception as e:
        logger.error(f"Error downloading data: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())