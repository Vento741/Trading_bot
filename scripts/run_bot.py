import asyncio
import sys
import os
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import (
    DATABASE_CONFIG, EXCHANGE_CONFIGS, 
    TRADING_CONFIG, RISK_CONFIG, STRATEGY_CONFIGS
)
from core.engine import TradingEngine
from utils.logger import setup_logger
from database.repository import RepositoryManager
import signal

logger = setup_logger('bot_runner')

class BotRunner:
    def __init__(self):
        self.engine = None
        self.running = False
        
    async def start(self):
        """Запуск торгового бота"""
        try:
            logger.info("Initializing trading bot...")
            
            # Инициализация репозитория
            repo_manager = RepositoryManager(DATABASE_CONFIG)
            repository = await repo_manager.get_repository()
            
            # Создание и настройка торгового движка
            self.engine = TradingEngine({
                'exchanges': EXCHANGE_CONFIGS,
                'trading': TRADING_CONFIG,
                'risk': RISK_CONFIG,
                'strategies': STRATEGY_CONFIGS,
                'repository': repository
            })
            
            # Регистрация обработчиков сигналов
            self._setup_signal_handlers()
            
            # Запуск торгового движка
            self.running = True
            logger.info("Starting trading engine...")
            await self.engine.start()
            
            # Основной цикл работы
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error running bot: {str(e)}")
            await self.stop()
            sys.exit(1)
            
    async def stop(self):
        """Остановка торгового бота"""
        logger.info("Stopping trading bot...")
        self.running = False
        
        if self.engine:
            await self.engine.stop()
            
        # Закрытие соединения с базой данных
        repo_manager = RepositoryManager()
        await repo_manager.close()
        
        logger.info("Trading bot stopped")
        
    def _setup_signal_handlers(self):
        """Настройка обработчиков сигналов"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}")
            asyncio.create_task(self.stop())
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

def main():
    try:
        # Проверка наличия необходимых переменных окружения
        required_env_vars = [
            'BYBIT_API_KEY', 'BYBIT_API_SECRET',
            'OKX_API_KEY', 'OKX_API_SECRET', 'OKX_PASSPHRASE'
        ]
        
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
            sys.exit(1)
            
        # Создание и запуск бота
        bot = BotRunner()
        asyncio.run(bot.start())
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()