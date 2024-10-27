import sys
import asyncio
from pathlib import Path
import pandas as pd
import numpy as np
from typing import Dict, List
import json
import matplotlib.pyplot as plt
from datetime import datetime

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import BACKTEST_CONFIG, STRATEGY_CONFIGS
from strategies.base_strategy import BaseStrategy
from models.orderbook import OrderBook
from utils.logger import setup_logger

logger = setup_logger('backtest')

class Backtester:
    def __init__(self, config: Dict):
        self.config = config
        self.initial_balance = config['default_deposit']
        self.commission_rate = config['commission_rate']
        self.balance = self.initial_balance
        self.positions = {}
        self.trades_history = []
        self.equity_curve = []
        
    async def load_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Загрузка исторических данных"""
        data_path = Path(self.config['data_dir']) / f"{symbol}_{start_date}_{end_date}.csv"
        if not data_path.exists():
            raise FileNotFoundError(f"Historical data not found: {data_path}")
        return pd.read_csv(data_path)
        
    def prepare_orderbook(self, row: pd.Series) -> OrderBook:
        """Подготовка книги ордеров из данных"""
        return OrderBook(
            symbol=row['symbol'],
            timestamp=row['timestamp'],
            bids=json.loads(row['bids']),
            asks=json.loads(row['asks'])
        )
        
    def execute_trade(self, signal: Dict, current_price: float) -> Dict:
        """Исполнение сделки с учетом комиссии"""
        commission = current_price * signal['size'] * self.commission_rate
        total_cost = current_price * signal['size'] + commission
        
        if total_cost > self.balance:
            return None
            
        self.balance -= total_cost
        return {
            'entry_price': current_price,
            'size': signal['size'],
            'commission': commission,
            'timestamp': signal['timestamp']
        }
        
    def run_strategy(self, strategy: BaseStrategy, data: pd.DataFrame) -> Dict:
        """Запуск стратегии на исторических данных"""
        for _, row in data.iterrows():
            orderbook = self.prepare_orderbook(row)
            signal = strategy.should_open_position(orderbook)
            
            if signal:
                trade = self.execute_trade(signal, orderbook.get_mid_price())
                if trade:
                    self.trades_history.append(trade)
            
            # Обновление позиций и проверка условий выхода
            self.update_positions(orderbook)
            
        return self.calculate_statistics()
        
    def update_positions(self, orderbook: OrderBook):
        """Обновление открытых позиций"""
        current_price = orderbook.get_mid_price()
        self.equity_curve.append({
            'timestamp': orderbook.timestamp,
            'equity': self.calculate_equity(current_price)
        })
        
    def calculate_equity(self, current_price: float) -> float:
        """Расчет текущего капитала"""
        return self.balance + sum(
            pos['size'] * (current_price - pos['entry_price'])
            for pos in self.positions.values()
        )
        
    def calculate_statistics(self) -> Dict:
        """Расчет статистики бэктеста"""
        returns = pd.Series([t['pnl'] for t in self.trades_history])
        equity = pd.Series([e['equity'] for e in self.equity_curve])
        
        return {
            'total_trades': len(self.trades_history),
            'profitable_trades': len(returns[returns > 0]),
            'win_rate': len(returns[returns > 0]) / len(returns) if len(returns) > 0 else 0,
            'profit_factor': abs(returns[returns > 0].sum() / returns[returns < 0].sum()) \
                           if len(returns[returns < 0]) > 0 else float('inf'),
            'sharpe_ratio': returns.mean() / returns.std() * np.sqrt(252) if len(returns) > 0 else 0,
            'max_drawdown': self.calculate_max_drawdown(equity),
            'total_return': (self.balance - self.initial_balance) / self.initial_balance
        }
        
    @staticmethod
    def calculate_max_drawdown(equity: pd.Series) -> float:
        """Расчет максимальной просадки"""
        peak = equity.expanding(min_periods=1).max()
        drawdown = (equity - peak) / peak
        return float(drawdown.min())
        
    def plot_results(self, save_path: Path):
        """Построение графиков результатов"""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
        
        # График капитала
        equity_df = pd.DataFrame(self.equity_curve)
        ax1.plot(equity_df['timestamp'], equity_df['equity'])
        ax1.set_title('Equity Curve')
        
        # График просадок
        drawdown = self.calculate_drawdown_series(equity_df['equity'])
        ax2.fill_between(equity_df['timestamp'], drawdown, 0, alpha=0.3, color='red')
        ax2.set_title('Drawdown')
        
        plt.tight_layout()
        plt.savefig(save_path / 'backtest_results.png')
        
    @staticmethod
    def calculate_drawdown_series(equity: pd.Series) -> pd.Series:
        """Расчет серии просадок"""
        peak = equity.expanding(min_periods=1).max()
        return (equity - peak) / peak

async def main():
    try:
        # Параметры бэктеста
        symbol = "BTC-USDT"
        start_date = "2024-01-01"
        end_date = "2024-02-01"
        
        backtester = Backtester(BACKTEST_CONFIG)
        
        # Загрузка данных
        data = await backtester.load_data(symbol, start_date, end_date)
        
        # Запуск всех стратегий
        results = {}
        for strategy_name, strategy_config in STRATEGY_CONFIGS.items():
            logger.info(f"Running backtest for {strategy_name}")
            strategy = BaseStrategy.create_strategy(strategy_name, strategy_config)
            results[strategy_name] = backtester.run_strategy(strategy, data)
            
        # Сохранение результатов
        results_path = Path(BACKTEST_CONFIG['results_dir'])
        results_path.mkdir(exist_ok=True, parents=True)
        
        with open(results_path / f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 'w') as f:
            json.dump(results, f, indent=2)
            
        backtester.plot_results(results_path)
        logger.info("Backtest completed successfully")
        
    except Exception as e:
        logger.error(f"Backtest error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())