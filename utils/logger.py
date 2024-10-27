import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

class CustomFormatter(logging.Formatter):
    """Кастомный форматтер с цветным выводом для консоли"""
    
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    
    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: grey + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset
    }
    
    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)

def setup_logger(name: str, log_level: Optional[int] = None) -> logging.Logger:
    """
    Настройка логгера с файловым и консольным выводом
    
    Args:
        name: Имя логгера
        log_level: Уровень логирования (по умолчанию INFO)
    
    Returns:
        logging.Logger: Настроенный логгер
    """
    if log_level is None:
        log_level = logging.INFO
        
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Создаем директорию для логов если её нет
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Формируем имя файла лога
    current_date = datetime.now().strftime('%Y-%m-%d')
    log_file = log_dir / f"{name}_{current_date}.log"
    
    # Настраиваем форматтеры
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Хендлер для файла
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(file_formatter)
    
    # Хендлер для консоли
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(CustomFormatter())
    
    # Добавляем хендлеры к логгеру
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

class TradeLogger:
    """Специализированный логгер для торговых операций"""
    
    def __init__(self, name: str):
        self.logger = setup_logger(f"trade_{name}")
        
        # Создаем отдельный файл для торговых операций
        trade_log_dir = Path("logs/trades")
        trade_log_dir.mkdir(exist_ok=True, parents=True)
        
        current_date = datetime.now().strftime('%Y-%m-%d')
        trade_file = trade_log_dir / f"trades_{name}_{current_date}.log"
        
        trade_handler = logging.FileHandler(trade_file)
        trade_handler.setFormatter(logging.Formatter(
            '%(asctime)s,%(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        
        self.trade_logger = logging.getLogger(f"trades_{name}")
        self.trade_logger.setLevel(logging.INFO)
        self.trade_logger.addHandler(trade_handler)
        
    def log_order_placed(self, order: dict):
        """Логирование размещения ордера"""
        msg = (f"ORDER_PLACED,{order['symbol']},{order['side']},"
               f"{order['size']},{order.get('price', 'MARKET')}")
        self.trade_logger.info(msg)
        self.logger.info(f"Placed {order['side']} order for {order['symbol']}")
        
    def log_order_filled(self, order: dict, fill_price: float):
        """Логирование исполнения ордера"""
        msg = (f"ORDER_FILLED,{order['symbol']},{order['side']},"
               f"{order['size']},{fill_price}")
        self.trade_logger.info(msg)
        self.logger.info(
            f"Filled {order['side']} order for {order['symbol']} at {fill_price}"
        )
        
    def log_position_closed(self, position: dict, pnl: float):
        """Логирование закрытия позиции"""
        msg = (f"POSITION_CLOSED,{position['symbol']},{pnl},"
               f"{position['entry_price']},{position['exit_price']}")
        self.trade_logger.info(msg)
        self.logger.info(
            f"Closed position for {position['symbol']} with PnL: {pnl:.2f}"
        )
        
    def log_error(self, error_msg: str):
        """Логирование ошибок"""
        self.logger.error(error_msg)
        self.trade_logger.error(f"ERROR,{error_msg}")