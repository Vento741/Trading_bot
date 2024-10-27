import os
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv
# from config.settings import WEBSOCKET_CONFIG

# Загрузка переменных окружения
load_dotenv()

# Базовая директория проекта
BASE_DIR = Path(__file__).resolve().parent.parent

# Настройки баз данных
DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'trading_bot'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', ''),
    'min_size': 5,
    'max_size': 20
}

# Настройки WebSocket
WEBSOCKET_CONFIG = {
    'ping_interval': 20,
    'ping_timeout': 5,
    'reconnect_delay': 2,
    'max_reconnect_attempts': 10
}

# Настройки Redis
REDIS_CONFIG = {
    'host': os.getenv('REDIS_HOST', 'localhost'),
    'port': int(os.getenv('REDIS_PORT', 6379)),
    'db': int(os.getenv('REDIS_DB', 0))
}

# Настройки бирж
EXCHANGE_CONFIGS = {
    'bybit': {
        'api_key': os.getenv('BYBIT_API_KEY', ''),
        'api_secret': os.getenv('BYBIT_API_SECRET', ''),
        'testnet': os.getenv('BYBIT_TESTNET', 'True').lower() == 'true',
        'category': 'spot',
        'enabled': True,  # Биржа активна
        'ws_config': {
            'ping_interval': 20,
            'reconnect_attempts': 5,
            'reconnect_delay': 2,
            'connection_timeout': 10
        }
    },
    'okx': {
        'api_key': os.getenv('OKX_API_KEY', ''),
        'api_secret': os.getenv('OKX_API_SECRET', ''),
        'passphrase': os.getenv('OKX_PASSPHRASE', ''),
        'testnet': os.getenv('OKX_TESTNET', 'True').lower() == 'true',
        'enabled': False,  # Биржа отключена
        'ws_config': {
            'ping_interval': 20,
            'reconnect_attempts': 5,
            'reconnect_delay': 2,
            'connection_timeout': 10
        }
    }
}

# Торговые параметры (оставляем только пары для Bybit)
TRADING_CONFIG = {
    'pairs': ['BTCUSDT', 'ETHUSDT'],  # Формат пар для Bybit
    'timeframes': ['1m', '5m', '15m', '1h', '4h'],
    'default_leverage': 1,
    'position_size_pct': 0.03,
    'max_positions': 5,
    'max_positions_per_symbol': 2,
    'primary_exchange': 'bybit'  # Указываем основную биржу
}

# Настройки риск-менеджмента
RISK_CONFIG = {
    'max_position_size': 0.05,  # 5% от портфеля
    'max_total_risk': 0.15,     # 15% от портфеля
    'max_correlated_positions': 3,
    'max_drawdown_pct': 40.0,   # 40% максимальная просадка
    'pause_after_losses': 10,    # Пауза после 10 убыточных сделок
    'daily_loss_limit_pct': 5.0, # 5% дневной лимит потерь
    'position_sizing_method': 'fixed_pct'  # или 'kelly_criterion'
}

# Настройки стратегий
STRATEGY_CONFIGS = {
    'OrderBookImbalance': {
        'min_imbalance_ratio': 3.0,
        'large_order_threshold': 100.0,
        'min_spread': 0.0005,
        'take_profit_pct': 0.002,
        'stop_loss_pct': 0.001,
        'max_hold_time': 120
    },
    'PriceAction': {
        'min_impulse_pct': 0.003,
        'volume_threshold': 2.0,
        'retracement_min': 0.3,
        'retracement_max': 0.5,
        'take_profit_pct': 0.003,
        'stop_loss_pct': 0.002,
        'max_hold_time': 60
    },
    'Arbitrage': {
        'min_spread_pct': 0.002,
        'min_liquidity': 200.0,
        'correlation_threshold': 0.8,
        'take_profit_pct': 0.001,
        'stop_loss_pct': 0.0008,
        'max_hold_time': 30
    },
    'VolumeImpulse': {
        'volume_threshold': 2.5,
        'price_change_threshold': 0.002,
        'consolidation_periods': 5,
        'take_profit_pct': 0.003,
        'stop_loss_pct': 0.002,
        'max_hold_time': 180
    }
}

# Настройки логирования
LOGGING_CONFIG = {
    'level': os.getenv('LOG_LEVEL', 'INFO'),
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'dir': BASE_DIR / 'logs',
    'max_size': 10 * 1024 * 1024,  # 10MB
    'backup_count': 5
}

# Настройки мониторинга
MONITORING_CONFIG = {
    'enabled': True,
    'prometheus_port': int(os.getenv('PROMETHEUS_PORT', 9090)),
    'metrics_interval': 5,  # секунды
    'alert_telegram_token': os.getenv('TELEGRAM_BOT_TOKEN', ''),
    'alert_telegram_chat_id': os.getenv('TELEGRAM_CHAT_ID', '')
}


# Настройки исполнения ордеров
EXECUTION_CONFIG = {
    'max_slippage_pct': 0.1,    # 0.1% максимальное проскальзывание
    'retry_attempts': 3,         # Количество попыток размещения ордера
    'retry_delay': 1.0,         # Задержка между попытками в секундах
    'partial_fill_timeout': 60,  # Тайм-аут для частичного исполнения
    'order_update_interval': 1.0 # Интервал обновления статуса ордера
}

# Параметры бэктестинга
BACKTEST_CONFIG = {
    'default_deposit': 10000,    # Начальный депозит для бэктеста
    'commission_rate': 0.001,    # 0.1% комиссия
    'data_dir': BASE_DIR / 'data/historical',
    'results_dir': BASE_DIR / 'data/backtest_results'
}