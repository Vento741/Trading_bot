import asyncio
import aiohttp
from typing import Optional, Dict
import json
from datetime import datetime
from utils.logger import setup_logger

class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.logger = setup_logger('telegram_notifier')
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def initialize(self):
        """Инициализация сессии"""
        self.session = aiohttp.ClientSession()
        
    async def close(self):
        """Закрытие сессии"""
        if self.session:
            await self.session.close()
            
    async def send_message(self, message: str, parse_mode: str = 'HTML'):
        """Отправка сообщения"""
        try:
            if not self.session:
                await self.initialize()
                
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode
            }
            
            async with self.session.post(url, json=data) as response:
                if response.status != 200:
                    self.logger.error(f"Failed to send message: {await response.text()}")
                    
        except Exception as e:
            self.logger.error(f"Error sending telegram message: {str(e)}")
            
    async def send_trade_notification(self, trade: Dict):
        """Уведомление о сделке"""
        message = (
            f"🔔 <b>Trade Executed</b>\n"
            f"Symbol: {trade['symbol']}\n"
            f"Side: {trade['side']}\n"
            f"Size: {trade['size']}\n"
            f"Price: {trade['price']}\n"
            f"Strategy: {trade['strategy']}\n"
            f"Time: {datetime.fromtimestamp(trade['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        await self.send_message(message)
        
    async def send_error_alert(self, error: str, severity: str = 'WARNING'):
        """Уведомление об ошибке"""
        emoji = '⚠️' if severity == 'WARNING' else '🚨'
        message = (
            f"{emoji} <b>{severity}</b>\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Error: {error}"
        )
        await self.send_message(message)
        
    async def send_performance_update(self, metrics: Dict):
        """Уведомление о производительности"""
        message = (
            f"📊 <b>Performance Update</b>\n"
            f"PnL: {metrics['total_pnl']:.2f}\n"
            f"Win Rate: {metrics['win_rate']:.1f}%\n"
            f"Open Positions: {metrics['open_positions']}\n"
            f"Daily Volume: {metrics['daily_volume']:.2f}"
        )
        await self.send_message(message)
        
    async def send_position_update(self, position: Dict):
        """Уведомление об изменении позиции"""
        message = (
            f"📈 <b>Position Update</b>\n"
            f"Symbol: {position['symbol']}\n"
            f"Side: {position['side']}\n"
            f"Size: {position['size']}\n"
            f"Entry: {position['entry_price']}\n"
            f"Current: {position['current_price']}\n"
            f"PnL: {position['unrealized_pnl']:.2f}\n"
            f"ROI: {position['roi']:.2f}%"
        )
        await self.send_message(message)